#!/usr/bin/env python3
"""
Straighten and level a curved IFC bridge point cloud.

Two focused steps:
  1. Unbend  – detect the curved horizontal centreline, remap every point
               so arc-length becomes the X axis (bridge lies along X).
  2. De-slope – fit and remove the longitudinal height gradient (bridge
               going uphill from one end to the other) so the deck
               is flat when viewed from the side.

Usage
-----
    python straighten_ifc.py
    python straighten_ifc.py --input ifc_cloud.ply --output ifc_straight.ply
    python straighten_ifc.py --slices 80 --degree 3 --no-view
"""

import argparse
import sys
import numpy as np


def load_cloud(path):
    import open3d as o3d
    pcd = o3d.io.read_point_cloud(path)
    if not pcd or len(pcd.points) == 0:
        print(f"[ERROR] Cannot load '{path}'")
        sys.exit(1)
    pts = np.asarray(pcd.points).copy()
    span = pts.max(axis=0) - pts.min(axis=0)
    print(f"Loaded {len(pts):,} points  X={span[0]:.2f}m  Y={span[1]:.2f}m  Z={span[2]:.2f}m")
    return pcd, pts


# ── Step 1: fit a spline through the bridge centreline ─────────────────────────

def fit_spine(pts, n_slices, degree):
    """
    1. PCA in XY only to find the main horizontal direction.
    2. Slice the cloud along that direction.
    3. Take the XY median of each slice -> spine control points.
    4. Fit a smoothed parametric spline through those points.
    """
    from scipy.interpolate import splprep, UnivariateSpline

    xy        = pts[:, :2]
    center_xy = xy.mean(axis=0)
    cov       = np.cov((xy - center_xy).T)
    _, eigvecs = np.linalg.eigh(cov)
    main_axis  = eigvecs[:, 1]   # largest eigenvalue (index 1 after ascending sort)

    proj  = (xy - center_xy) @ main_axis
    edges = np.linspace(proj.min(), proj.max(), n_slices + 1)

    spine_xy, spine_z = [], []
    for i in range(n_slices):
        mask = (proj >= edges[i]) & (proj < edges[i + 1])
        if mask.sum() < 3:
            continue
        # Median avoids bias from arch tops / pier bottoms
        c = np.median(pts[mask], axis=0)
        spine_xy.append(c[:2])
        spine_z.append(c[2])

    spine_xy = np.array(spine_xy)
    spine_z  = np.array(spine_z)
    K        = len(spine_xy)
    print(f"  Spine: {K} centroids, degree={degree}")

    t = np.linspace(0.0, 1.0, K)
    k = min(degree, K - 1)

    tck_xy, _ = splprep([spine_xy[:, 0], spine_xy[:, 1]],
                         u=t, k=k, s=K * 0.3)
    spl_z = UnivariateSpline(t, spine_z, k=min(3, K - 1), s=K * 0.3)
    return tck_xy, spl_z


def spine_samples(tck_xy, spl_z, n=6000):
    from scipy.interpolate import splev
    t_fine  = np.linspace(0.0, 1.0, n)
    xy_fine = np.array(splev(t_fine, tck_xy)).T
    z_fine  = spl_z(t_fine)
    arc     = np.concatenate([[0.0],
                               np.cumsum(np.linalg.norm(np.diff(xy_fine, axis=0), axis=1))])
    return t_fine, xy_fine, z_fine, arc


# ── Step 2: remap every point to arc-length coordinates ───────────────────────

def unbend(pts, xy_fine, z_fine, arc):
    """
    new_x = arc-length to the nearest spine point   (0 .. bridge length)
    new_y = signed lateral offset from the spine     (cross-bridge)
    new_z = point Z minus spine Z at that location  (height above deck CL)
    """
    from scipy.spatial import KDTree

    tree = KDTree(xy_fine)
    print(f"  KD-tree query for {len(pts):,} points ...")
    _, idxs = tree.query(pts[:, :2])

    new_x = arc[idxs]

    eps      = 2
    idx_next = np.clip(idxs + eps, 0, len(xy_fine) - 1)
    idx_prev = np.clip(idxs - eps, 0, len(xy_fine) - 1)
    tang     = xy_fine[idx_next] - xy_fine[idx_prev]
    nlen     = np.linalg.norm(tang, axis=1, keepdims=True)
    tang    /= np.where(nlen < 1e-9, 1.0, nlen)

    # 90 deg CCW normal in XY
    norm_vec = np.stack([-tang[:, 1], tang[:, 0]], axis=1)
    new_y    = ((pts[:, :2] - xy_fine[idxs]) * norm_vec).sum(axis=1)
    new_z    = pts[:, 2] - z_fine[idxs]

    return np.stack([new_x, new_y, new_z], axis=1)


# ── Step 3: remove the longitudinal slope ─────────────────────────────────────

