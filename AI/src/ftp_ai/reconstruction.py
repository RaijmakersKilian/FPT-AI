from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np


def build_sparse_point_cloud_from_video(
    video_path: Path,
    output_dir: Path,
    frame_a: int,
    frame_b: int,
    max_dimension: int = 1280,
    max_points: int = 6000,
    focal_scale: float = 1.2,
) -> dict[str, object]:
    """Build a small two-view sparse point cloud from drone footage.

    This is a fast structure-from-motion proof of concept, not a metric bridge
    model. Scale is arbitrary because no camera calibration/GPS/IMU is available.
    """

    cv2 = _import_cv2()
    output_dir.mkdir(parents=True, exist_ok=True)

    image_a = _read_video_frame(cv2, video_path, frame_a)
    image_b = _read_video_frame(cv2, video_path, frame_b)
    image_a = _fit_within(cv2, image_a, max_dimension)
    image_b = _fit_within(cv2, image_b, max_dimension)

    cv2.imwrite(str(output_dir / "frame_a.jpg"), image_a)
    cv2.imwrite(str(output_dir / "frame_b.jpg"), image_b)

    keypoints_a, keypoints_b, matches, matcher_name = _match_features(cv2, image_a, image_b)
    if len(matches) < 40:
        raise RuntimeError(f"Only {len(matches)} feature matches found; need at least 40.")

    points_a = np.float64([keypoints_a[match.queryIdx].pt for match in matches])
    points_b = np.float64([keypoints_b[match.trainIdx].pt for match in matches])
    height, width = image_a.shape[:2]
    focal = focal_scale * max(width, height)
    camera = np.array(
        [[focal, 0.0, width / 2.0], [0.0, focal, height / 2.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )

    essential, essential_mask = cv2.findEssentialMat(
        points_a,
        points_b,
        camera,
        method=cv2.RANSAC,
        prob=0.999,
        threshold=1.0,
    )
    if essential is None or essential_mask is None:
        raise RuntimeError("Could not estimate camera motion from matched features.")
    if essential.shape[0] > 3:
        essential = essential[:3]

    inlier_mask = essential_mask.ravel().astype(bool)
    points_a_in = points_a[inlier_mask]
    points_b_in = points_b[inlier_mask]
    if len(points_a_in) < 30:
        raise RuntimeError(f"Only {len(points_a_in)} geometric inliers found; need at least 30.")

    _, rotation, translation, pose_mask = cv2.recoverPose(
        essential,
        points_a_in,
        points_b_in,
        camera,
    )
    pose_mask = pose_mask.ravel().astype(bool)
    points_a_pose = points_a_in[pose_mask]
    points_b_pose = points_b_in[pose_mask]
    if len(points_a_pose) < 20:
        raise RuntimeError(f"Only {len(points_a_pose)} pose inliers found; need at least 20.")

    cloud, colors, reprojection_errors = _triangulate(
        cv2,
        image_a,
        points_a_pose,
        points_b_pose,
        camera,
        rotation,
        translation,
    )
    if len(cloud) == 0:
        raise RuntimeError("Triangulation produced no valid 3D points.")

    order = np.argsort(reprojection_errors)
    if len(order) > max_points:
        order = order[:max_points]
    cloud = cloud[order]
    colors = colors[order]
    reprojection_errors = reprojection_errors[order]

    ply_path = output_dir / "sparse_point_cloud.ply"
    _write_ply(ply_path, cloud, colors)
    _write_pointcloud_preview(cv2, output_dir / "pointcloud_preview.jpg", cloud, colors)
    _write_match_preview(
        cv2,
        output_dir / "matches_preview.jpg",
        image_a,
        image_b,
        keypoints_a,
        keypoints_b,
        [matches[index] for index, keep in enumerate(inlier_mask) if keep][:100],
    )

    metrics: dict[str, object] = {
        "video": str(video_path),
        "frame_a": frame_a,
        "frame_b": frame_b,
        "matcher": matcher_name,
        "raw_matches": len(matches),
        "essential_inliers": int(inlier_mask.sum()),
        "pose_inliers": int(pose_mask.sum()),
        "points_written": int(len(cloud)),
        "mean_reprojection_error_px": round(float(reprojection_errors.mean()), 3),
        "median_reprojection_error_px": round(float(np.median(reprojection_errors)), 3),
        "outputs": {
            "ply": str(ply_path),
            "pointcloud_preview": str(output_dir / "pointcloud_preview.jpg"),
            "matches_preview": str(output_dir / "matches_preview.jpg"),
        },
        "limitations": [
            "Sparse point cloud only, not a complete mesh.",
            "Scale is arbitrary without camera calibration or drone GPS/IMU.",
            "Moving vehicles and parallax can create noisy points.",
        ],
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def build_colmap_mesh_from_video(
    video_path: Path,
    output_dir: Path,
    colmap_path: Path | None = None,
    frame_interval_seconds: float = 0.5,
    start_seconds: float = 0.0,
    max_frames: int = 120,
    blur_threshold: float = 50.0,
    max_image_size: int = 1600,
    sequential_overlap: int = 15,
    matcher: str = "sequential",
    run_dense: bool = True,
) -> dict[str, object]:
    """Run a COLMAP video-to-mesh pipeline.

    This is the first "real photogrammetry" path: it extracts video frames,
    estimates camera poses, and then tries dense stereo + meshing. The dense
    steps are CPU-heavy with the current no-CUDA COLMAP binary.
    """

    cv2 = _import_cv2()
    video_path = video_path.resolve()
    output_dir = output_dir.resolve()
    colmap = _resolve_colmap_path(colmap_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    images_dir = output_dir / "images"
    database_path = output_dir / "database.db"
    sparse_dir = output_dir / "sparse"
    sparse_model_dir = sparse_dir / "0"
    sparse_txt_dir = output_dir / "sparse_txt"
    dense_dir = output_dir / "dense"
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    if database_path.exists():
        raise RuntimeError(
            f"{database_path} already exists. Use a new output folder for a fresh COLMAP run."
        )

    frames = _extract_video_frames_by_time(
        cv2=cv2,
        video_path=video_path,
        output_dir=images_dir,
        interval_seconds=frame_interval_seconds,
        start_seconds=start_seconds,
        max_frames=max_frames,
        blur_threshold=blur_threshold,
    )
    summary: dict[str, object] = {
        "tool": "COLMAP",
        "video": str(video_path),
        "colmap": str(colmap),
        "frame_interval_seconds": frame_interval_seconds,
        "start_seconds": start_seconds,
        "input_frames": len(frames),
        "matcher": matcher,
        "status": "started",
        "outputs": {
            "images": str(images_dir),
            "database": str(database_path),
            "sparse_model": str(sparse_model_dir),
            "sparse_point_cloud": str(output_dir / "sparse_point_cloud.ply"),
            "dense_workspace": str(dense_dir),
            "dense_point_cloud": str(output_dir / "dense_point_cloud.ply"),
            "mesh": str(output_dir / "mesh.ply"),
        },
    }
    _write_summary(output_dir, summary)

    if len(frames) < 3:
        summary["status"] = "failed"
        summary["error"] = f"Only {len(frames)} usable frames extracted; need at least 3."
        _write_summary(output_dir, summary)
        return summary

    try:
        _run_colmap_step(
            "feature_extractor",
            logs_dir,
            [
                colmap,
                "feature_extractor",
                "--database_path",
                database_path,
                "--image_path",
                images_dir,
                "--ImageReader.single_camera",
                "1",
                "--FeatureExtraction.use_gpu",
                "0",
                "--FeatureExtraction.max_image_size",
                str(max_image_size),
            ],
        )
        if matcher == "exhaustive":
            _run_colmap_step(
                "exhaustive_matcher",
                logs_dir,
                [
                    colmap,
                    "exhaustive_matcher",
                    "--database_path",
                    database_path,
                    "--FeatureMatching.use_gpu",
                    "0",
                ],
            )
        else:
            _run_colmap_step(
                "sequential_matcher",
                logs_dir,
                [
                    colmap,
                    "sequential_matcher",
                    "--database_path",
                    database_path,
                    "--FeatureMatching.use_gpu",
                    "0",
                    "--SequentialMatching.overlap",
                    str(sequential_overlap),
                ],
            )
        sparse_dir.mkdir(parents=True, exist_ok=True)
        _run_colmap_step(
            "mapper",
            logs_dir,
            [
                colmap,
                "mapper",
                "--database_path",
                database_path,
                "--image_path",
                images_dir,
                "--output_path",
                sparse_dir,
                "--Mapper.min_num_matches",
                "15",
                "--Mapper.init_min_num_inliers",
                "30",
                "--Mapper.init_min_tri_angle",
                "2",
                "--Mapper.init_max_forward_motion",
                "1",
                "--Mapper.abs_pose_min_num_inliers",
                "15",
                "--Mapper.tri_ignore_two_view_tracks",
                "0",
            ],
        )

        if not sparse_model_dir.exists():
            summary["status"] = "failed_sparse"
            summary["error"] = "COLMAP did not produce sparse/0."
            _write_summary(output_dir, summary)
            return summary

        _run_colmap_step(
            "model_converter_sparse_ply",
            logs_dir,
            [
                colmap,
                "model_converter",
                "--input_path",
                sparse_model_dir,
                "--output_path",
                output_dir / "sparse_point_cloud.ply",
                "--output_type",
                "PLY",
            ],
        )
        sparse_txt_dir.mkdir(parents=True, exist_ok=True)
        _run_colmap_step(
            "model_converter_sparse_txt",
            logs_dir,
            [
                colmap,
                "model_converter",
                "--input_path",
                sparse_model_dir,
                "--output_path",
                sparse_txt_dir,
                "--output_type",
                "TXT",
            ],
        )
        summary.update(_read_colmap_txt_metrics(sparse_txt_dir))
        summary["status"] = "sparse_success"
        _write_summary(output_dir, summary)

        if not run_dense:
            return summary

        _run_colmap_step(
            "image_undistorter",
            logs_dir,
            [
                colmap,
                "image_undistorter",
                "--image_path",
                images_dir,
                "--input_path",
                sparse_model_dir,
                "--output_path",
                dense_dir,
                "--output_type",
                "COLMAP",
                "--max_image_size",
                str(max_image_size),
            ],
        )
        _run_colmap_step(
            "patch_match_stereo",
            logs_dir,
            [
                colmap,
                "patch_match_stereo",
                "--workspace_path",
                dense_dir,
                "--workspace_format",
                "COLMAP",
                "--PatchMatchStereo.gpu_index",
                "-1",
                "--PatchMatchStereo.max_image_size",
                str(max_image_size),
                "--PatchMatchStereo.geom_consistency",
                "1",
            ],
        )
        _run_colmap_step(
            "stereo_fusion",
            logs_dir,
            [
                colmap,
                "stereo_fusion",
                "--workspace_path",
                dense_dir,
                "--workspace_format",
                "COLMAP",
                "--input_type",
                "geometric",
                "--output_path",
                output_dir / "dense_point_cloud.ply",
            ],
        )
        _run_colmap_step(
            "poisson_mesher",
            logs_dir,
            [
                colmap,
                "poisson_mesher",
                "--input_path",
                output_dir / "dense_point_cloud.ply",
                "--output_path",
                output_dir / "mesh.ply",
                "--PoissonMeshing.depth",
                "10",
            ],
        )
        summary.update(_read_ply_header(output_dir / "dense_point_cloud.ply", "dense"))
        summary.update(_read_ply_header(output_dir / "mesh.ply", "mesh"))
        summary["status"] = "mesh_success"
        _write_summary(output_dir, summary)
        return summary
    except RuntimeError as exc:
        summary["status"] = "partial_or_failed"
        summary["error"] = str(exc)
        _write_summary(output_dir, summary)
        return summary


def build_dust3r_3d_from_video(
    video_path: Path,
    output_dir: Path,
    n_frames: int = 60,
    image_size: int = 512,
    scene_graph: str = "swin",
    niter: int = 300,
    batch_size: int = 1,
    model_name: str | None = None,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
    blur_threshold: float = 50.0,
    max_output_points: int = 500_000,
) -> dict[str, object]:
    """Run DUSt3R/MASt3R neural 3D reconstruction on drone video footage.

    Install first: pip install git+https://github.com/naver/mast3r.git
    Model weights (~1.5 GB) download from HuggingFace automatically on first run.
    """
    import torch

    cv2 = _import_cv2()
    model_cls, default_model_name, backend = _import_dust3r_or_mast3r()
    used_model_name = model_name or default_model_name
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "frames"

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    total_seconds = total_frame_count / fps if total_frame_count > 0 else 0.0
    effective_end = min(end_seconds, total_seconds) if end_seconds is not None else total_seconds
    duration = max(1.0, effective_end - start_seconds)
    interval_seconds = max(0.3, duration / n_frames)

    frames = _extract_video_frames_by_time(
        cv2=cv2,
        video_path=video_path,
        output_dir=images_dir,
        interval_seconds=interval_seconds,
        start_seconds=start_seconds,
        max_frames=n_frames,
        blur_threshold=blur_threshold,
    )
    if len(frames) < 2:
        raise RuntimeError(
            f"Only {len(frames)} usable frames after blur filtering "
            f"(threshold={blur_threshold}). Lower --blur-threshold and retry."
        )

    # _import_dust3r_or_mast3r already inserted the right paths into sys.path
    try:
        from dust3r.inference import inference  # type: ignore
        from dust3r.utils.image import load_images  # type: ignore
        from dust3r.image_pairs import make_pairs  # type: ignore
        from dust3r.cloud_opt import global_aligner, GlobalAlignerMode  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "DUSt3R inference modules not found.\n"
            "Clone: git clone --recursive https://github.com/naver/mast3r.git AI/.external/mast3r"
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model_cls.from_pretrained(used_model_name).to(device)
    model.eval()

    filelist = [str(f) for f in frames]
    images_data = load_images(filelist, size=image_size)
    pairs = make_pairs(images_data, scene_graph=scene_graph, prefilter=None, symmetrize=True)
    output = inference(pairs, model, device, batch_size=batch_size, verbose=True)

    scene = global_aligner(output, device=device, mode=GlobalAlignerMode.PointCloudOptimizer)
    loss = scene.compute_global_alignment(init="mst", niter=niter, schedule="cosine", lr=0.01)

    pts3d_tensors = scene.get_pts3d()
    masks_tensors = scene.get_masks()
    imgs_arrays = scene.imgs

    all_pts: list[np.ndarray] = []
    all_colors: list[np.ndarray] = []
    for pts_t, mask_t, img_arr in zip(pts3d_tensors, masks_tensors, imgs_arrays):
        pts_np = pts_t.detach().cpu().numpy()
        mask_np = mask_t.detach().cpu().numpy().astype(bool)
        img_np = (np.clip(img_arr, 0.0, 1.0) * 255).astype(np.uint8)
        all_pts.append(pts_np[mask_np])
        all_colors.append(img_np[mask_np])

    cloud = np.concatenate(all_pts, axis=0)
    colors_out = np.concatenate(all_colors, axis=0)

    if len(cloud) > max_output_points:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(cloud), size=max_output_points, replace=False)
        cloud = cloud[idx]
        colors_out = colors_out[idx]

    ply_path = output_dir / "pointcloud.ply"
    _write_ply(ply_path, cloud, colors_out)

    summary: dict[str, object] = {
        "tool": backend,
        "model": used_model_name,
        "video": str(video_path),
        "frames_extracted": len(frames),
        "pairs_computed": len(pairs),
        "image_size": image_size,
        "scene_graph": scene_graph,
        "niter": niter,
        "final_loss": round(float(loss), 6) if loss is not None else None,
        "points_written": int(len(cloud)),
        "device": device,
        "outputs": {
            "frames": str(images_dir),
            "pointcloud_ply": str(ply_path),
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _import_dust3r_or_mast3r():
    """Return (model_class, default_model_name, backend_name).

    Prefers MASt3R (better quality) over plain DUSt3R.
    Automatically adds the bundled .external/mast3r source tree to sys.path
    if the packages are not pip-installed.
    """
    import sys

    # Try a plain import first (works if the user pip-installed the packages)
    try:
        from mast3r.model import AsymmetricMASt3R  # type: ignore
        return (
            AsymmetricMASt3R,
            "naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric",
            "mast3r",
        )
    except ImportError:
        pass

    # Fall back to the bundled clone at AI/.external/mast3r
    # __file__ = AI/src/ftp_ai/reconstruction.py → parents[2] = AI/
    _ext = Path(__file__).resolve().parents[2] / ".external" / "mast3r"
    _dust3r_src = _ext / "dust3r"
    _croco_src = _ext / "dust3r" / "croco"
    for _p in (_ext, _dust3r_src, _croco_src):
        if _p.exists() and str(_p) not in sys.path:
            sys.path.insert(0, str(_p))

    try:
        from mast3r.model import AsymmetricMASt3R  # type: ignore
        return (
            AsymmetricMASt3R,
            "naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric",
            "mast3r",
        )
    except ImportError:
        pass
    try:
        from dust3r.model import AsymmetricCroCo3DStereo  # type: ignore
        return (
            AsymmetricCroCo3DStereo,
            "naver/DUSt3R_ViTLarge_BaseDecoder_512_dpt",
            "dust3r",
        )
    except ImportError:
        pass
    raise RuntimeError(
        "Neither mast3r nor dust3r could be imported.\n"
        "Clone the repo:  git clone --recursive https://github.com/naver/mast3r.git AI/.external/mast3r\n"
        "Then install deps: pip install scikit-learn roma einops trimesh huggingface-hub\n"
        "Model weights (~1.5 GB) download from HuggingFace automatically on first run."
    )


def _resolve_colmap_path(colmap_path: Path | None) -> Path:
    if colmap_path:
        resolved = colmap_path.resolve()
    else:
        bundled = Path("AI/.external/colmap/nocuda/bin/colmap.exe")
        resolved = bundled.resolve() if bundled.exists() else Path(shutil.which("colmap") or "")
    if not resolved or not resolved.exists():
        raise RuntimeError(
            "COLMAP executable not found. Pass --colmap-path or install COLMAP on PATH."
        )
    return resolved


def _extract_video_frames_by_time(
    cv2,
    video_path: Path,
    output_dir: Path,
    interval_seconds: float,
    start_seconds: float,
    max_frames: int,
    blur_threshold: float,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    start_frame = max(0, int(round(start_seconds * fps)))
    step = max(1, int(round(interval_seconds * fps)))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    selected: list[Path] = []

    try:
        frame_index = start_frame
        while len(selected) < max_frames and (total_frames <= 0 or frame_index < total_frames):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if blur >= blur_threshold:
                frame_path = output_dir / f"frame_{frame_index:08d}.jpg"
                cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                selected.append(frame_path)
            frame_index += step
    finally:
        cap.release()

    return selected


def _run_colmap_step(name: str, logs_dir: Path, command: list[object]) -> None:
    stdout_path = logs_dir / f"{name}.stdout.log"
    stderr_path = logs_dir / f"{name}.stderr.log"
    result = subprocess.run(
        [str(item) for item in command],
        cwd=str(logs_dir.parent),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_text(result.stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(result.stderr, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        tail = "\n".join(result.stderr.splitlines()[-20:])
        raise RuntimeError(f"COLMAP step '{name}' failed with code {result.returncode}: {tail}")


def _read_colmap_txt_metrics(sparse_txt_dir: Path) -> dict[str, object]:
    images_path = sparse_txt_dir / "images.txt"
    points_path = sparse_txt_dir / "points3D.txt"
    registered_images = 0
    sparse_points = 0

    if images_path.exists():
        for line in images_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line and not line.startswith("#") and line.lower().endswith((".jpg", ".jpeg", ".png")):
                registered_images += 1

    if points_path.exists():
        sparse_points = sum(
            1
            for line in points_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line and not line.startswith("#")
        )

    return {
        "registered_images": registered_images,
        "sparse_points": sparse_points,
    }


def _read_ply_header(path: Path, prefix: str) -> dict[str, object]:
    metrics: dict[str, object] = {}
    if not path.exists():
        return metrics
    with path.open("rb") as handle:
        for raw_line in handle:
            line = raw_line.decode("ascii", errors="ignore").strip()
            if line.startswith("element vertex "):
                metrics[f"{prefix}_vertices"] = int(line.split()[-1])
            elif line.startswith("element face "):
                metrics[f"{prefix}_faces"] = int(line.split()[-1])
            elif line == "end_header":
                break
    return metrics


def _write_summary(output_dir: Path, summary: dict[str, object]) -> None:
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _read_video_frame(cv2, video_path: Path, frame_index: int):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = cap.read()
        if not ok or frame is None:
            raise ValueError(f"Could not read frame {frame_index} from {video_path}")
        return frame
    finally:
        cap.release()


def _match_features(cv2, image_a, image_b):
    gray_a = cv2.cvtColor(image_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(image_b, cv2.COLOR_BGR2GRAY)

    if hasattr(cv2, "SIFT_create"):
        detector = cv2.SIFT_create(nfeatures=8000)
        norm = cv2.NORM_L2
        matcher_name = "SIFT"
    else:
        detector = cv2.ORB_create(nfeatures=9000, fastThreshold=7)
        norm = cv2.NORM_HAMMING
        matcher_name = "ORB"

    keypoints_a, descriptors_a = detector.detectAndCompute(gray_a, None)
    keypoints_b, descriptors_b = detector.detectAndCompute(gray_b, None)
    if descriptors_a is None or descriptors_b is None:
        raise RuntimeError("Could not compute feature descriptors for both frames.")

    matcher = cv2.BFMatcher(norm)
    pairs = matcher.knnMatch(descriptors_a, descriptors_b, k=2)
    matches = []
    for pair in pairs:
        if len(pair) != 2:
            continue
        best, second = pair
        if best.distance < 0.74 * second.distance:
            matches.append(best)
    matches = sorted(matches, key=lambda item: item.distance)
    return keypoints_a, keypoints_b, matches, matcher_name


def _triangulate(cv2, image, points_a, points_b, camera, rotation, translation):
    projection_a = camera @ np.hstack([np.eye(3), np.zeros((3, 1))])
    projection_b = camera @ np.hstack([rotation, translation])

    homogeneous = cv2.triangulatePoints(
        projection_a,
        projection_b,
        points_a.T,
        points_b.T,
    )
    points_3d = (homogeneous[:3] / np.maximum(homogeneous[3:], 1e-9)).T
    points_3d_b = (rotation @ points_3d.T + translation).T

    finite = np.isfinite(points_3d).all(axis=1)
    positive_depth = (points_3d[:, 2] > 0) & (points_3d_b[:, 2] > 0)
    negative_depth = (points_3d[:, 2] < 0) & (points_3d_b[:, 2] < 0)
    if int(negative_depth.sum()) > int(positive_depth.sum()):
        points_3d = -points_3d
        points_3d_b = (rotation @ points_3d.T + translation).T
        positive_depth = (points_3d[:, 2] > 0) & (points_3d_b[:, 2] > 0)

    if int(positive_depth.sum()) >= 10:
        reasonable_depth = points_3d[:, 2] < np.percentile(points_3d[positive_depth, 2], 98)
        keep = finite & positive_depth & reasonable_depth
    else:
        depths = np.linalg.norm(points_3d, axis=1)
        keep = finite & (depths < np.percentile(depths[finite], 95))

    points_3d = points_3d[keep]
    points_a = points_a[keep]
    points_b = points_b[keep]
    if len(points_3d) == 0:
        return points_3d, np.zeros((0, 3), dtype=np.uint8), np.zeros((0,), dtype=np.float64)

    reproj_a = _project(points_3d, camera, np.eye(3), np.zeros((3, 1)))
    reproj_b = _project(points_3d, camera, rotation, translation)
    errors = (np.linalg.norm(reproj_a - points_a, axis=1) + np.linalg.norm(reproj_b - points_b, axis=1)) / 2.0
    keep_error = errors < np.percentile(errors, 90)

    points_3d = points_3d[keep_error]
    points_a = points_a[keep_error]
    errors = errors[keep_error]

    height, width = image.shape[:2]
    xy = np.round(points_a).astype(int)
    xy[:, 0] = np.clip(xy[:, 0], 0, width - 1)
    xy[:, 1] = np.clip(xy[:, 1], 0, height - 1)
    colors_bgr = image[xy[:, 1], xy[:, 0]]
    colors_rgb = colors_bgr[:, ::-1].astype(np.uint8)
    return points_3d, colors_rgb, errors


def _project(points_3d, camera, rotation, translation):
    points_camera = (rotation @ points_3d.T + translation).T
    projected = (camera @ points_camera.T).T
    return projected[:, :2] / np.maximum(projected[:, 2:], 1e-9)


def _write_ply(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write("ply\n")
        handle.write("format ascii 1.0\n")
        handle.write(f"element vertex {len(points)}\n")
        handle.write("property float x\n")
        handle.write("property float y\n")
        handle.write("property float z\n")
        handle.write("property uchar red\n")
        handle.write("property uchar green\n")
        handle.write("property uchar blue\n")
        handle.write("end_header\n")
        for point, color in zip(points, colors):
            handle.write(
                f"{point[0]:.6f} {point[1]:.6f} {point[2]:.6f} "
                f"{int(color[0])} {int(color[1])} {int(color[2])}\n"
            )


def _write_pointcloud_preview(cv2, path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    canvas = np.zeros((900, 1200, 3), dtype=np.uint8)
    if len(points) == 0:
        cv2.imwrite(str(path), canvas)
        return

    x = points[:, 0]
    z = points[:, 2]
    x_min, x_max = np.percentile(x, [2, 98])
    z_min, z_max = np.percentile(z, [2, 98])
    x_norm = (x - x_min) / max(1e-9, x_max - x_min)
    z_norm = (z - z_min) / max(1e-9, z_max - z_min)
    px = np.clip((x_norm * 1150 + 25).astype(int), 0, 1199)
    py = np.clip(((1.0 - z_norm) * 850 + 25).astype(int), 0, 899)

    colors_bgr = colors[:, ::-1]
    for point_x, point_y, color in zip(px, py, colors_bgr):
        cv2.circle(canvas, (int(point_x), int(point_y)), 2, tuple(int(v) for v in color), -1)
    cv2.putText(
        canvas,
        "Sparse 3D point cloud preview (X/Z view, arbitrary scale)",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (230, 230, 230),
        2,
        cv2.LINE_AA,
    )
    cv2.imwrite(str(path), canvas)


def _write_match_preview(
    cv2,
    path: Path,
    image_a,
    image_b,
    keypoints_a,
    keypoints_b,
    matches,
) -> None:
    preview = cv2.drawMatches(
        image_a,
        keypoints_a,
        image_b,
        keypoints_b,
        matches,
        None,
        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
    )
    cv2.imwrite(str(path), _fit_within(cv2, preview, 1800))


def _fit_within(cv2, image, max_dimension: int):
    height, width = image.shape[:2]
    largest = max(height, width)
    if largest <= max_dimension:
        return image
    scale = max_dimension / largest
    size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(image, size)


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for 3D reconstruction.") from exc
    return cv2
