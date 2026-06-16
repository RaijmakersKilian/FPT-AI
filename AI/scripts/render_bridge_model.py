"""Software perspective renderer for the bridge 3D model (no OpenGL needed).

EGL/offscreen GL is unavailable on this Windows setup, so this renders the GLB
by densely sampling its surface, projecting the points through a pinhole camera
with a painter's-algorithm depth sort, and splatting small disks. The result is
a clean, background-free render of the planned bridge that can sit next to the
SAM-segmented drone frame for the vision comparison.

    AI/.venv-sam3/Scripts/python.exe AI/scripts/render_bridge_model.py \
        --model Frontend/KCPT_Ki_centered.glb \
        --output AI/outputs/vision_compare/model_render.jpg \
        --azimuth 35 --elevation 28
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
import trimesh


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--samples", type=int, default=500_000)
    parser.add_argument("--azimuth", type=float, default=35.0, help="Camera azimuth in degrees around the bridge")
    parser.add_argument("--elevation", type=float, default=30.0, help="Camera elevation in degrees above the deck")
    parser.add_argument("--color-by", choices=["model", "length", "height"], default="length",
                        help="model=GLB colors, length=rainbow along bridge, height=by elevation")
    parser.add_argument("--point-px", type=int, default=2)
    args = parser.parse_args()

    points, colors = _sample_model(args.model, args.samples)
    points = _orient_long_axis_to_x(points)

    if args.color_by == "length":
        colors = _ramp_colors(points[:, 0])
    elif args.color_by == "height":
        colors = _ramp_colors(points[:, 2])

    image = _render(points, colors, args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), image)
    print(f"rendered {len(points)} points -> {args.output}")


def _sample_model(path: Path, samples: int) -> tuple[np.ndarray, np.ndarray]:
    scene = trimesh.load(str(path), force="scene", process=False)
    meshes = []
    for node_name in scene.graph.nodes_geometry:
        transform, geometry_name = scene.graph[node_name]
        mesh = scene.geometry[geometry_name].copy()
        mesh.apply_transform(transform)
        meshes.append(mesh)
    mesh = trimesh.util.concatenate(meshes)
    sampled, face_index = trimesh.sample.sample_surface(mesh, samples)

    colors = np.full((len(sampled), 3), 200, dtype=np.uint8)
    visual = getattr(mesh, "visual", None)
    try:
        face_colors = mesh.visual.face_colors[:, :3]
        colors = face_colors[face_index]
    except Exception:
        pass
    return np.asarray(sampled, dtype=np.float64), np.asarray(colors, dtype=np.uint8)


def _orient_long_axis_to_x(points: np.ndarray) -> np.ndarray:
    """Rotate so the bridge's longest extent is X and up is Z (PCA on XY)."""
    centered = points - points.mean(axis=0)
    # Longest horizontal axis -> X. Keep the original vertical as Z.
    xy = centered[:, :2]
    cov = np.cov(xy.T)
    values, vectors = np.linalg.eigh(cov)
    long_axis = vectors[:, int(np.argmax(values))]
    angle = np.arctan2(long_axis[1], long_axis[0])
    cos_a, sin_a = np.cos(-angle), np.sin(-angle)
    rotation = np.array([[cos_a, -sin_a, 0], [sin_a, cos_a, 0], [0, 0, 1.0]])
    return centered @ rotation.T


def _ramp_colors(values: np.ndarray) -> np.ndarray:
    norm = (values - values.min()) / max(values.ptp(), 1e-9)
    ramp = (norm * 255).astype(np.uint8)
    return cv2.applyColorMap(ramp.reshape(-1, 1), cv2.COLORMAP_TURBO).reshape(-1, 3)


def _render(points: np.ndarray, colors: np.ndarray, args) -> np.ndarray:
    az = np.radians(args.azimuth)
    el = np.radians(args.elevation)
    extent = points.max(axis=0) - points.min(axis=0)
    radius = float(np.linalg.norm(extent)) * 0.62

    direction = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
    eye = direction * radius
    target = np.zeros(3)
    up = np.array([0.0, 0.0, 1.0])

    forward = target - eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, up)
    right /= np.linalg.norm(right)
    true_up = np.cross(right, forward)

    rel = points - eye
    cam_x = rel @ right
    cam_y = rel @ true_up
    cam_z = rel @ forward
    in_front = cam_z > 1e-6
    cam_x, cam_y, cam_z, colors = cam_x[in_front], cam_y[in_front], cam_z[in_front], colors[in_front]

    focal = args.width * 0.9
    sx = (focal * cam_x / cam_z + args.width / 2).astype(int)
    sy = (-focal * cam_y / cam_z + args.height / 2).astype(int)
    valid = (sx >= 0) & (sx < args.width) & (sy >= 0) & (sy < args.height)
    sx, sy, cam_z, colors = sx[valid], sy[valid], cam_z[valid], colors[valid]

    # Painter's algorithm: draw far points first.
    order = np.argsort(-cam_z)
    sx, sy, cam_z, colors = sx[order], sy[order], cam_z[order], colors[order]

    # Mild depth shading for legibility.
    near, far = np.percentile(cam_z, 2), np.percentile(cam_z, 98)
    shade = np.clip(1.15 - (cam_z - near) / max(far - near, 1e-9) * 0.5, 0.5, 1.15)
    shaded = np.clip(colors.astype(float) * shade[:, None], 0, 255).astype(np.uint8)

    canvas = np.zeros((args.height, args.width, 3), dtype=np.uint8)
    r = args.point_px
    for x, y, color in zip(sx, sy, shaded):
        cv2.circle(canvas, (int(x), int(y)), r, (int(color[0]), int(color[1]), int(color[2])), -1)

    cv2.putText(canvas, "Planned bridge model (BIM/3D) - no background", (15, args.height - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


if __name__ == "__main__":
    main()
