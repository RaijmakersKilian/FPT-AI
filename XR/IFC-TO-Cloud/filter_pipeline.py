#!/usr/bin/env python3
"""
Filter pipeline: MASt3R cloud schoonmaken en uitlijnen op IFC cloud.

Volgorde:
  1. PCA alignment     (rotatie + schaal)
  2. Bounding box crop (houdt punten in buurt van IFC)
  3. Statistical Outlier Removal
  4. Radius Outlier Removal
  5. Hoogte-filter

Gebruik:
    python filter_pipeline.py --ifc ifc_cloud.ply --mast3r mast3r_cloud.ply
    python filter_pipeline.py --ifc ifc_cloud.ply --mast3r mast3r_cloud.ply --no-ror --height-min -5 --height-max 20
"""
import argparse
import sys
import numpy as np


# ── hulpfuncties ────────────────────────────────────────────────────────────

def load_cloud(path, label=""):
    import open3d as o3d
    pcd = o3d.io.read_point_cloud(path)
    if pcd is None or len(pcd.points) == 0:
        print(f"[FOUT] Kan '{path}' niet laden.")
        sys.exit(1)
    _print_stats(pcd, f"Geladen  {label}")
    return pcd


def _print_stats(pcd, label=""):
    pts = np.asarray(pcd.points)
    if len(pts) == 0:
        print(f"  {label}: 0 punten")
        return
    span = pts.max(axis=0) - pts.min(axis=0)
    print(f"  {label}: {len(pts)} punten  "
          f"X={span[0]:.2f}  Y={span[1]:.2f}  Z={span[2]:.2f}  "
          f"langste={float(np.max(span)):.2f}m")


def _make_proper(axes):
    """Zorg dat de matrix een echte rotatiematrix is (det = +1)."""
    if np.linalg.det(axes) < 0:
        axes = axes.copy()
        axes[:, 0] *= -1
    return axes


def pca_axes(pcd):
    pts = np.asarray(pcd.points)
    centroid = pts.mean(axis=0)
    centered = pts - centroid
    cov = centered.T @ centered / len(pts)
    vals, vecs = np.linalg.eigh(cov)
    idx = np.argsort(vals)[::-1]
    return centroid, _make_proper(vecs[:, idx])


def _apply_transform(pcd, R, scale, src_center, tgt_center):
    import open3d as o3d
    pts = (np.asarray(pcd.points) - src_center) @ R.T * scale + tgt_center
    result = o3d.geometry.PointCloud()
    result.points = o3d.utility.Vector3dVector(pts)
    if pcd.has_colors():
        result.colors = pcd.colors
    if pcd.has_normals():
        result.normals = o3d.utility.Vector3dVector(np.asarray(pcd.normals) @ R.T)
    return result


# ── Z-flip hulpfuncties ──────────────────────────────────────────────────────

def _flip_z_around(pcd, z_center):
    """Spiegel alle punten rond z_center (Z-as omdraaien)."""
    import open3d as o3d
    pts = np.asarray(pcd.points).copy()
    pts[:, 2] = 2.0 * z_center - pts[:, 2]
    result = o3d.geometry.PointCloud()
    result.points = o3d.utility.Vector3dVector(pts)
    if pcd.has_colors():  result.colors  = pcd.colors
    if pcd.has_normals(): result.normals = pcd.normals
    return result


def _z_histogram_error(pcd_a, pcd_b, bins=40):
    """MAE tussen genormaliseerde Z-histogrammen van twee clouds."""
    za = np.asarray(pcd_a.points)[:, 2]
    zb = np.asarray(pcd_b.points)[:, 2]
    lo = min(za.min(), zb.min())
    hi = max(za.max(), zb.max())
    if hi <= lo:
        return float("inf")
    ha, _ = np.histogram(za, bins=bins, range=(lo, hi), density=True)
    hb, _ = np.histogram(zb, bins=bins, range=(lo, hi), density=True)
    return float(np.mean(np.abs(ha - hb)))


# ── stap 1: PCA alignment ────────────────────────────────────────────────────

