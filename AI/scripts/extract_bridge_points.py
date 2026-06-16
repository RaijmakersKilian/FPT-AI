"""Extract bridge-only points from a reconstruction using the final model as crop region.

Aligns the current reconstruction to the completed bridge reference (same
PCA + sign-flip + trimmed ICP pipeline as the 3D comparison), then keeps only
the points that lie within a distance threshold of the reference geometry.
Trees, buildings, roads, and water fall outside the threshold and are dropped.
The output keeps the reconstruction's original coordinates and colors.

This mirrors how a production system would scope the scan: the BIM/design
model defines the region of interest.

    python AI/scripts/extract_bridge_points.py \
        --current AI/outputs/mast3r_slam_bridge1_masked_s15/pointcloud_clean.ply \
        --reference AI/data/BridgePointcloud/coverage_result.ply \
        --output AI/outputs/mast3r_slam_bridge1_masked_s15/pointcloud_bridge_only.ply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))

from ftp_ai.model_comparison import (  # noqa: E402
    _best_sign_alignment,
    _load_dependencies,
    _load_model_points,
    _pca_normalize,
    _trimmed_icp,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True, help="Completed bridge model or point cloud (.ply/.glb/.obj)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.04, help="Keep current points within this normalized distance of the reference")
    parser.add_argument("--max-reference-points", type=int, default=200_000)
    parser.add_argument("--remove-vegetation", action="store_true", help="Also drop green points (excess-green + HSV hue test); catches trees the distance crop keeps")
    args = parser.parse_args()

    _, cKDTree = _load_dependencies()

    cloud = trimesh.load(str(args.current), process=False)
    points = np.asarray(cloud.vertices, dtype=np.float64)
    colors = np.asarray(cloud.visual.vertex_colors)[:, :4]
    finite = np.isfinite(points).all(axis=1)
    points, colors = points[finite], colors[finite]
    print(f"loaded {len(points)} current points")

    reference = _load_model_points(trimesh, args.reference, max_model_points=args.max_reference_points, seed=13)
    print(f"loaded {len(reference)} reference points")

    current_norm, _ = _pca_normalize(points)
    reference_norm, _ = _pca_normalize(reference)
    aligned, sign_info = _best_sign_alignment(current_norm, reference_norm, cKDTree)
    aligned, icp_info = _trimmed_icp(aligned, reference_norm, cKDTree)
    print(f"alignment: sign_flip={sign_info['sign_flip']} icp_p75={icp_info['final_sample_p75_distance']}")

    tree = cKDTree(reference_norm)
    distances, _ = tree.query(aligned, k=1, workers=-1)
    keep = distances <= args.threshold

    vegetation_removed = 0
    if args.remove_vegetation:
        vegetation = _vegetation_mask(colors[:, :3])
        vegetation_removed = int((keep & vegetation).sum())
        keep &= ~vegetation
        print(f"vegetation filter removed {vegetation_removed} points")

    bridge = trimesh.PointCloud(points[keep], colors=colors[keep])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bridge.export(str(args.output))

    stats = {
        "current": str(args.current),
        "reference": str(args.reference),
        "output": str(args.output),
        "threshold": args.threshold,
        "points_in": int(len(points)),
        "points_kept": int(keep.sum()),
        "kept_pct": round(float(keep.mean()) * 100.0, 2),
        "vegetation_removed": vegetation_removed,
        "alignment": {"sign_flip": sign_info["sign_flip"], "icp": icp_info},
        "note": "Output is in the reconstruction's original coordinates; the threshold is applied in normalized alignment space.",
    }
    stats_path = args.output.with_suffix(".extract_stats.json")
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


def _vegetation_mask(rgb: np.ndarray) -> np.ndarray:
    """Flag vegetation by color: bright excess-green or saturated green hue.

    The HSV hue test catches dark/shadowed foliage that the excess-green ratio
    misses; the saturation floor keeps grey deck/road points out.
    """
    import cv2

    rgb = rgb.astype(np.uint8)
    red, green, blue = (rgb[:, i].astype(int) for i in range(3))
    excess_green = (green > red * 1.06) & (green > blue * 1.06) & (green > 40)

    hsv = cv2.cvtColor(rgb.reshape(-1, 1, 3), cv2.COLOR_RGB2HSV).reshape(-1, 3).astype(int)
    hue, saturation = hsv[:, 0], hsv[:, 1]
    hsv_green = (hue >= 25) & (hue <= 95) & (saturation >= 50)

    return excess_green | hsv_green


if __name__ == "__main__":
    main()
