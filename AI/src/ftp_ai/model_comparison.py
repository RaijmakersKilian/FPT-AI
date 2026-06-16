from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np


def compare_reconstruction_to_model(
    current_ply: Path,
    final_model: Path,
    output_dir: Path,
    max_current_points: int = 200_000,
    max_model_points: int = 200_000,
    seed: int = 13,
    sections: int = 10,
    icp_iterations: int = 40,
    built_threshold: float = 0.04,
    control_points_current: Path | None = None,
    control_points_reference: Path | None = None,
    anchor_current: Path | None = None,
    anchor_reference: Path | None = None,
) -> dict[str, object]:
    """Compare an as-built reconstruction with a completed bridge model.

    Pipeline:

    1. PCA-normalize both clouds and pick the best axis sign flips (coarse).
    2. Refine the alignment with a trimmed, scale-aware ICP that ignores the
       worst-matching points so trees/traffic/background hurt less.
    3. Measure current->model distances (how noisy is the scan).
    4. Measure model->current distances (which planned geometry already has
       as-built evidence) - this is the progress signal.
    5. Slice the final model along its longest axis and report per-section
       coverage instead of one global percentage.

    Scale and coordinates remain normalized, so the result is a feasibility
    measurement, not survey/BIM-grade progress.
    """

    trimesh, cKDTree = _load_dependencies()
    output_dir.mkdir(parents=True, exist_ok=True)

    current_points, current_colors = _load_point_cloud(trimesh, current_ply)
    model_points = _load_model_points(trimesh, final_model, max_model_points=max_model_points, seed=seed)

    current_points, current_colors = _sample_points(
        current_points,
        current_colors,
        max_points=max_current_points,
        seed=seed,
    )

    model_norm, model_transform = _pca_normalize(model_points)

    if control_points_current is not None and control_points_reference is not None:
        # Calibrated path: the user-picked landmark pairs define the transform
        # into the reference frame; PCA/sign-flip guessing is skipped and ICP
        # may only refine without rescaling.
        current_in_ref, alignment_info = _control_point_alignment(
            current_points,
            control_points_current,
            control_points_reference,
        )
        current_aligned = _apply_normalization(current_in_ref, model_transform)
        current_aligned, icp_info = _trimmed_icp(
            current_aligned,
            model_norm,
            cKDTree,
            iterations=icp_iterations,
            allow_scale=False,
        )
    elif anchor_current is not None and anchor_reference is not None:
        # Anchor path: one rough click near the same bridge end in both clouds
        # resolves the lengthwise mirror ambiguity that geometry cannot.
        current_aligned, alignment_info, icp_info = _anchor_disambiguated_alignment(
            current_points,
            model_norm,
            model_transform,
            anchor_current,
            anchor_reference,
            cKDTree,
            icp_iterations,
        )
    else:
        current_norm, current_transform = _pca_normalize(current_points)
        current_aligned, alignment_info = _best_sign_alignment(current_norm, model_norm, cKDTree)
        current_aligned, icp_info = _trimmed_icp(
            current_aligned,
            model_norm,
            cKDTree,
            iterations=icp_iterations,
        )
    alignment_info["icp"] = icp_info

    tree = cKDTree(model_norm)
    distances, _ = tree.query(current_aligned, k=1, workers=-1)

    thresholds = {
        "close": 0.04,
        "medium": 0.08,
        "far": 0.14,
    }
    diff_colors = _distance_colors(distances, thresholds)

    # Progress direction: which final-model points have nearby as-built points.
    current_tree = cKDTree(current_aligned)
    model_distances, _ = current_tree.query(model_norm, k=1, workers=-1)
    built_mask = model_distances <= built_threshold
    section_report = _per_section_progress(model_norm, model_distances, built_threshold, sections)

    diff_ply = output_dir / "difference_pointcloud.ply"
    model_ply = output_dir / "normalized_final_model_points.ply"
    coverage_ply = output_dir / "model_coverage_pointcloud.ply"
    preview = output_dir / "comparison_preview.jpg"
    summary_path = output_dir / "comparison_summary.json"

    coverage_colors = np.where(
        built_mask[:, None],
        np.array([[40, 220, 80]], dtype=np.uint8),
        np.array([[230, 40, 40]], dtype=np.uint8),
    ).astype(np.uint8)

    _write_ascii_ply(diff_ply, current_aligned, diff_colors)
    _write_ascii_ply(model_ply, model_norm, np.tile(np.array([[170, 170, 170]], dtype=np.uint8), (len(model_norm), 1)))
    _write_ascii_ply(coverage_ply, model_norm, coverage_colors)
    _write_preview(preview, current_aligned, model_norm, diff_colors, coverage_colors, section_report)

    summary: dict[str, object] = {
        "status": "experimental",
        "method": "PCA + sign flip + trimmed scaled ICP, two-direction nearest-neighbor 3D comparison",
        "current_ply": str(current_ply),
        "final_model": str(final_model),
        "current_points_used": int(len(current_aligned)),
        "model_points_used": int(len(model_norm)),
        "distance_units": "normalized_scene_units",
        "distance_mean": round(float(np.mean(distances)), 5),
        "distance_median": round(float(np.median(distances)), 5),
        "distance_p75": round(float(np.percentile(distances, 75)), 5),
        "distance_p90": round(float(np.percentile(distances, 90)), 5),
        "distance_p95": round(float(np.percentile(distances, 95)), 5),
        "coverage_close_pct": round(float(np.mean(distances <= thresholds["close"]) * 100.0), 2),
        "coverage_medium_pct": round(float(np.mean(distances <= thresholds["medium"]) * 100.0), 2),
        "coverage_far_pct": round(float(np.mean(distances <= thresholds["far"]) * 100.0), 2),
        "likely_non_bridge_current_pct": round(float(np.mean(distances > thresholds["far"]) * 100.0), 2),
        "progress_estimate": {
            "direction": "final_model_to_current",
            "built_threshold": built_threshold,
            "model_built_pct": round(float(np.mean(built_mask) * 100.0), 2),
            "model_built_pct_strict": round(float(np.mean(model_distances <= built_threshold / 2.0) * 100.0), 2),
            "model_built_pct_loose": round(float(np.mean(model_distances <= built_threshold * 2.0) * 100.0), 2),
            "model_distance_median": round(float(np.median(model_distances)), 5),
            "per_section": section_report,
        },
        "alignment": alignment_info,
        "outputs": {
            "difference_pointcloud": str(diff_ply),
            "normalized_final_model_points": str(model_ply),
            "model_coverage_pointcloud": str(coverage_ply),
            "preview": str(preview),
            "summary": str(summary_path),
        },
        "limitations": [
            "Scale and coordinates are normalized, not survey/BIM accurate.",
            "PCA + ICP alignment is unsupervised; without control points it can settle on a wrong fit.",
            "Background points from trees, roads, cars, and buildings can increase distance.",
            "Per-section percentages depend on alignment quality; treat them as relative, not absolute progress.",
            "This tests whether comparison is feasible; final progress tracking needs calibrated alignment or control points.",
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _load_dependencies():
    try:
        import trimesh  # type: ignore
        from scipy.spatial import cKDTree  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install optional comparison dependencies: pip install trimesh scipy") from exc
    return trimesh, cKDTree


def _load_point_cloud(trimesh, path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    loaded = trimesh.load(str(path), process=False)
    if hasattr(loaded, "vertices"):
        points = np.asarray(loaded.vertices, dtype=np.float64)
        colors = getattr(getattr(loaded, "visual", None), "vertex_colors", None)
        if colors is not None:
            colors = np.asarray(colors[:, :3], dtype=np.uint8)
        return points, colors
    raise ValueError(f"Could not load point cloud vertices from {path}")


def _load_model_points(trimesh, path: Path, max_model_points: int, seed: int) -> np.ndarray:
    loaded = trimesh.load(str(path), force="scene", process=False)
    meshes = []
    if hasattr(loaded, "geometry"):
        for node_name in loaded.graph.nodes_geometry:
            transform, geometry_name = loaded.graph[node_name]
            mesh = loaded.geometry[geometry_name].copy()
            mesh.apply_transform(transform)
            meshes.append(mesh)
    elif hasattr(loaded, "vertices"):
        meshes.append(loaded)

    if not meshes:
        raise ValueError(f"No mesh geometry found in {path}")

    mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    if len(getattr(mesh, "faces", [])) > 0:
        count = min(max_model_points, max(10_000, len(mesh.vertices) * 10))
        points, _ = trimesh.sample.sample_surface(mesh, count)
        return np.asarray(points, dtype=np.float64)

    points = np.asarray(mesh.vertices, dtype=np.float64)
    if len(points) > max_model_points:
        rng = np.random.default_rng(seed)
        points = points[rng.choice(len(points), size=max_model_points, replace=False)]
    return points


def _sample_points(
    points: np.ndarray,
    colors: np.ndarray | None,
    max_points: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray | None]:
    finite = np.isfinite(points).all(axis=1)
    points = points[finite]
    if colors is not None and len(colors) == len(finite):
        colors = colors[finite]

    if len(points) <= max_points:
        return points, colors

    rng = np.random.default_rng(seed)
    indices = rng.choice(len(points), size=max_points, replace=False)
    sampled_colors = colors[indices] if colors is not None else None
    return points[indices], sampled_colors


def _pca_normalize(points: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    center = np.median(points, axis=0)
    centered = points - center
    covariance = np.cov(centered.T)
    values, vectors = np.linalg.eigh(covariance)
    order = np.argsort(values)[::-1]
    vectors = vectors[:, order]
    values = values[order]
    rotated = centered @ vectors
    scale = float(np.percentile(np.linalg.norm(rotated, axis=1), 95))
    scale = max(scale, 1e-9)
    normalized = rotated / scale
    return normalized, {
        "center": [round(float(value), 6) for value in center],
        "scale_p95_radius": round(scale, 6),
        "eigenvalues": [round(float(value), 6) for value in values],
        "_vectors": vectors,
        "_center": center,
        "_scale": scale,
    }


def _apply_normalization(points: np.ndarray, transform: dict[str, object]) -> np.ndarray:
    """Map raw-frame points into the normalized frame of a _pca_normalize call."""
    return ((points - transform["_center"]) @ transform["_vectors"]) / transform["_scale"]


def _control_point_alignment(
    points: np.ndarray,
    control_points_current: Path,
    control_points_reference: Path,
) -> tuple[np.ndarray, dict[str, object]]:
    """Transform points into the reference frame using picked landmark pairs."""
    source = _load_control_points(control_points_current)
    target = _load_control_points(control_points_reference)
    if len(source) != len(target):
        raise ValueError(
            f"Control point counts differ: {len(source)} in {control_points_current} "
            f"vs {len(target)} in {control_points_reference}. Pick the same landmarks in the same order."
        )
    if len(source) < 3:
        raise ValueError("At least 3 control point pairs are required.")

    scale, rotation, translation = _umeyama_similarity(source, target)
    fitted = (scale * (rotation @ source.T)).T + translation
    residuals = np.linalg.norm(fitted - target, axis=1)
    transformed = (scale * (rotation @ points.T)).T + translation
    return transformed, {
        "method": "control_points",
        "pairs": len(source),
        "scale": round(scale, 6),
        "rms_error": round(float(np.sqrt(np.mean(residuals**2))), 4),
        "max_error": round(float(residuals.max()), 4),
        "per_point_error": [round(float(value), 4) for value in residuals],
    }


def _anchor_disambiguated_alignment(
    current_points: np.ndarray,
    model_norm: np.ndarray,
    model_transform: dict[str, object],
    anchor_current: Path,
    anchor_reference: Path,
    cKDTree,
    icp_iterations: int,
) -> tuple[np.ndarray, dict[str, object], dict[str, object]]:
    """Align with PCA + ICP, using one rough anchor pair to pick the mirror.

    The anchor point rides along through the whole alignment as an extra row
    of the current cloud, so no separate transform bookkeeping is needed.
    """
    anchor_cur = _load_control_points(anchor_current)[:1]
    anchor_ref = _load_control_points(anchor_reference)[:1]
    anchor_ref_norm = _apply_normalization(anchor_ref, model_transform)[0]

    extended = np.vstack([current_points, anchor_cur])
    extended_norm, _ = _pca_normalize(extended)
    base, sign_info = _best_sign_alignment(extended_norm, model_norm, cKDTree)

    candidates = []
    for label, flip in (("as_picked", np.array([1.0, 1.0, 1.0])), ("length_mirrored", np.array([-1.0, -1.0, 1.0]))):
        aligned_ext, icp_info = _trimmed_icp(base * flip, model_norm, cKDTree, iterations=icp_iterations)
        anchor_distance = float(np.linalg.norm(aligned_ext[-1] - anchor_ref_norm))
        candidates.append((anchor_distance, label, aligned_ext, icp_info))

    candidates.sort(key=lambda item: item[0])
    best_distance, best_label, best_aligned_ext, best_icp = candidates[0]
    info = {
        "method": "anchor_disambiguated",
        "base_sign_flip": sign_info["sign_flip"],
        "chosen_mirror": best_label,
        "anchor_distance_chosen": round(best_distance, 5),
        "anchor_distance_rejected": round(candidates[1][0], 5),
    }
    if best_distance >= candidates[1][0] * 0.8:
        info["warning"] = "Anchor distances are close; the anchor may be near the bridge center. Pick a point closer to one end."
    return best_aligned_ext[:-1], info, best_icp


def _load_control_points(path: Path) -> np.ndarray:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    points = np.asarray(payload["points"], dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError(f"{path} does not contain an Nx3 'points' list")
    return points


def _best_sign_alignment(current: np.ndarray, model: np.ndarray, cKDTree) -> tuple[np.ndarray, dict[str, object]]:
    tree = cKDTree(model)
    best_points = current
    best_signs = (1, 1, 1)
    best_score = float("inf")
    sample = current
    if len(sample) > 30_000:
        rng = np.random.default_rng(7)
        sample = sample[rng.choice(len(sample), size=30_000, replace=False)]

    for signs in itertools.product((-1, 1), repeat=3):
        signed = sample * np.array(signs)
        distances, _ = tree.query(signed, k=1, workers=-1)
        score = float(np.percentile(distances, 75))
        if score < best_score:
            best_score = score
            best_signs = signs

    best_points = current * np.array(best_signs)
    return best_points, {
        "sign_flip": list(best_signs),
        "sample_p75_distance": round(best_score, 5),
    }


def _umeyama_similarity(src: np.ndarray, dst: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    mu_src = src.mean(axis=0)
    mu_dst = dst.mean(axis=0)
    src_centered = src - mu_src
    dst_centered = dst - mu_dst
    covariance = dst_centered.T @ src_centered / len(src)
    u, singular, vt = np.linalg.svd(covariance)
    reflection_fix = np.eye(3)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        reflection_fix[2, 2] = -1.0
    rotation = u @ reflection_fix @ vt
    src_variance = float((src_centered ** 2).sum() / len(src))
    scale = float((singular * np.diag(reflection_fix)).sum() / max(src_variance, 1e-12))
    translation = mu_dst - scale * rotation @ mu_src
    return scale, rotation, translation


def _trimmed_icp(
    current: np.ndarray,
    model: np.ndarray,
    cKDTree,
    iterations: int = 40,
    trim_pct: float = 70.0,
    sample_size: int = 40_000,
    seed: int = 7,
    allow_scale: bool = True,
) -> tuple[np.ndarray, dict[str, object]]:
    """Refine alignment with a similarity-transform ICP on the best-matching points.

    Only the closest `trim_pct` percent of correspondences drive each update, so
    trees, traffic, and background points do not dominate the fit. The
    per-iteration scale is clamped to avoid the cloud collapsing onto a dense
    model region.
    """

    tree = cKDTree(model)
    rng = np.random.default_rng(seed)
    if len(current) > sample_size:
        sample = current[rng.choice(len(current), size=sample_size, replace=False)]
    else:
        sample = current.copy()

    scale_total = 1.0
    rotation_total = np.eye(3)
    translation_total = np.zeros(3)
    previous_error: float | None = None
    iterations_run = 0

    for _ in range(max(0, iterations)):
        distances, indices = tree.query(sample, k=1, workers=-1)
        cutoff = float(np.percentile(distances, trim_pct))
        keep = distances <= cutoff
        if int(keep.sum()) < 100:
            break

        scale, rotation, translation = _umeyama_similarity(sample[keep], model[indices[keep]])
        if not allow_scale:
            scale = 1.0
        scale = float(np.clip(scale, 0.95, 1.05))
        if not (0.5 <= scale_total * scale <= 2.0):
            scale = 1.0

        sample = (scale * (rotation @ sample.T)).T + translation
        rotation_total = rotation @ rotation_total
        translation_total = scale * rotation @ translation_total + translation
        scale_total *= scale
        iterations_run += 1

        error = float(np.mean(distances[keep]))
        if previous_error is not None and abs(previous_error - error) < 1e-6:
            break
        previous_error = error

    aligned = (scale_total * (rotation_total @ current.T)).T + translation_total
    final_distances, _ = tree.query(
        aligned if len(aligned) <= sample_size else aligned[rng.choice(len(aligned), size=sample_size, replace=False)],
        k=1,
        workers=-1,
    )
    return aligned, {
        "iterations_run": iterations_run,
        "trim_pct": trim_pct,
        "scale_total": round(scale_total, 6),
        "final_sample_p75_distance": round(float(np.percentile(final_distances, 75)), 5),
    }


def _per_section_progress(
    model_norm: np.ndarray,
    model_distances: np.ndarray,
    built_threshold: float,
    sections: int,
) -> list[dict[str, object]]:
    """Report coverage per slice along the model's longest (first PCA) axis."""

    sections = max(1, sections)
    axis_values = model_norm[:, 0]
    edges = np.linspace(float(axis_values.min()), float(axis_values.max()), sections + 1)
    edges[-1] += 1e-9

    report: list[dict[str, object]] = []
    for index in range(sections):
        in_section = (axis_values >= edges[index]) & (axis_values < edges[index + 1])
        count = int(in_section.sum())
        if count == 0:
            built_pct = 0.0
            median_distance = None
        else:
            built_pct = round(float(np.mean(model_distances[in_section] <= built_threshold) * 100.0), 2)
            median_distance = round(float(np.median(model_distances[in_section])), 5)
        report.append(
            {
                "section": index + 1,
                "axis_range": [round(float(edges[index]), 4), round(float(edges[index + 1]), 4)],
                "model_points": count,
                "built_pct": built_pct,
                "model_distance_median": median_distance,
            }
        )
    return report


def _distance_colors(distances: np.ndarray, thresholds: dict[str, float]) -> np.ndarray:
    colors = np.zeros((len(distances), 3), dtype=np.uint8)
    colors[distances <= thresholds["close"]] = (40, 220, 80)
    medium = (distances > thresholds["close"]) & (distances <= thresholds["medium"])
    colors[medium] = (240, 220, 40)
    far = (distances > thresholds["medium"]) & (distances <= thresholds["far"])
    colors[far] = (255, 140, 20)
    colors[distances > thresholds["far"]] = (230, 40, 40)
    return colors


def _write_ascii_ply(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
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


def _write_preview(
    path: Path,
    current: np.ndarray,
    model: np.ndarray,
    current_colors: np.ndarray,
    model_coverage_colors: np.ndarray,
    section_report: list[dict[str, object]],
) -> None:
    try:
        import cv2  # type: ignore
    except ImportError:
        return

    panel_height = 1100
    panel_width = 1600
    canvas = np.full((panel_height * 2 + 60, panel_width, 3), 18, dtype=np.uint8)

    all_xy = np.vstack([current[:, :2], model[:, :2]])
    mn = np.percentile(all_xy, 1, axis=0)
    mx = np.percentile(all_xy, 99, axis=0)
    span = np.maximum(mx - mn, 1e-9)

    def project(points: np.ndarray, y_offset: int) -> np.ndarray:
        norm = (points[:, :2] - mn) / span
        x = np.clip((norm[:, 0] * (panel_width - 100) + 50).astype(int), 0, panel_width - 1)
        y = np.clip(((1.0 - norm[:, 1]) * (panel_height - 100) + 50 + y_offset).astype(int), y_offset, y_offset + panel_height - 1)
        return np.column_stack([x, y])

    model_xy = project(model, 0)
    current_xy = project(current, 0)
    for x, y in model_xy[:: max(1, len(model_xy) // 80_000)]:
        canvas[int(y), int(x)] = (90, 90, 90)
    for (x, y), color in zip(current_xy, current_colors[:, ::-1]):
        canvas[int(y), int(x)] = color

    cv2.putText(
        canvas,
        "3D comparison: final model in grey, current reconstruction colored by distance",
        (35, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (230, 230, 230),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(canvas, "green=close  yellow/orange=some difference  red=far/noisy", (35, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (230, 230, 230), 2, cv2.LINE_AA)

    coverage_offset = panel_height + 60
    coverage_xy = project(model, coverage_offset)
    for (x, y), color in zip(coverage_xy, model_coverage_colors[:, ::-1]):
        canvas[int(y), int(x)] = color

    cv2.putText(
        canvas,
        "Progress view: final model points, green=as-built evidence found, red=missing",
        (35, coverage_offset + 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (230, 230, 230),
        2,
        cv2.LINE_AA,
    )

    if section_report:
        label_y = coverage_offset + 82
        labels = "  ".join(f"S{entry['section']}:{entry['built_pct']}%" for entry in section_report)
        cv2.putText(canvas, f"per-section built: {labels}", (35, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 1, cv2.LINE_AA)

    cv2.imwrite(str(path), canvas)
