from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from .batch import run_roi_batch
from .classification import IdentitySegmentClassifier
from .config import PipelineConfig
from .gaussian_splat import pointcloud_to_gaussian_splat
from .model_comparison import compare_reconstruction_to_model
from .panorama import build_drone_panorama, build_slitscan_panorama, build_smooth_panorama, build_strip_panorama
from .pipeline import run_image_pipeline, run_video_pipeline
from .reconstruction import (
    build_colmap_mesh_from_video,
    build_dust3r_3d_from_video,
    build_sparse_point_cloud_from_video,
)
from .roi import Sam3ConstructionRoiDetector
from .segmentation import (
    ClassicalSegmenter,
    SAM3_OBJECT_PROMPTS,
    SAM3_PROGRESS_PROMPTS,
    Sam2AutomaticSegmenter,
    Sam3TextPromptSegmenter,
)
from .video import extract_panorama_frames
from .video_overlay import build_segmentation_overlay_video


console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="GOT bridge AI progress pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    video_parser = subparsers.add_parser("run-video", help="Run pipeline from a drone video")
    video_parser.add_argument("--video", type=Path, required=True)
    video_parser.add_argument("--output", type=Path, required=True)
    video_parser.add_argument("--config", type=Path)
    video_parser.add_argument("--sample-every", type=int)
    video_parser.add_argument(
        "--segmenter",
        choices=["classical", "sam2-auto", "sam3", "sam3-progress", "sam3-objects"],
        default="classical",
    )
    video_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="none")
    video_parser.add_argument("--analysis-max-dimension", type=int)

    overlay_parser = subparsers.add_parser(
        "run-video-overlay",
        help="Run segmentation on sampled video frames and write an overlay MP4",
    )
    overlay_parser.add_argument("--video", type=Path, required=True)
    overlay_parser.add_argument("--output", type=Path, required=True)
    overlay_parser.add_argument(
        "--segmenter",
        choices=["classical", "sam2-auto", "sam3", "sam3-progress", "sam3-objects"],
        default="sam2-auto",
    )
    overlay_parser.add_argument(
        "--sample-every",
        type=int,
        default=60,
        help="Process one frame every N source frames. For 60fps video, 60 = 1 sample per second.",
    )
    overlay_parser.add_argument("--max-dimension", type=int, default=960)
    overlay_parser.add_argument("--output-fps", type=float, default=6.0)
    overlay_parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional cap for quick demos.",
    )

    image_parser = subparsers.add_parser("run-image", help="Run pipeline from one image")
    image_parser.add_argument("--image", type=Path, required=True)
    image_parser.add_argument("--output", type=Path, required=True)
    image_parser.add_argument("--config", type=Path)
    image_parser.add_argument(
        "--segmenter",
        choices=["classical", "sam2-auto", "sam3", "sam3-progress", "sam3-objects"],
        default="classical",
    )
    image_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="none")
    image_parser.add_argument("--analysis-max-dimension", type=int)

    images_parser = subparsers.add_parser("run-images", help="Run pipeline from an image folder")
    images_parser.add_argument("--images", type=Path, required=True)
    images_parser.add_argument("--output", type=Path, required=True)
    images_parser.add_argument("--config", type=Path)
    images_parser.add_argument(
        "--segmenter",
        choices=["classical", "sam2-auto", "sam3", "sam3-progress", "sam3-objects"],
        default="classical",
    )
    images_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="none")
    images_parser.add_argument("--analysis-max-dimension", type=int)

    batch_parser = subparsers.add_parser(
        "run-roi-batch",
        help="Run ROI analysis on a spread of images and write a batch summary",
    )
    batch_parser.add_argument("--images", type=Path, required=True)
    batch_parser.add_argument("--output", type=Path, required=True)
    batch_parser.add_argument("--config", type=Path)
    batch_parser.add_argument("--limit", type=int, default=10)
    batch_parser.add_argument(
        "--segmenter",
        choices=["classical", "sam2-auto", "sam3", "sam3-progress", "sam3-objects"],
        default="classical",
    )
    batch_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="sam3-construction")
    batch_parser.add_argument("--analysis-max-dimension", type=int)

    panorama_parser = subparsers.add_parser(
        "build-panorama",
        help="Build a smooth panorama from an image folder",
    )
    panorama_parser.add_argument("--images", type=Path, required=True)
    panorama_parser.add_argument("--output", type=Path, required=True)
    panorama_parser.add_argument("--max-dimension", type=int, default=4096)
    panorama_parser.add_argument("--method", choices=["stitcher", "strip"], default="stitcher")
    panorama_parser.add_argument("--max-images", type=int, default=80)

    video_pano_parser = subparsers.add_parser(
        "build-video-panorama",
        help="Extract frames from a drone video and stitch them into a full bridge panorama",
    )
    video_pano_parser.add_argument("--video", type=Path, required=True, help="Drone video file")
    video_pano_parser.add_argument("--output", type=Path, required=True, help="Output panorama path (.jpg)")
    video_pano_parser.add_argument(
        "--n-tiles",
        type=int,
        default=200,
        help="Maximum number of overlapping frames to extract from the video (default 200)",
    )
    video_pano_parser.add_argument(
        "--blur-threshold",
        type=float,
        default=80.0,
        help="Minimum sharpness score to keep a frame (default 80; lower if too few frames pass)",
    )
    video_pano_parser.add_argument(
        "--sample-every",
        type=int,
        default=15,
        help="Extract one frame every N video frames (default 15, tuned for 60fps drone footage; use 8 for 30fps, 1 for very short clips)",
    )
    video_pano_parser.add_argument(
        "--work-width",
        type=int,
        default=1280,
        help="Resize tiles to this width before feature matching (default 1280)",
    )
    video_pano_parser.add_argument(
        "--max-dimension",
        type=int,
        default=8192,
        help="Longest side of the output panorama in pixels (default 8192)",
    )
    video_pano_parser.add_argument(
        "--tiles-dir",
        type=Path,
        default=None,
        help="Where to save extracted tiles (defaults to <output_dir>/mosaic_tiles)",
    )
    video_pano_parser.add_argument(
        "--start-frame",
        type=int,
        default=0,
        help="Skip this many video frames before extracting (useful to skip takeoff/approach)",
    )
    video_pano_parser.add_argument(
        "--rotate",
        action="store_true",
        default=False,
        help="Rotate each frame 90 degrees clockwise before stitching (use when bridge runs top-to-bottom in the video)",
    )
    video_pano_parser.add_argument(
        "--method",
        choices=["drone", "slitscan"],
        default="drone",
        help="Stitching method: 'drone' = SIFT feature chain (default), 'slitscan' = fixed-strip concatenation (no rotation artefacts, best for steady forward flight)",
    )

    sparse_3d_parser = subparsers.add_parser(
        "build-sparse-3d",
        help="Build a two-view sparse 3D point cloud proof of concept from a drone video",
    )
    sparse_3d_parser.add_argument("--video", type=Path, required=True)
    sparse_3d_parser.add_argument("--output", type=Path, required=True)
    sparse_3d_parser.add_argument("--frame-a", type=int, required=True)
    sparse_3d_parser.add_argument("--frame-b", type=int, required=True)
    sparse_3d_parser.add_argument("--max-dimension", type=int, default=1280)
    sparse_3d_parser.add_argument("--max-points", type=int, default=6000)

    colmap_mesh_parser = subparsers.add_parser(
        "build-colmap-mesh",
        help="Extract video frames and run COLMAP sparse + dense reconstruction to create a mesh",
    )
    colmap_mesh_parser.add_argument("--video", type=Path, required=True)
    colmap_mesh_parser.add_argument("--output", type=Path, required=True)
    colmap_mesh_parser.add_argument(
        "--colmap-path",
        type=Path,
        default=None,
        help="Path to colmap.exe. Defaults to AI/.external/colmap/nocuda/bin/colmap.exe or PATH.",
    )
    colmap_mesh_parser.add_argument(
        "--frame-interval",
        type=float,
        default=0.5,
        help="Seconds between extracted frames (default 0.5).",
    )
    colmap_mesh_parser.add_argument(
        "--start-seconds",
        type=float,
        default=0.0,
        help="Start reading the video from this timestamp in seconds.",
    )
    colmap_mesh_parser.add_argument(
        "--max-frames",
        type=int,
        default=120,
        help="Maximum frames to extract for reconstruction (default 120).",
    )
    colmap_mesh_parser.add_argument(
        "--blur-threshold",
        type=float,
        default=50.0,
        help="Skip frames blurrier than this Laplacian score (default 50).",
    )
    colmap_mesh_parser.add_argument(
        "--max-image-size",
        type=int,
        default=1600,
        help="Maximum image size used by COLMAP feature/dense steps (default 1600).",
    )
    colmap_mesh_parser.add_argument(
        "--sequential-overlap",
        type=int,
        default=15,
        help="How many neighboring frames COLMAP should match in video order (default 15).",
    )
    colmap_mesh_parser.add_argument(
        "--matcher",
        choices=["sequential", "exhaustive"],
        default="sequential",
        help="COLMAP matcher. Use exhaustive for small frame sets when sequential matching registers too few frames.",
    )
    colmap_mesh_parser.add_argument(
        "--skip-dense",
        action="store_true",
        default=False,
        help="Only run sparse SfM; skip dense cloud and mesh.",
    )

    compare_3d_parser = subparsers.add_parser(
        "compare-3d-model",
        help="Compare a current reconstruction against the completed bridge model",
    )
    compare_3d_parser.add_argument("--current", type=Path, required=True, help="Current/as-built PLY reconstruction")
    compare_3d_parser.add_argument("--final-model", type=Path, required=True, help="Completed bridge model (.glb/.gltf/.obj)")
    compare_3d_parser.add_argument("--output", type=Path, required=True)
    compare_3d_parser.add_argument("--max-current-points", type=int, default=200_000)
    compare_3d_parser.add_argument("--max-model-points", type=int, default=200_000)

    splat_parser = subparsers.add_parser(
        "pointcloud-to-gaussian-splat",
        help="Convert a point cloud into an experimental 3D Gaussian Splat seed PLY",
    )
    splat_parser.add_argument("--input", type=Path, required=True, help="Input colored PLY point cloud")
    splat_parser.add_argument("--output", type=Path, required=True)
    splat_parser.add_argument("--max-points", type=int, default=250_000)
    splat_parser.add_argument("--splat-scale", type=float, default=0.01)
    splat_parser.add_argument("--opacity", type=float, default=0.65)

    dust3r_parser = subparsers.add_parser(
        "build-dust3r-3d",
        help="Extract video frames and run DUSt3R/MASt3R neural 3D reconstruction (outputs .ply point cloud)",
    )
    dust3r_parser.add_argument("--video", type=Path, required=True, help="Drone video file")
    dust3r_parser.add_argument("--output", type=Path, required=True, help="Output directory")
    dust3r_parser.add_argument(
        "--n-frames",
        type=int,
        default=60,
        help="Number of frames to extract from the video (default 60; use fewer for speed, more for quality)",
    )
    dust3r_parser.add_argument(
        "--image-size",
        type=int,
        default=512,
        help="Resolution fed to the network (default 512; 224/512 are the supported values)",
    )
    dust3r_parser.add_argument(
        "--scene-graph",
        choices=["swin", "complete", "oneref", "pairs"],
        default="swin",
        help="How to form image pairs (default swin; complete is best quality but slow with many frames)",
    )
    dust3r_parser.add_argument(
        "--niter",
        type=int,
        default=300,
        help="Global alignment iterations (default 300; fewer = faster but lower quality)",
    )
    dust3r_parser.add_argument(
        "--start-seconds",
        type=float,
        default=0.0,
        help="Skip this many seconds at the start of the video (default 0)",
    )
    dust3r_parser.add_argument(
        "--end-seconds",
        type=float,
        default=None,
        help="Stop reading the video at this timestamp in seconds (default: full video)",
    )
    dust3r_parser.add_argument(
        "--blur-threshold",
        type=float,
        default=50.0,
        help="Drop frames blurrier than this Laplacian score (default 50; lower if too few frames pass)",
    )
    dust3r_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="HuggingFace model ID to use (default: naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric)",
    )
    dust3r_parser.add_argument(
        "--max-points",
        type=int,
        default=500_000,
        help="Subsample the output point cloud to at most this many points (default 500000)",
    )

    args = parser.parse_args()
    config = _load_config(getattr(args, "config", None))
    if getattr(args, "sample_every", None):
        config = PipelineConfig(
            project_name=config.project_name,
            sample_every_n_frames=args.sample_every,
            blur_threshold=config.blur_threshold,
            motion_threshold=config.motion_threshold,
            target_keyframes=config.target_keyframes,
            sections=config.sections,
            weights=config.weights,
        )

    if args.command == "run-video":
        segmenter, classifier = _build_segmentation_stack(args.segmenter)
        report = run_video_pipeline(
            args.video,
            args.output,
            config,
            segmenter=segmenter,
            classifier=classifier,
            roi_detector=_build_roi_detector(args.roi),
            analysis_max_dimension=args.analysis_max_dimension,
        )
    elif args.command == "run-video-overlay":
        segmenter, _ = _build_segmentation_stack(args.segmenter)
        summary = build_segmentation_overlay_video(
            video_path=args.video,
            output_dir=args.output,
            segmenter=segmenter,
            sample_every_n_frames=args.sample_every,
            max_dimension=args.max_dimension,
            output_fps=args.output_fps,
            max_frames=args.max_frames,
        )
        console.print(f"[green]Overlay video:[/green] {summary['output_video']}")
        console.print(f"[green]Processed frames:[/green] {summary['processed_frames']}")
        console.print(f"[green]Average segments/frame:[/green] {summary['average_segments_per_frame']}")
        console.print(f"[green]Summary:[/green] {args.output / 'overlay_summary.json'}")
        return
    elif args.command == "run-image":
        segmenter, classifier = _build_segmentation_stack(args.segmenter)
        report = run_image_pipeline(
            [args.image],
            args.output,
            config,
            segmenter=segmenter,
            classifier=classifier,
            roi_detector=_build_roi_detector(args.roi),
            analysis_max_dimension=args.analysis_max_dimension,
            inputs={"image": str(args.image)},
        )
    elif args.command == "run-images":
        image_paths = sorted(
            path
            for path in args.images.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        )
        segmenter, classifier = _build_segmentation_stack(args.segmenter)
        report = run_image_pipeline(
            image_paths,
            args.output,
            config,
            segmenter=segmenter,
            classifier=classifier,
            roi_detector=_build_roi_detector(args.roi),
            analysis_max_dimension=args.analysis_max_dimension,
            inputs={"images": str(args.images)},
        )
    elif args.command == "run-roi-batch":
        segmenter, classifier = _build_segmentation_stack(args.segmenter)
        items = run_roi_batch(
            images_dir=args.images,
            output_dir=args.output,
            config=config,
            limit=args.limit,
            segmenter=segmenter,
            classifier=classifier,
            roi_detector=_build_roi_detector(args.roi),
            analysis_max_dimension=args.analysis_max_dimension,
        )
        succeeded = [item for item in items if item.report is not None]
        average = (
            sum(item.report.overall_completion for item in succeeded if item.report)
            / len(succeeded)
            if succeeded
            else 0.0
        )
        console.print(f"[green]Batch succeeded:[/green] {len(succeeded)}/{len(items)}")
        console.print(f"[green]Average completion:[/green] {average:.1%}")
        console.print(f"[green]Summary:[/green] {args.output / 'summary.json'}")
        return
    elif args.command == "build-panorama":
        output_path = args.output
        if output_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            output_path = output_path / "panorama.jpg"
        image_paths = sorted(
            path
            for path in args.images.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        )
        if args.method == "strip":
            build_strip_panorama(
                image_paths,
                output_path,
                max_images=args.max_images,
                max_dimension=args.max_dimension,
            )
        else:
            build_smooth_panorama(image_paths, output_path, max_dimension=args.max_dimension)
        console.print(f"[green]Panorama:[/green] {output_path}")
        return
    elif args.command == "build-video-panorama":
        output_path = args.output
        if output_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            output_path = output_path / "panorama.jpg"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        frames_dir = args.tiles_dir or (output_path.parent / "mosaic_tiles")
        console.print(f"[cyan]Extracting overlapping frames from:[/cyan] {args.video}")
        frame_paths = extract_panorama_frames(
            video_path=args.video,
            output_dir=frames_dir,
            sample_every_n_frames=args.sample_every,
            blur_threshold=args.blur_threshold,
            target_frames=args.n_tiles,
            start_frame=args.start_frame,
        )
        if not frame_paths:
            console.print(
                "[red]No usable frames extracted — lower --blur-threshold or --sample-every and retry.[/red]"
            )
            return
        console.print(f"[cyan]Extracted {len(frame_paths)} frames - stitching panorama...[/cyan]")
        if args.method == "slitscan":
            build_slitscan_panorama(
                image_paths=frame_paths,
                output_path=output_path,
                work_width=args.work_width,
                max_dimension=args.max_dimension,
            )
        else:
            build_drone_panorama(
                image_paths=frame_paths,
                output_path=output_path,
                max_images=len(frame_paths),
                work_width=args.work_width,
                max_dimension=args.max_dimension,
                rotate_cw90=args.rotate,
            )
        console.print(f"[green]Panorama:[/green] {output_path}")
        return
    elif args.command == "build-sparse-3d":
        metrics = build_sparse_point_cloud_from_video(
            video_path=args.video,
            output_dir=args.output,
            frame_a=args.frame_a,
            frame_b=args.frame_b,
            max_dimension=args.max_dimension,
            max_points=args.max_points,
        )
        console.print(f"[green]3D points:[/green] {metrics['points_written']}")
        console.print(f"[green]Point cloud:[/green] {args.output / 'sparse_point_cloud.ply'}")
        console.print(f"[green]Preview:[/green] {args.output / 'pointcloud_preview.jpg'}")
        console.print(f"[green]Metrics:[/green] {args.output / 'metrics.json'}")
        return
    elif args.command == "build-colmap-mesh":
        summary = build_colmap_mesh_from_video(
            video_path=args.video,
            output_dir=args.output,
            colmap_path=args.colmap_path,
            frame_interval_seconds=args.frame_interval,
            start_seconds=args.start_seconds,
            max_frames=args.max_frames,
            blur_threshold=args.blur_threshold,
            max_image_size=args.max_image_size,
            sequential_overlap=args.sequential_overlap,
            matcher=args.matcher,
            run_dense=not args.skip_dense,
        )
        console.print(f"[green]Status:[/green] {summary['status']}")
        console.print(f"[green]Input frames:[/green] {summary['input_frames']}")
        if "registered_images" in summary:
            console.print(f"[green]Registered images:[/green] {summary['registered_images']}")
        if "sparse_points" in summary:
            console.print(f"[green]Sparse points:[/green] {summary['sparse_points']}")
        if "dense_vertices" in summary:
            console.print(f"[green]Dense vertices:[/green] {summary['dense_vertices']}")
        if "mesh_vertices" in summary:
            console.print(f"[green]Mesh vertices:[/green] {summary['mesh_vertices']}")
        if "mesh_faces" in summary:
            console.print(f"[green]Mesh faces:[/green] {summary['mesh_faces']}")
        console.print(f"[green]Summary:[/green] {args.output / 'summary.json'}")
        console.print(f"[green]Mesh target:[/green] {args.output / 'mesh.ply'}")
        return
    elif args.command == "compare-3d-model":
        summary = compare_reconstruction_to_model(
            current_ply=args.current,
            final_model=args.final_model,
            output_dir=args.output,
            max_current_points=args.max_current_points,
            max_model_points=args.max_model_points,
        )
        console.print(f"[green]Median distance:[/green] {summary['distance_median']}")
        console.print(f"[green]P90 distance:[/green] {summary['distance_p90']}")
        console.print(f"[green]Close coverage:[/green] {summary['coverage_close_pct']}%")
        console.print(f"[green]Preview:[/green] {args.output / 'comparison_preview.jpg'}")
        console.print(f"[green]Difference PLY:[/green] {args.output / 'difference_pointcloud.ply'}")
        console.print(f"[green]Summary:[/green] {args.output / 'comparison_summary.json'}")
        return
    elif args.command == "pointcloud-to-gaussian-splat":
        summary = pointcloud_to_gaussian_splat(
            input_ply=args.input,
            output_dir=args.output,
            max_points=args.max_points,
            splat_scale=args.splat_scale,
            opacity=args.opacity,
        )
        console.print(f"[green]Splat points:[/green] {summary['splat_points']}")
        console.print(f"[green]Gaussian Splat seed:[/green] {args.output / 'gaussian_splat_seed.ply'}")
        console.print(f"[green]Preview:[/green] {args.output / 'gaussian_splat_preview.jpg'}")
        console.print(f"[green]Summary:[/green] {args.output / 'gaussian_splat_summary.json'}")
        return
    elif args.command == "build-dust3r-3d":
        summary = build_dust3r_3d_from_video(
            video_path=args.video,
            output_dir=args.output,
            n_frames=args.n_frames,
            image_size=args.image_size,
            scene_graph=args.scene_graph,
            niter=args.niter,
            model_name=args.model,
            start_seconds=args.start_seconds,
            end_seconds=args.end_seconds,
            blur_threshold=args.blur_threshold,
            max_output_points=args.max_points,
        )
        console.print(f"[green]Backend:[/green]         {summary['tool']}")
        console.print(f"[green]Model:[/green]           {summary['model']}")
        console.print(f"[green]Frames used:[/green]     {summary['frames_extracted']}")
        console.print(f"[green]Pairs computed:[/green]  {summary['pairs_computed']}")
        console.print(f"[green]Points written:[/green]  {summary['points_written']:,}")
        console.print(f"[green]Final loss:[/green]      {summary['final_loss']}")
        console.print(f"[green]Point cloud:[/green]     {args.output / 'pointcloud.ply'}")
        console.print(f"[green]Summary:[/green]         {args.output / 'summary.json'}")
        console.print(
            "[cyan]Open pointcloud.ply in MeshLab, CloudCompare, or Blender to view the 3D model.[/cyan]"
        )
        return
    else:
        raise ValueError(f"Unsupported command: {args.command}")

    console.print(f"[green]Overall completion:[/green] {report.overall_completion:.1%}")
    console.print(f"[green]Report:[/green] {args.output / 'report.json'}")
    console.print(f"[green]Annotated image:[/green] {args.output / 'annotated.jpg'}")


