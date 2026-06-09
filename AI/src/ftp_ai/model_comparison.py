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
) -> dict[str, object]:
    """Compare an as-built reconstruction with a completed bridge model.

    This is an exploratory, scale-free comparison. It uses PCA normalization and
    a nearest-neighbor distance field, so the result is useful for correlation
    testing, not final BIM-grade progress measurement.
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

    current_norm, current_transform = _pca_normalize(current_points)
    model_norm, model_transform = _pca_normalize(model_points)

    current_aligned, alignment_info = _best_sign_alignment(current_norm, model_norm, cKDTree)
    tree = cKDTree(model_norm)
    distances, _ = tree.query(current_aligned, k=1, workers=-1)

    thresholds = {
        "close": 0.04,
        "medium": 0.08,
        "far": 0.14,
    }
    diff_colors = _distance_colors(distances, thresholds)

    diff_ply = output_dir / "difference_pointcloud.ply"
    model_ply = output_dir / "normalized_final_model_points.ply"
    preview = output_dir / "comparison_preview.jpg"
    summary_path = output_dir / "comparison_summary.json"

    _write_ascii_ply(diff_ply, current_aligned, diff_colors)
    _write_ascii_ply(model_ply, model_norm, np.tile(np.array([[170, 170, 170]], dtype=np.uint8), (len(model_norm), 1)))
    _write_preview(preview, current_aligned, model_norm, diff_colors)

    summary: dict[str, object] = {
        "status": "experimental",
        "method": "PCA normalized nearest-neighbor 3D comparison",
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
        "alignment": alignment_info,
        "outputs": {
            "difference_pointcloud": str(diff_ply),
            "normalized_final_model_points": str(model_ply),
            "preview": str(preview),
            "summary": str(summary_path),
        },
        "limitations": [
            "Scale and coordinates are normalized, not survey/BIM accurate.",
            "PCA alignment can flip or simplify geometry for long bridge-like shapes.",
            "Background points from trees, roads, cars, and buildings can increase distance.",
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
    return np.asarray(mesh.vertices, dtype=np.float64)


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
    }


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
) -> None:
    try:
        import cv2  # type: ignore
    except ImportError:
        return

    canvas = np.full((1100, 1600, 3), 18, dtype=np.uint8)
    all_xy = np.vstack([current[:, :2], model[:, :2]])
    mn = np.percentile(all_xy, 1, axis=0)
    mx = np.percentile(all_xy, 99, axis=0)
    span = np.maximum(mx - mn, 1e-9)

    def project(points: np.ndarray) -> np.ndarray:
        norm = (points[:, :2] - mn) / span
        x = np.clip((norm[:, 0] * 1500 + 50).astype(int), 0, 1599)
        y = np.clip(((1.0 - norm[:, 1]) * 1000 + 50).astype(int), 0, 1099)
        return np.column_stack([x, y])

    model_xy = project(model)
    current_xy = project(current)
    for x, y in model_xy[:: max(1, len(model_xy) // 80_000)]:
        canvas[int(y), int(x)] = (90, 90, 90)
    for (x, y), color in zip(current_xy, current_colors[:, ::-1]):
        canvas[int(y), int(x)] = color

    cv2.putText(
        canvas,
        "3D comparison preview: final model in grey, current reconstruction colored by distance",
        (35, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (230, 230, 230),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(canvas, "green=close  yellow/orange=some difference  red=far/noisy", (35, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (230, 230, 230), 2, cv2.LINE_AA)
    cv2.imwrite(str(path), canvas)
