"""Lift SAM3 2D bridge masks onto a MASt3R-SLAM 3D point cloud.

SAM is a 2D image model -- it cannot segment a 3D point cloud directly. This
script does the next best thing: it projects the fused MASt3R-SLAM cloud back
into each saved keyframe using the SLAM trajectory poses, runs SAM3 bridge-prompt
segmentation on the keyframe images, and votes every 3D point bridge / not-bridge
by the 2D masks it lands in. The result is a semantically isolated bridge-only
point cloud -- the "run SAM on the 3D" experiment.

Why this is needed: MASt3R-SLAM ran with use_calib=False, so it never stored a
pinhole focal length. We recover an approximate focal by rendering the cloud into
each keyframe (painter's z-buffer) and minimising colour error against the real
keyframe image, then reuse that focal for mask lifting.

Inputs we rely on (all already produced by the existing SLAM run):
  - the fused cloud            (pointcloud.ply, per-keyframe pointmaps concatenated)
  - the trajectory             (trajectory.txt, TUM: ts tx ty tz qx qy qz qw,
                                T_WC = camera->world, OpenCV camera frame)
  - the saved keyframe images  (keyframes/<seq>/<ts>.png, named by the SAME ts as
                                the trajectory rows -> exact image<->pose pairing)

Run with the AI/.venv-sam3 environment (SAM3 + open3d + scipy):

    AI/.venv-sam3/Scripts/python.exe AI/scripts/sam_lift_to_pointcloud.py \
        --cloud AI/outputs/mast3r_slam_bridge1_fast/pointcloud.ply \
        --keyframes-dir AI/.external/MASt3R-SLAM/logs/bridge1_fast/keyframes/BridgeVid1-271223 \
        --trajectory AI/outputs/mast3r_slam_bridge1_fast/trajectory.txt \
        --output AI/outputs/sam_lift_bridge1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))

from ftp_ai.models import SegmentLabel  # noqa: E402
from ftp_ai.segmentation import Sam3TextPromptSegmenter  # noqa: E402

# Prompts chosen to KEEP the whole bridge structure (deck + piers + the connecting
# road), not to find small objects. Broad on purpose -- we want the union to cover
# all of the as-built bridge so the rest (trees, water, buildings, sky, ground)
# can be discarded.
DEFAULT_BRIDGE_PROMPTS: list[tuple[SegmentLabel, str]] = [
    (SegmentLabel.UNKNOWN, "bridge"),
    (SegmentLabel.UNKNOWN, "bridge deck"),
    (SegmentLabel.UNKNOWN, "concrete bridge structure"),
    (SegmentLabel.UNKNOWN, "elevated road"),
    (SegmentLabel.UNKNOWN, "bridge pier column"),
]


def parse_trajectory(path: Path) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Return [(timestamp_token, R_WC (3x3), t_WC (3,)), ...] in keyframe order.

    The timestamp token is kept as the raw string so we can match the keyframe
    PNG filename exactly (it was written as f"{ts}.png").
    """
    entries: list[tuple[str, np.ndarray, np.ndarray]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        token = parts[0]
        x, y, z, qx, qy, qz, qw = (float(v) for v in parts[1:8])
        R_WC = Rotation.from_quat([qx, qy, qz, qw]).as_matrix()
        t_WC = np.array([x, y, z], dtype=np.float64)
        entries.append((token, R_WC, t_WC))
    return entries


def project(points: np.ndarray, R_WC: np.ndarray, t_WC: np.ndarray,
            focal: float, cx: float, cy: float):
    """Project world points into a camera. Returns (u, v, z) float arrays.

    Xc = R_WC^T (Xw - t_WC); OpenCV frame (z forward, y down, x right).
    """
    cam = (points - t_WC) @ R_WC  # == (R_WC^T (Xw - t)) per row
    z = cam[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = focal * cam[:, 0] / z + cx
        v = focal * cam[:, 1] / z + cy
    return u, v, z


def painter_render(points, colors, R_WC, t_WC, focal, cx, cy, W, H):
    """Render the cloud into one camera with a painter's algorithm (far->near).

    Returns (rgb_render uint8 HxWx3, depth float HxW with inf where empty,
    covered bool HxW).
    """
    u, v, z = project(points, R_WC, t_WC, focal, cx, cy)
    ui = np.round(u).astype(np.int64)
    vi = np.round(v).astype(np.int64)
    valid = (z > 1e-6) & (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
    ui, vi, zz = ui[valid], vi[valid], z[valid]
    cc = colors[valid]
    order = np.argsort(zz)[::-1]  # far first so nearest overwrites
    pix = vi[order] * W + ui[order]
    render = np.zeros((H * W, 3), dtype=np.uint8)
    depth = np.full(H * W, np.inf, dtype=np.float64)
    render[pix] = cc[order]
    depth[pix] = zz[order]
    covered = np.isfinite(depth)
    return render.reshape(H, W, 3), depth.reshape(H, W), covered.reshape(H, W)


def fit_focal(points, colors, entries, keyframes_dir, W, H, fit_keyframes,
              fit_points, debug_dir):
    """Search for the focal that best reprojects the cloud onto the keyframes."""
    cx, cy = W / 2.0, H / 2.0
    rng = np.random.default_rng(0)
    if len(points) > fit_points:
        sel = rng.choice(len(points), size=fit_points, replace=False)
        pts, cols = points[sel], colors[sel]
    else:
        pts, cols = points, colors

    # evenly spaced subset of keyframes for speed
    idx = np.linspace(0, len(entries) - 1, min(fit_keyframes, len(entries))).astype(int)
    loaded = []
    for i in idx:
        token, R_WC, t_WC = entries[i]
        img = cv2.imread(str(keyframes_dir / f"{token}.png"))
        if img is None:
            continue
        loaded.append((cv2.cvtColor(img, cv2.COLOR_BGR2RGB), R_WC, t_WC))

    def score(focal):
        errs, covs = [], []
        for img, R_WC, t_WC in loaded:
            render, _, covered = painter_render(pts, cols, R_WC, t_WC, focal, cx, cy, W, H)
            if covered.sum() < 0.02 * W * H:
                errs.append(255.0)
                covs.append(0.0)
                continue
            diff = np.abs(render[covered].astype(np.float64) - img[covered].astype(np.float64))
            errs.append(float(diff.mean()))
            covs.append(float(covered.mean()))
        return float(np.mean(errs)), float(np.mean(covs))

    coarse = list(range(150, 901, 25))
    results = {f: score(f) for f in coarse}
    best = min(coarse, key=lambda f: results[f][0])
    fine = [f for f in range(best - 24, best + 25, 6) if f > 0]
    for f in fine:
        if f not in results:
            results[f] = score(f)
    best = min(results, key=lambda f: results[f][0])
    best_err, best_cov = results[best]

    # save render-vs-actual sanity images at the best focal
    debug_dir.mkdir(parents=True, exist_ok=True)
    for j, (img, R_WC, t_WC) in enumerate(loaded[:3]):
        render, _, _ = painter_render(pts, cols, R_WC, t_WC, float(best), cx, cy, W, H)
        side = np.hstack([img, render])
        cv2.imwrite(str(debug_dir / f"focal_check_{j}.png"), cv2.cvtColor(side, cv2.COLOR_RGB2BGR))

    curve = {int(f): round(results[f][0], 3) for f in sorted(results)}
    return float(best), best_err, best_cov, curve


def topdown(points, keep_mask, out_path):
    """PCA top-down scatter: bridge-only (blue) over removed (light grey)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    c = points - points.mean(0)
    # 2 axes of largest spread = the ground plane (top-down)
    _, _, vt = np.linalg.svd(c[np.random.default_rng(0).choice(len(c), min(len(c), 200000), replace=False)], full_matrices=False)
    proj = c @ vt[:2].T
    fig, ax = plt.subplots(1, 2, figsize=(16, 7))
    for a, m, title in ((ax[0], np.ones(len(points), bool), "before (full SLAM cloud)"),
                        (ax[1], keep_mask, "after (SAM bridge-only)")):
        a.scatter(proj[~keep_mask, 0], proj[~keep_mask, 1], s=0.2, c="#dddddd", linewidths=0)
        a.scatter(proj[m & keep_mask, 0], proj[m & keep_mask, 1], s=0.2, c="#1f77b4", linewidths=0)
        a.set_title(title)
        a.set_aspect("equal")
        a.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cloud", type=Path, required=True)
    parser.add_argument("--keyframes-dir", type=Path, required=True)
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--focal", type=float, default=None, help="Skip focal fit and use this value")
    parser.add_argument("--vote-threshold", type=float, default=0.5, help="Fraction of views that must call a point bridge")
    parser.add_argument("--min-views", type=int, default=2, help="Minimum keyframes a point must be visible in to be labelled")
    parser.add_argument("--occlusion-tol", type=float, default=0.06, help="Relative depth tolerance for the visibility z-test")
    parser.add_argument("--min-score", type=float, default=0.3)
    parser.add_argument("--fit-keyframes", type=int, default=8)
    parser.add_argument("--fit-points", type=int, default=300000)
    parser.add_argument("--fit-only", action="store_true", help="Fit focal + write sanity images, then stop (go/no-go gate)")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    debug_dir = args.output / "debug"

    print(f"loading cloud: {args.cloud}")
    pcd = o3d.io.read_point_cloud(str(args.cloud))
    points = np.asarray(pcd.points, dtype=np.float64)
    colors = (np.asarray(pcd.colors) * 255.0).astype(np.uint8)
    print(f"  {len(points):,} points")

    entries = parse_trajectory(args.trajectory)
    print(f"trajectory: {len(entries)} keyframes")

    # image size from the first keyframe
    first_img = cv2.imread(str(args.keyframes_dir / f"{entries[0][0]}.png"))
    if first_img is None:
        raise SystemExit(f"could not read first keyframe for token {entries[0][0]}")
    H, W = first_img.shape[:2]
    cx, cy = W / 2.0, H / 2.0
    print(f"keyframe size: {W}x{H}, principal point ({cx},{cy})")

    if args.focal is None:
        print("fitting focal (z-buffer render vs keyframe colour)...")
        focal, err, cov, curve = fit_focal(
            points, colors, entries, args.keyframes_dir, W, H,
            args.fit_keyframes, args.fit_points, debug_dir)
        print(f"  best focal={focal:.0f}  mean colour error={err:.1f}/255  coverage={cov*100:.1f}%")
        print(f"  -> sanity images in {debug_dir}/focal_check_*.png")
        if args.fit_only:
            (args.output / "focal_fit.json").write_text(
                json.dumps({"focal": focal, "color_error": err, "coverage": cov, "curve": curve}, indent=2),
                encoding="utf-8")
            print("fit-only: stopping before SAM lifting.")
            return
    else:
        focal, err, cov, curve = args.focal, None, None, None
        print(f"using supplied focal={focal}")

    # --- mask lifting ---
    segmenter = Sam3TextPromptSegmenter(
        prompts=DEFAULT_BRIDGE_PROMPTS,
        min_score=args.min_score,
        max_segments_per_prompt=30,
        min_area_ratio=0.0008,
        source_name="sam3_bridge_lift",
    )

    n = len(points)
    views = np.zeros(n, dtype=np.int32)
    bridge_votes = np.zeros(n, dtype=np.int32)
    start = time.time()
    per_frame = []

    for k, (token, R_WC, t_WC) in enumerate(entries):
        img_path = args.keyframes_dir / f"{token}.png"
        if not img_path.exists():
            print(f"  [{k+1}/{len(entries)}] missing {img_path.name}, skip")
            continue

        segments = segmenter.segment(img_path)
        mask = np.zeros((H, W), dtype=bool)
        for seg in segments:
            m = seg.mask
            if m.shape != (H, W):
                m = cv2.resize(m.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST).astype(bool)
            mask |= m

        # project full cloud + painter depth for occlusion
        u, v, z = project(points, R_WC, t_WC, focal, cx, cy)
        ui = np.round(u).astype(np.int64)
        vi = np.round(v).astype(np.int64)
        inb = (z > 1e-6) & (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)

        idx_in = np.nonzero(inb)[0]
        zi = z[idx_in]
        pix = vi[idx_in] * W + ui[idx_in]
        depth = np.full(H * W, np.inf)
        order = np.argsort(zi)[::-1]
        depth[pix[order]] = zi[order]
        nearest = depth[pix]
        visible = zi <= nearest * (1.0 + args.occlusion_tol) + 1e-6

        vis_idx = idx_in[visible]
        views[vis_idx] += 1
        bridge_hit = mask[vi[vis_idx], ui[vis_idx]]
        bridge_votes[vis_idx[bridge_hit]] += 1

        if k % 6 == 0:
            overlay = cv2.cvtColor(cv2.imread(str(img_path)), cv2.COLOR_BGR2RGB)
            tint = overlay.copy()
            tint[mask] = (0.4 * tint[mask] + 0.6 * np.array([31, 119, 180])).astype(np.uint8)
            debug_dir.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(debug_dir / f"mask_{k:02d}.png"),
                        cv2.cvtColor(np.hstack([overlay, tint]), cv2.COLOR_RGB2BGR))

        per_frame.append({
            "keyframe": token,
            "segments": len(segments),
            "bridge_mask_ratio": round(float(mask.mean()), 4),
            "points_visible": int(visible.sum()),
        })
        print(f"  [{k+1}/{len(entries)}] {len(segments)} seg, "
              f"mask {mask.mean()*100:.1f}%, {int(visible.sum()):,} pts visible "
              f"({time.time()-start:.0f}s)", flush=True)

    seen = views >= args.min_views
    ratio = np.zeros(n)
    ratio[seen] = bridge_votes[seen] / views[seen]
    keep = seen & (ratio >= args.vote_threshold)

    print(f"\npoints seen in >= {args.min_views} views: {int(seen.sum()):,}")
    print(f"kept as bridge: {int(keep.sum()):,} ({keep.mean()*100:.1f}% of cloud)")

    bridge = o3d.geometry.PointCloud()
    bridge.points = o3d.utility.Vector3dVector(points[keep])
    bridge.colors = o3d.utility.Vector3dVector(colors[keep] / 255.0)
    out_bridge = args.output / "pointcloud_sam_bridge.ply"
    o3d.io.write_point_cloud(str(out_bridge), bridge)

    removed = o3d.geometry.PointCloud()
    removed.points = o3d.utility.Vector3dVector(points[~keep])
    removed.colors = o3d.utility.Vector3dVector(colors[~keep] / 255.0)
    o3d.io.write_point_cloud(str(args.output / "pointcloud_removed.ply"), removed)

    print("rendering top-down before/after...")
    topdown(points, keep, args.output / "topdown_before_after.png")

    summary = {
        "cloud": str(args.cloud),
        "points_total": n,
        "keyframes": len(entries),
        "image_size": [W, H],
        "focal_fitted": focal,
        "focal_fit_color_error": err,
        "focal_fit_coverage": cov,
        "focal_curve": curve,
        "vote_threshold": args.vote_threshold,
        "min_views": args.min_views,
        "occlusion_tol": args.occlusion_tol,
        "points_seen": int(seen.sum()),
        "points_kept_bridge": int(keep.sum()),
        "kept_fraction": round(float(keep.mean()), 4),
        "per_frame": per_frame,
    }
    (args.output / "sam_lift_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"done -> {out_bridge}")
    print(f"summary -> {args.output / 'sam_lift_summary.json'}")


if __name__ == "__main__":
    main()
