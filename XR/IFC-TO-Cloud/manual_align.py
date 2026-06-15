#!/usr/bin/env python3
"""
Handmatige alignment via punt-correspondentie.

Werkwijze:
  Stap 1 — IFC venster:
      Shift + klik  → punt aanwijzen (kies herkenbare punten: brug-uiteinden, pijlers)
      Shift + rechts → laatste punt ongedaan maken
      Q / venster sluiten → klaar

  Stap 2 — MASt3R venster:
      Klik DEZELFDE punten in DEZELFDE volgorde aan.
      Q → klaar

  Minimaal 3 punten vereist. Meer = nauwkeuriger.

Gebruik:
    python manual_align.py --ifc ifc_cloud.ply --mast3r mast3r_filtered.ply
    python manual_align.py --ifc ifc_cloud.ply --mast3r mast3r_filtered.ply --output mast3r_manual.ply
"""
import argparse
import sys
import numpy as np


def load(path, label, color=None):
    import open3d as o3d
    o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Error)
    pcd = o3d.io.read_point_cloud(path)
    if not pcd or len(pcd.points) == 0:
        print(f"[FOUT] Kan '{path}' niet laden.")
        sys.exit(1)
    pts = np.asarray(pcd.points)
    span = pts.ptp(axis=0)
    has_colors = pcd.has_colors()
    print(f"  {label}: {len(pts):,} punten  langste={float(np.max(span)):.1f}m  "
          f"kleuren={'ja (origineel)' if has_colors else 'nee'}")
    if color is not None and not has_colors:
        pcd.paint_uniform_color(color)
    elif color is not None and has_colors:
        print(f"    → originele kleuren behouden (geen uniform kleur toegepast)")
    return pcd


def pick_points(pcd, title, instructions):
    import open3d as o3d
    o3d.utility.set_verbosity_level(o3d.utility.VerbosityLevel.Error)
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")
    for line in instructions:
        print(f"  {line}")
    print(f"{'─'*55}")

    vis = o3d.visualization.VisualizerWithEditing()
    vis.create_window(window_name=title, width=1280, height=800)
    vis.add_geometry(pcd)

    # Render options
    opt = vis.get_render_option()
    opt.point_size = 3.0
    opt.background_color = np.array([0.08, 0.08, 0.08])

    vis.run()
    vis.destroy_window()

    indices = vis.get_picked_points()
    if len(indices) == 0:
        print("  Geen punten gekozen.")
        return np.empty((0, 3))

    coords = np.asarray(pcd.points)[list(indices)]
    print(f"  {len(indices)} punten gekozen:")
    for i, (idx, c) in enumerate(zip(indices, coords)):
        print(f"    #{i+1}  index={idx}  xyz=({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f})")
    return coords


def compute_transform(src_pts, tgt_pts):
    """
    Bereken rigide transformatie (rotatie + translatie) via SVD.
    src_pts worden getransformeerd naar tgt_pts.
    """
    assert len(src_pts) == len(tgt_pts) >= 3

    src_c = src_pts.mean(axis=0)
    tgt_c = tgt_pts.mean(axis=0)

    A = src_pts - src_c
    B = tgt_pts - tgt_c

    H = A.T @ B
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T

    # Corrigeer spiegeling (det moet +1 zijn)
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T

    t = tgt_c - R @ src_c

    T = np.eye(4)
    T[:3, :3] = R
    T[:3,  3] = t
    return T


def apply_and_show(ifc, mast3r_orig, T, output_path):
    import open3d as o3d
    from viz_utils import show_windows

    aligned = o3d.geometry.PointCloud(mast3r_orig)
    aligned.transform(T)

    # Controleer nauwkeurigheid
    dists = np.asarray(ifc.compute_point_cloud_distance(aligned))
    print(f"\n  Gem. afstand na alignment : {np.mean(dists):.3f}m")
    print(f"  Mediaan afstand           : {np.median(dists):.3f}m")

    o3d.io.write_point_cloud(output_path, aligned)
    print(f"  Opgeslagen: {output_path}")

    ifc_v = o3d.geometry.PointCloud(ifc)
    ifc_v.paint_uniform_color([0.0, 0.4, 1.0])

    # MASt3R behoudt originele kleuren als die aanwezig zijn
    if not aligned.has_colors():
        aligned.paint_uniform_color([1.0, 0.3, 0.0])
        kleur_info = "Rood = MASt3R (geen originele kleuren)"
    else:
        kleur_info = "Kleur = MASt3R originele scan-kleuren"

    print(f"\n  [Blauw = IFC]  [{kleur_info}]")
    show_windows(
        ([ifc_v, aligned], f"Resultaat — Blauw=IFC  |  {kleur_info}"),
        point_size=2.0,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc",    "-i", required=True)
    parser.add_argument("--mast3r", "-m", required=True)
    parser.add_argument("--output", "-o", default="mast3r_manual.ply")
    args = parser.parse_args()

    try:
        import open3d as o3d
    except ImportError:
        print("Open3D niet gevonden.  pip install open3d")
        sys.exit(1)

    print("=== Laden ===")
    ifc    = load(args.ifc,    "IFC   ", [0.0, 0.4, 1.0])
    mast3r = load(args.mast3r, "MASt3R", [1.0, 0.3, 0.0])

    ifc_instructions = [
        "Kies 3 of meer herkenbare punten op de IFC brug.",
        "Goede keuzes: brug-uiteinden, pijler-bovenkanten,",
        "hoekpunten van het dek.",
        "",
        "Shift + klik      → punt kiezen",
        "Shift + rechts    → laatste punt ongedaan",
        "Q / venster dicht → klaar",
    ]
    mast3r_instructions = [
        "Kies DEZELFDE punten in DEZELFDE VOLGORDE als in de IFC.",
        "Punt #1 hier moet overeenkomen met punt #1 in IFC, enz.",
        "",
        "Shift + klik      → punt kiezen",
        "Shift + rechts    → laatste punt ongedaan",
        "Q / venster dicht → klaar",
    ]

    ifc_pts    = pick_points(ifc,    "Stap 1 — Kies punten op IFC (blauw)",    ifc_instructions)
    mast3r_pts = pick_points(mast3r, "Stap 2 — Kies DEZELFDE punten op MASt3R (rood)", mast3r_instructions)

    if len(ifc_pts) < 3 or len(mast3r_pts) < 3:
        print("\n[FOUT] Minimaal 3 punten per cloud vereist.")
        sys.exit(1)

    if len(ifc_pts) != len(mast3r_pts):
        n = min(len(ifc_pts), len(mast3r_pts))
        print(f"\n[WAARSCHUWING] Ongelijk aantal punten — gebruik eerste {n} van elk.")
        ifc_pts    = ifc_pts[:n]
        mast3r_pts = mast3r_pts[:n]

    print(f"\n=== Transformatie berekenen ({len(ifc_pts)} punt-paren) ===")
    T = compute_transform(mast3r_pts, ifc_pts)
    print(f"  Rotatie:\n{np.round(T[:3,:3], 4)}")
    print(f"  Translatie: {np.round(T[:3,3], 2).tolist()}")

    apply_and_show(ifc, mast3r, T, args.output)


if __name__ == "__main__":
    main()