def step_pca_align(mast3r, ifc, force_flip_z=False):
    import open3d as o3d
    print("\n── Stap 1: PCA alignment ──")

    ifc_center,    ifc_ax    = pca_axes(ifc)
    mast3r_center, mast3r_ax = pca_axes(mast3r)

    # Robuuste lengtemeting via PCA-projectie (percentiel 2–98) → ruis heeft geen invloed
    def pca_length(pts, centroid, ax, lo=2, hi=98):
        proj = (pts - centroid) @ ax[:, 0]
        return float(np.percentile(proj, hi) - np.percentile(proj, lo))

    ifc_pts    = np.asarray(ifc.points)
    mast3r_pts = np.asarray(mast3r.points)
    ifc_len    = pca_length(ifc_pts,    ifc_center,    ifc_ax)
    mast3r_len = pca_length(mast3r_pts, mast3r_center, mast3r_ax)
    scale = ifc_len / mast3r_len
    print(f"  IFC lengte (P2-P98 langs PC1)   : {ifc_len:.3f}m")
    print(f"  MASt3R lengte (P2-P98 langs PC1): {mast3r_len:.3f}")
    print(f"  Schaalfactor: ×{scale:.4f}")

    # 4 geldige rotatie-varianten (det R = +1)
    sign_combos = [(1,1,1), (1,-1,-1), (-1,1,-1), (-1,-1,1)]

    voxel = ifc_len / 300.0
    ifc_eval = ifc.voxel_down_sample(voxel)

    best_pcd, best_dist, best_signs = None, float("inf"), None
    for s0, s1, s2 in sign_combos:
        flipped = mast3r_ax * np.array([s0, s1, s2])
        R = ifc_ax @ flipped.T
        if abs(np.linalg.det(R) - 1.0) > 0.05:
            continue
        candidate = _apply_transform(mast3r, R, scale, mast3r_center, ifc_center)
        dists = np.asarray(ifc_eval.compute_point_cloud_distance(candidate))
        mean_dist = float(np.mean(dists))
        print(f"  tekens=({s0:+d},{s1:+d},{s2:+d})  gem. afstand={mean_dist:.4f}")
        if mean_dist < best_dist:
            best_dist, best_pcd, best_signs = mean_dist, candidate, (s0, s1, s2)

    print(f"  → Beste rotatie: tekens={best_signs}  gem. afstand={best_dist:.4f}")

    # Z-flip check: vergelijk Z-histogram van gealigneerde MASt3R met IFC
    ifc_z_center = float(np.asarray(ifc.points)[:, 2].mean())
    flipped_z = _flip_z_around(best_pcd, ifc_z_center)
    err_normal  = _z_histogram_error(ifc, best_pcd)
    err_flipped = _z_histogram_error(ifc, flipped_z)
    print(f"  Z-histogram fout — normaal: {err_normal:.4f}  geflipt: {err_flipped:.4f}")

    if force_flip_z:
        print("  → Z geflipt (--flip-z opgegeven)")
        best_pcd = flipped_z
    elif err_flipped < err_normal:
        print("  → Z automatisch geflipt (betere Z-distributie match)")
        best_pcd = flipped_z
    else:
        print("  → Z niet geflipt")

    _print_stats(best_pcd, "Na PCA  ")
    return best_pcd


# ── stap 2: bounding-box crop ────────────────────────────────────────────────

def step_bbox_crop(mast3r, ifc, crop_scale=1.2):
    import open3d as o3d
    print(f"\n── Stap 2: Bounding-box crop (schaalfactor={crop_scale}) ──")
    bbox = ifc.get_axis_aligned_bounding_box()
    bbox_scaled = bbox.scale(crop_scale, bbox.get_center())
    cropped = mast3r.crop(bbox_scaled)
    _print_stats(cropped, "Na crop ")
    if len(cropped.points) == 0:
        print("  [WAARSCHUWING] Lege cloud na crop — stap overgeslagen")
        return mast3r
    return cropped


# ── stap 3: Statistical Outlier Removal ─────────────────────────────────────

def step_sor(pcd, nb_neighbors=20, std_ratio=2.0):
    print(f"\n── Stap 3: Statistical Outlier Removal "
          f"(neighbors={nb_neighbors}, std={std_ratio}) ──")
    clean, _ = pcd.remove_statistical_outlier(nb_neighbors=nb_neighbors,
                                               std_ratio=std_ratio)
    removed = len(pcd.points) - len(clean.points)
    print(f"  Verwijderd: {removed} ({removed/len(pcd.points)*100:.1f}%)")
    _print_stats(clean, "Na SOR  ")
    return clean


