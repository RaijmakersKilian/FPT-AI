"""Interactive control-point picker for point clouds and models.

Opens an Open3D window. Shift+LeftClick picks a point (a marker appears),
Shift+RightClick removes the last pick. Close the window (or press Q) when
done; the picked 3D coordinates are saved to a JSON file in pick order.

Pick the SAME landmarks in the SAME ORDER on the scan and on the reference
model, e.g. pylon bases, deck section corners, ramp ends. 3 points minimum,
4-6 well-spread points recommended.

    python AI/scripts/pick_control_points.py \
        --input AI/outputs/mast3r_slam_bridge1_masked_s15/pointcloud_clean.ply \
        --output AI/outputs/control_points/scan_points.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import open3d as o3d
import trimesh


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Point cloud (.ply) or model (.glb/.obj); meshes are sampled to points")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON with picked coordinates")
    parser.add_argument("--mesh-samples", type=int, default=400_000, help="Points to sample when the input is a mesh")
    args = parser.parse_args()

    cloud = _load_as_o3d_cloud(args.input, args.mesh_samples)
    print(f"loaded {len(cloud.points)} points from {args.input}")
    print("Shift+LeftClick = pick point, Shift+RightClick = undo, Q/close window = finish")

    visualizer = o3d.visualization.VisualizerWithEditing()
    visualizer.create_window(window_name=f"Pick control points: {args.input.name}", width=1600, height=900)
    visualizer.add_geometry(cloud)
    visualizer.run()
    visualizer.destroy_window()

    indices = visualizer.get_picked_points()
    if not indices:
        print("no points picked, nothing saved")
        return

    points = np.asarray(cloud.points)[indices]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": str(args.input),
        "count": len(indices),
        "points": [[round(float(v), 6) for v in point] for point in points],
    }
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"saved {len(indices)} control points to {args.output}")
    for index, point in enumerate(points, start=1):
        print(f"  {index}: {point.round(3).tolist()}")


def _load_as_o3d_cloud(path: Path, mesh_samples: int) -> o3d.geometry.PointCloud:
    loaded = trimesh.load(str(path), force="scene", process=False)
    meshes = []
    if hasattr(loaded, "geometry") and loaded.geometry:
        for node_name in loaded.graph.nodes_geometry:
            transform, geometry_name = loaded.graph[node_name]
            mesh = loaded.geometry[geometry_name].copy()
            mesh.apply_transform(transform)
            meshes.append(mesh)
    merged = trimesh.util.concatenate(meshes) if len(meshes) > 1 else (meshes[0] if meshes else trimesh.load(str(path), process=False))

    cloud = o3d.geometry.PointCloud()
    if len(getattr(merged, "faces", [])) > 0:
        points, _ = trimesh.sample.sample_surface(merged, mesh_samples)
        cloud.points = o3d.utility.Vector3dVector(np.asarray(points, dtype=np.float64))
        cloud.paint_uniform_color([0.7, 0.7, 0.75])
        return cloud

    cloud.points = o3d.utility.Vector3dVector(np.asarray(merged.vertices, dtype=np.float64))
    colors = getattr(getattr(merged, "visual", None), "vertex_colors", None)
    if colors is not None and len(colors) == len(merged.vertices):
        cloud.colors = o3d.utility.Vector3dVector(np.asarray(colors[:, :3], dtype=np.float64) / 255.0)
    return cloud


if __name__ == "__main__":
    main()