def _load_config(path: Path | None) -> PipelineConfig:
    return PipelineConfig.from_json(path) if path else PipelineConfig()


def _build_segmentation_stack(name: str):
    if name == "sam3":
        return Sam3TextPromptSegmenter(), IdentitySegmentClassifier()
    if name == "sam3-progress":
        return (
            Sam3TextPromptSegmenter(
                prompts=SAM3_PROGRESS_PROMPTS,
                min_score=0.25,
                max_segments_per_prompt=6,
                min_area_ratio=0.004,
                nms_iou_threshold=0.45,
            ),
            IdentitySegmentClassifier(),
        )
    if name == "sam3-objects":
        return (
            Sam3TextPromptSegmenter(
                prompts=SAM3_OBJECT_PROMPTS,
                min_score=0.18,
                max_segments_per_prompt=8,
                min_area_ratio=0.0004,
                nms_iou_threshold=0.35,
                source_name="sam3_object_prompt",
            ),
            IdentitySegmentClassifier(),
        )
    if name == "sam2-auto":
        return Sam2AutomaticSegmenter(), IdentitySegmentClassifier()
    return ClassicalSegmenter(), None


def _build_roi_detector(name: str):
    if name == "sam3-construction":
        return Sam3ConstructionRoiDetector()
    return None


if __name__ == "__main__":
    main()