# ── stap 4: Radius Outlier Removal ──────────────────────────────────────────

def step_ror(pcd, nb_points=16, radius=2.0):
    print(f"\n── Stap 4: Radius Outlier Removal "
          f"(nb_points={nb_points}, radius={radius}) ──")
    clean, _ = pcd.remove_radius_outlier(nb_points=nb_points, radius=radius)
    removed = len(pcd.points) - len(clean.points)
    print(f"  Verwijderd: {removed} ({removed/len(pcd.points)*100:.1f}%)")
    _print_stats(clean, "Na ROR  ")
    return clean


# ── stap 5: hoogte-filter ────────────────────────────────────────────────────

def step_height_filter(pcd, z_min=None, z_max=None):
    print(f"\n── Stap 5: Hoogte-filter (z_min={z_min}, z_max={z_max}) ──")
    pts = np.asarray(pcd.points)
    mask = np.ones(len(pts), dtype=bool)
    if z_min is not None:
        mask &= pts[:, 2] >= z_min
    if z_max is not None:
        mask &= pts[:, 2] <= z_max
    import open3d as o3d
    filtered = pcd.select_by_index(np.where(mask)[0])
    removed = len(pts) - len(filtered.points)
    print(f"  Verwijderd: {removed} ({removed/len(pts)*100:.1f}%)")
    _print_stats(filtered, "Na Z    ")
    return filtered


# ── visualisatie ─────────────────────────────────────────────────────────────

def _open_window(geometries, title, point_size=2.0):
    import open3d as o3d
    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name=title, width=1280, height=800)
    for g in geometries:
        vis.add_geometry(g)
    opt = vis.get_render_option()
    opt.point_size = point_size
    opt.background_color = np.array([0.1, 0.1, 0.1])
    vis.poll_events()
    vis.update_renderer()
    vis.reset_view_point(True)
    vis.run()
    vis.destroy_window()


