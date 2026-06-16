"""Check both lengthwise mirror fits of a scan against the bridge model.

Bridges are nearly symmetric along their length, so unsupervised alignment
can settle on either orientation. This script runs ICP from both mirror
candidates, reports their fit quality, and renders an overlay image per
candidate so a human can confirm which orientation is correct.

    python AI/scripts/check_mirror_fit.py \
        --current AI/outputs/mast3r_slam_bridge1_masked_s15/pointcloud_clean.ply \
        --reference Frontend/KCPT_Ki_centered.glb \
        --output AI/outputs/mast3r_slam_bridge1_masked_s15/mirror_fit_check.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import trimesh
from scipy.spatial import cKDTree

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))

from ftp_ai.model_comparison import (  # noqa: E402
    _best_sign_alignment,
    _load_model_points,
    _pca_normalize,
    _trimmed_icp,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Output overlay PNG")
    parser.add_argument("--sample", type=int, default=200_000)
    args = parser.parse_args()

    cloud = trimesh.load(str(args.current), process=False)
    points = np.asarray(cloud.vertices, dtype=np.float64)
    rng = np.random.default_rng(13)
    if len(points) > args.sample:
        points = points[rng.choice(len(points), args.sample, replace=False)]
    model = _load_model_points(trimesh, args.reference, max_model_points=args.sample, seed=13)

    current_norm, _ = _pca_normalize(points)
    model_norm, _ = _pca_normalize(model)
    base, sign_info = _best_sign_alignment(current_norm, model_norm, cKDTree)
    print(f"auto-picked sign flip: {sign_info['sign_flip']} (p75 {sign_info['sample_p75_distance']})")

    tree = cKDTree(model_norm)
    candidates = {
        "A_as_auto_picked": np.array([1.0, 1.0, 1.0]),
        # Mirror the bridge lengthwise; flipping two axes keeps a proper rotation.
        "B_length_mirrored": np.array([-1.0, -1.0, 1.0]),
    }
    fits = {}
    for name, flip in candidates.items():
        aligned, icp = _trimmed_icp(base * flip, model_norm, cKDTree, iterations=40)
        distances, _ = tree.query(aligned[::5], k=1, workers=-1)
        fits[name] = {
            "aligned": aligned,
            "p75": float(np.percentile(distances, 75)),
            "median": float(np.median(distances)),
            "icp_scale": icp["scale_total"],
        }
        print(f"{name}: p75={fits[name]['p75']:.5f} median={fits[name]['median']:.5f} icp_scale={icp['scale_total']}")

    better = min(fits, key=lambda key: fits[key]["p75"])
    margin = abs(fits["A_as_auto_picked"]["p75"] - fits["B_length_mirrored"]["p75"])
    print(f"better fit: {better} (p75 margin {margin:.5f})")
    if margin < 0.003:
        print("WARNING: margin is small; confirm the orientation visually in the overlay image.")

    panel_h, panel_w = 500, 1400
    canvas = np.full((panel_h * 2 + 30, panel_w, 3), 18, np.uint8)
    mn = np.percentile(model_norm[:, :2], 1, axis=0)
    mx = np.percentile(model_norm[:, :2], 99, axis=0)
    span = np.maximum(mx - mn, 1e-9)

    def project(p: np.ndarray, y_offset: int) -> tuple[np.ndarray, np.ndarray]:
        x = np.clip(((p[:, 0] - mn[0]) / span[0] * (panel_w - 20) + 10).astype(int), 0, panel_w - 1)
        y = np.clip(((1 - (p[:, 1] - mn[1]) / span[1]) * (panel_h - 20) + 10 + y_offset).astype(int), y_offset, y_offset + panel_h - 1)
        return x, y

    for index, (name, fit) in enumerate(fits.items()):
        y_offset = index * (panel_h + 30)
        x, y = project(model_norm, y_offset)
        canvas[y, x] = (120, 120, 120)
        x, y = project(fit["aligned"], y_offset)
        canvas[y, x] = (60, 200, 60) if index == 0 else (60, 160, 255)
        label = f"{name}  p75={fit['p75']:.4f}  (grey=model)"
        cv2.putText(canvas, label, (20, y_offset + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), canvas)
    print(f"overlay saved to {args.output}")


if __name__ == "__main__":
    main()
