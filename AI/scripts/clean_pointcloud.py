"""Clean reconstruction noise from a point cloud.

Two filters against typical MASt3R-SLAM/photogrammetry artifacts:

1. Statistical outlier removal (SOR): drop points whose mean distance to
   their k nearest neighbors is far above average (floating noise).
2. Density filter: drop points with few neighbors inside a radius. This
   removes thin depth-smear "beams" (poles, tree edges smeared toward the
   camera), which survive SOR because they have close neighbors along the
   smear direction.

    python AI/scripts/clean_pointcloud.py \
        --input AI/outputs/mast3r_slam_bridge1_masked/pointcloud_filtered.ply \
        --output AI/outputs/mast3r_slam_bridge1_masked/pointcloud_clean.ply
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sor-neighbors", type=int, default=16)
    parser.add_argument("--sor-std-ratio", type=float, default=2.0)
    parser.add_argument("--density-radius-factor", type=float, default=6.0, help="Density radius as a multiple of the median nearest-neighbor distance")
    parser.add_argument("--density-min-neighbors", type=int, default=24)
    parser.add_argument("--skip-sor", action="store_true")
    parser.add_argument("--skip-density", action="store_true")
    args = parser.parse_args()

    cloud = trimesh.load(str(args.input), process=False)
    points = np.asarray(cloud.vertices, dtype=np.float64)
    colors = np.asarray(cloud.visual.vertex_colors)[:, :4]
    total = len(points)
    print(f"loaded {total} points")

    keep = np.ones(total, dtype=bool)
    stats: dict[str, object] = {"input": str(args.input), "points_in": total}

    tree = cKDTree(points)
    nn_distances, _ = tree.query(points, k=2, workers=-1)
    median_nn = float(np.median(nn_distances[:, 1]))
    stats["median_nn_distance"] = median_nn
    print(f"median nearest-neighbor distance: {median_nn:.6f}")

    if not args.skip_sor:
        distances, _ = tree.query(points, k=args.sor_neighbors + 1, workers=-1)
        mean_distance = distances[:, 1:].mean(axis=1)
        cutoff = float(mean_distance.mean() + args.sor_std_ratio * mean_distance.std())
        sor_keep = mean_distance <= cutoff
        keep &= sor_keep
        stats["sor"] = {
            "neighbors": args.sor_neighbors,
            "std_ratio": args.sor_std_ratio,
            "cutoff": round(cutoff, 6),
            "removed": int((~sor_keep).sum()),
        }
        print(f"SOR removed {int((~sor_keep).sum())} points")

    if not args.skip_density:
        radius = median_nn * args.density_radius_factor
        counts = tree.query_ball_point(points, r=radius, workers=-1, return_length=True)
        density_keep = counts >= args.density_min_neighbors
        removed_by_density = int((keep & ~density_keep).sum())
        keep &= density_keep
        stats["density"] = {
            "radius": round(radius, 6),
            "min_neighbors": args.density_min_neighbors,
            "removed_additionally": removed_by_density,
        }
        print(f"density filter removed {removed_by_density} additional points")

    cleaned = trimesh.PointCloud(points[keep], colors=colors[keep])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cleaned.export(str(args.output))

    stats["points_out"] = int(keep.sum())
    stats["removed_total"] = int(total - keep.sum())
    stats["removed_pct"] = round(float(total - keep.sum()) / total * 100.0, 2)
    stats["output"] = str(args.output)
    stats_path = args.output.with_suffix(".clean_stats.json")
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
