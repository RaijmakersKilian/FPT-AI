"""Remove near-black points from a reconstructed point cloud.

Frames masked by mask_dynamic_objects.py have their dynamic objects filled
with pure black. MASt3R-SLAM still hallucinates depth for those pixels, which
shows up as black streaks/beams in the point cloud. Because the fill is pure
black, those points are identifiable by color: drop every point whose
brightest color channel is below the threshold.

    python AI/scripts/remove_black_points.py \
        --input AI/outputs/mast3r_slam_bridge1_masked/pointcloud.ply \
        --output AI/outputs/mast3r_slam_bridge1_masked/pointcloud_filtered.ply \
        --threshold 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=int, default=20, help="Drop points whose max RGB channel is below this value")
    args = parser.parse_args()

    cloud = trimesh.load(str(args.input), process=False)
    points = np.asarray(cloud.vertices)
    colors = np.asarray(cloud.visual.vertex_colors)[:, :4]

    max_channel = colors[:, :3].astype(int).max(axis=1)
    keep = max_channel >= args.threshold
    removed = int((~keep).sum())

    filtered = trimesh.PointCloud(points[keep], colors=colors[keep])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    filtered.export(str(args.output))

    stats = {
        "input": str(args.input),
        "output": str(args.output),
        "threshold": args.threshold,
        "points_in": int(len(points)),
        "points_removed": removed,
        "points_out": int(keep.sum()),
        "removed_pct": round(removed / len(points) * 100.0, 2),
    }
    stats_path = args.output.with_suffix(".filter_stats.json")
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