def flatten_to_deck(pts, tolerance, n_slices=80):
    """
    For each X slice find the dominant deck surface Z (histogram peak),
    then keep only points within +/- tolerance metres of that level.
    This removes arch humps above and pier foundations below.
    """
    x_all = pts[:, 0]
    edges = np.linspace(x_all.min(), x_all.max(), n_slices + 1)

    keep = np.zeros(len(pts), dtype=bool)
    for i in range(n_slices):
        mask = (x_all >= edges[i]) & (x_all < edges[i + 1])
        if mask.sum() < 5:
            continue
        z_slice = pts[mask, 2]
        # Histogram peak = dominant surface (the deck)
        counts, bin_edges = np.histogram(z_slice, bins=40)
        deck_z = (bin_edges[counts.argmax()] + bin_edges[counts.argmax() + 1]) / 2
        keep[mask] = np.abs(z_slice - deck_z) <= tolerance

    n_kept = keep.sum()
    print(f"  Deck filter: kept {n_kept:,} / {len(pts):,} points  "
          f"({100*n_kept/len(pts):.1f}%)  tolerance=+/-{tolerance}m")
    return pts[keep], keep


def remove_slope(pts):
    """
    After unbending the bridge runs along X.
    Fit a linear Z vs X trend through the deck level and subtract it,
    so the bridge is horizontal when viewed from the side.
    """
    n_sl  = 60
    x_all = pts[:, 0]
    edges = np.linspace(x_all.min(), x_all.max(), n_sl + 1)

    xs, zs = [], []
    for i in range(n_sl):
        mask = (x_all >= edges[i]) & (x_all < edges[i + 1])
        if mask.sum() < 10:
            continue
        xs.append((edges[i] + edges[i + 1]) / 2)
        # 40th percentile = roughly the deck surface level
        zs.append(np.percentile(pts[mask, 2], 40))

    p     = np.polyfit(xs, zs, 1)
    slope = p[0]
    print(f"  Longitudinal slope: {slope*1000:.2f} mm/m -> removing")

    out       = pts.copy()
    out[:, 2] = pts[:, 2] - np.polyval(p, pts[:, 0])
    return out


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",        "-i", default="ifc_cloud.ply")
    ap.add_argument("--output",       "-o", default="ifc_straight.ply")
    ap.add_argument("--slices",       type=int, default=80)
    ap.add_argument("--degree",       type=int, default=3)
    ap.add_argument("--no-slope-fix", action="store_true",
                    help="Skip longitudinal slope removal")
    ap.add_argument("--flatten", type=float, default=None, metavar="TOLERANCE",
                    help="Keep only points within TOLERANCE metres of the local deck surface "
                         "(removes arch humps and pier foundations). E.g. --flatten 2.5")
    ap.add_argument("--no-view",      action="store_true")
    args = ap.parse_args()

    for pkg in ("scipy", "open3d"):
        try:
            __import__(pkg)
        except ImportError:
            print(f"[ERROR] {pkg} required:  pip install {pkg}")
            sys.exit(1)

    import open3d as o3d

    print("=== Straighten IFC cloud ===")
    print(f"  input={args.input}  output={args.output}")
    print(f"  slices={args.slices}  degree={args.degree}\n")

    pcd, pts = load_cloud(args.input)

    print("\n[1] Fitting bridge centreline ...")
    tck_xy, spl_z = fit_spine(pts, args.slices, args.degree)

    print("  Sampling spine ...")
    t_fine, xy_fine, z_fine, arc = spine_samples(tck_xy, spl_z)
    print(f"  Arc length: {arc[-1]:.2f} m")

    print("\n[2] Unbending to arc-length coordinates ...")
    result = unbend(pts, xy_fine, z_fine, arc)

    if not args.no_slope_fix:
        print("\n[3] Removing longitudinal slope ...")
        result = remove_slope(result)

    keep_mask = None
    if args.flatten is not None:
        print(f"\n[4] Filtering to deck surface (tolerance={args.flatten}m) ...")
        result, keep_mask = flatten_to_deck(result, args.flatten)

    span_in  = pts.max(axis=0) - pts.min(axis=0)
    span_out = result.max(axis=0) - result.min(axis=0)
    print(f"\nInput  extent  X={span_in[0]:.2f}  Y={span_in[1]:.2f}  Z={span_in[2]:.2f}")
    print(f"Output extent  X={span_out[0]:.2f}  Y={span_out[1]:.2f}  Z={span_out[2]:.2f}")

    out = o3d.geometry.PointCloud()
    out.points = o3d.utility.Vector3dVector(result)
    if pcd.has_colors():
        c = np.asarray(pcd.colors)
        out.colors = o3d.utility.Vector3dVector(
            c[keep_mask] if args.flatten is not None else c
        )
    if pcd.has_normals() and args.flatten is None:
        out.normals = pcd.normals

    o3d.io.write_point_cloud(args.output, out)
    print(f"\nSaved: {args.output}")

    if not args.no_view:
        centre = result.mean(axis=0).tolist()
        print("Opening viewer ... (Q to quit)")
        # Top-down view so you can confirm the bridge is straight along X
        o3d.visualization.draw_geometries(
            [out],
            window_name="Straightened IFC (top-down)",
            front=[0, 0, -1],
            lookat=centre,
            up=[0, 1, 0],
            zoom=0.3,
        )


if __name__ == "__main__":
    main()
