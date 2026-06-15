#!/usr/bin/env python3
"""
Laad opgeslagen coverage-resultaten en toon beide vensters direct.
Geen herberekening nodig.

Gebruik:
    python view_coverage.py
    python view_coverage.py --json coverage_results.json
    python view_coverage.py --json coverage_results.json --point-size 3
"""
import argparse
import json
import sys
import numpy as np


def _run_window(geoms, title, point_size=2.0):
    import open3d as o3d
    vis = o3d.visualization.Visualizer()
    vis.create_window(window_name=title, width=1280, height=800)
    for g in geoms:
        vis.add_geometry(g)
    opt = vis.get_render_option()
    opt.point_size = point_size
    opt.background_color = np.array([0.08, 0.08, 0.08])
    vis.poll_events()
    vis.update_renderer()
    vis.reset_view_point(True)
    vis.run()
    vis.destroy_window()


def print_table(results, threshold):
    BUILT   = 0.80
    PARTIAL = 0.30
    def st(c):
        if c >= BUILT:   return "Built"
        if c >= PARTIAL: return "Partial"
        return "Missing"

    print(f"\n{'Groep':<45} {'Elem':>5} {'%':>6}  Status")
    print("─" * 70)
    for r in sorted(results, key=lambda x: -x["coverage"]):
        c   = r["coverage"]
        bar = "█" * int(c * 15) + "░" * (15 - int(c * 15))
        print(f"  {r['group']:<43} {r['n_elements']:5d} {c*100:5.1f}%  {st(c):<8}  {bar}")

    built   = sum(1 for r in results if r["coverage"] >= BUILT)
    partial = sum(1 for r in results if PARTIAL <= r["coverage"] < BUILT)
    missing = sum(1 for r in results if r["coverage"] < PARTIAL)
    print("─" * 70)
    print(f"  Built={built}  Partial={partial}  Missing={missing}  "
          f"(drempel={threshold}m)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json",       default="coverage_results.json",
                        help="JSON bestand aangemaakt door coverage_per_type.py")
    parser.add_argument("--point-size", type=float, default=2.0)
    args = parser.parse_args()

    try:
        import open3d as o3d
    except ImportError:
        print("Open3D niet gevonden. pip install open3d")
        sys.exit(1)

    # ── Laad JSON ──
    try:
        data = json.loads(open(args.json).read())
    except FileNotFoundError:
        print(f"[FOUT] {args.json} niet gevonden.")
        print("  Draai eerst: python coverage_per_type.py ...")
        sys.exit(1)

    print_table(data["results"], data["threshold"])

    # ── Laad point clouds ──
    ifc_path = data.get("ifc_cloud", "ifc_cloud.ply")
    m_path   = data.get("mast3r",    "mast3r_filtered.ply")
    cov_path = data.get("coverage_colored_ply", "coverage_colored.ply")

    missing_files = []
    for p in [ifc_path, m_path, cov_path]:
        import pathlib
        if not pathlib.Path(p).exists():
            missing_files.append(p)

    if missing_files:
        print(f"\n[FOUT] Bestanden niet gevonden:")
        for f in missing_files:
            print(f"  {f}")
        sys.exit(1)

    print(f"\nLaden...")
    from viz_utils import color_cloud
    ifc_v = color_cloud(o3d.io.read_point_cloud(ifc_path), [0.0, 0.4, 1.0])
    m_v   = color_cloud(o3d.io.read_point_cloud(m_path),   [0.55, 0.55, 0.55])
    cov_pcd = o3d.io.read_point_cloud(cov_path)

    print(f"  IFC:      {len(ifc_v.points):,} punten")
    print(f"  MASt3R:   {len(m_v.points):,} punten")
    print(f"  Coverage: {len(cov_pcd.points):,} punten")

    print("\nVenster 1 — Blauw=IFC  Grijs=MASt3R")
    print("Venster 2 — Groen=Built  Oranje=Partial  Rood=Missing")

    from viz_utils import show_windows
    show_windows(
        ([ifc_v, m_v], "Venster 1 — IFC (blauw) vs MASt3R (grijs)"),
        ([cov_pcd],    "Venster 2 — Coverage: Groen=Built  Oranje=Partial  Rood=Missing"),
        point_size=args.point_size,
    )


if __name__ == "__main__":
    main()