def visualize(ifc, mast3r_clean, coverage_threshold=5.0):
    import open3d as o3d

    # ── Venster 1: beide clouds naast elkaar ──
    from viz_utils import color_cloud
    ifc_vis = color_cloud(o3d.geometry.PointCloud(ifc), [0.0, 0.4, 1.0])
    mast3r_vis = color_cloud(o3d.geometry.PointCloud(mast3r_clean), [1.0, 0.3, 0.0])
    print("\n[Venster 1] Blauw = IFC (volledig)   Rood = MASt3R (gescand)")
    print("  Sluit dit venster om de coverage-analyse te zien.")
    _open_window([ifc_vis, mast3r_vis], "IFC vs MASt3R")

    # ── Venster 2: coverage-analyse ──
    print(f"\n[Venster 2] Coverage-analyse (drempelwaarde={coverage_threshold:.1f}m)...")
    dists = np.asarray(ifc.compute_point_cloud_distance(mast3r_clean))
    covered = dists < coverage_threshold
    pct = float(covered.sum()) / len(covered) * 100.0
    print(f"  IFC punten gedekt : {covered.sum():,}  /  {len(covered):,}  ({pct:.1f}%)")
    print(f"  IFC punten ontbreekt: {(~covered).sum():,}  ({100-pct:.1f}%)")

    # Kleur: groen = gedekt, rood = nog niet gebouwd
    colors = np.zeros((len(dists), 3))
    colors[ covered] = [0.0, 0.9, 0.2]   # groen
    colors[~covered] = [1.0, 0.15, 0.0]  # rood
    ifc_cov = o3d.geometry.PointCloud(ifc)
    ifc_cov.colors = o3d.utility.Vector3dVector(colors)

    print("  Groen = gedekt door MASt3R scan")
    print("  Rood  = nog niet gescand / gebouwd")
    _open_window([ifc_cov], "Coverage: Groen=gedekt  Rood=ontbreekt")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc",    "-i", required=True)
    parser.add_argument("--mast3r", "-m", required=True)
    parser.add_argument("--output", "-o", default="mast3r_filtered.ply")

    parser.add_argument("--no-align",  action="store_true", help="Sla PCA alignment over")
    parser.add_argument("--flip-z",    action="store_true", help="Forceer Z-flip na alignment (brug staat ondersteboven)")
    parser.add_argument("--no-crop",   action="store_true", help="Sla bbox crop over")
    parser.add_argument("--no-sor",    action="store_true", help="Sla Statistical OR over")
    parser.add_argument("--no-ror",    action="store_true", help="Sla Radius OR over")
    parser.add_argument("--no-height", action="store_true", help="Sla hoogte-filter over")
    parser.add_argument("--no-view",   action="store_true")

    parser.add_argument("--crop-scale",   type=float, default=1.2)
    parser.add_argument("--sor-neighbors",type=int,   default=20)
    parser.add_argument("--sor-std",      type=float, default=2.0)
    parser.add_argument("--ror-points",   type=int,   default=16)
    parser.add_argument("--ror-radius",   type=float, default=2.0)
    parser.add_argument("--height-min",          type=float, default=None)
    parser.add_argument("--height-max",          type=float, default=None)
    parser.add_argument("--coverage-threshold",  type=float, default=5.0,
                        help="Max afstand (m) IFC→MASt3R om als 'gedekt' te tellen (default 5.0)")
    parser.add_argument("--rz", type=float, default=0.0, help="Handmatige rotatie om Z-as (graden, + = tegen klok in)")
    parser.add_argument("--tx", type=float, default=0.0, help="Handmatige verschuiving X (meter, + = rechts)")
    parser.add_argument("--ty", type=float, default=0.0, help="Handmatige verschuiving Y (meter, + = vooruit)")
    parser.add_argument("--tz", type=float, default=0.0, help="Handmatige verschuiving Z (meter, + = omhoog)")
    args = parser.parse_args()

    try:
        import open3d as o3d
    except ImportError:
        print("Open3D niet gevonden. pip install open3d")
        sys.exit(1)

    print("=== IFC cloud ===")
    ifc = load_cloud(args.ifc, "IFC")
    print("\n=== MASt3R cloud (origineel) ===")
    mast3r = load_cloud(args.mast3r, "MASt3R")

    pcd = mast3r

    if not args.no_align:
        pcd = step_pca_align(pcd, ifc, force_flip_z=args.flip_z)

    if not args.no_crop:
        pcd = step_bbox_crop(pcd, ifc, crop_scale=args.crop_scale)

    if not args.no_sor:
        pcd = step_sor(pcd, nb_neighbors=args.sor_neighbors, std_ratio=args.sor_std)

    if not args.no_ror:
        # Radius in wereld-eenheden: ~1% van bruglengte als standaard
        ifc_span = np.asarray(ifc.points).ptp(axis=0)
        default_radius = float(np.max(ifc_span)) * 0.01 if args.ror_radius == 2.0 else args.ror_radius
        pcd = step_ror(pcd, nb_points=args.ror_points, radius=default_radius)

    if not args.no_height:
        if args.height_min is not None or args.height_max is not None:
            pcd = step_height_filter(pcd, z_min=args.height_min, z_max=args.height_max)
        else:
            print("\n── Stap 5: Hoogte-filter overgeslagen (geen --height-min/--height-max opgegeven)")

    if args.rz != 0.0:
        angle_rad = np.deg2rad(args.rz)
        R = np.array([
            [np.cos(angle_rad), -np.sin(angle_rad), 0],
            [np.sin(angle_rad),  np.cos(angle_rad), 0],
            [0, 0, 1]
        ])
        center = np.asarray(ifc.points).mean(axis=0)
        print(f"\n── Handmatige rotatie Z: {args.rz:+.1f}° (draaipunt = IFC centroïde) ──")
        pcd.rotate(R, center=center)

    if args.tx != 0.0 or args.ty != 0.0 or args.tz != 0.0:
        print(f"\n── Handmatige verschuiving: X={args.tx:+.1f}m  Y={args.ty:+.1f}m  Z={args.tz:+.1f}m ──")
        pcd.translate([args.tx, args.ty, args.tz])

    print(f"\n=== Eindresultaat ===")
    _print_stats(pcd, "MASt3R gefilterd")

    o3d.io.write_point_cloud(args.output, pcd)
    print(f"Opgeslagen: {args.output}")

    if not args.no_view:
        visualize(ifc, pcd, coverage_threshold=args.coverage_threshold)


if __name__ == "__main__":
    main()
