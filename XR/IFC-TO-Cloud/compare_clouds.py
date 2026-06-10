#!/usr/bin/env python3
"""
Bekijk één of twee point clouds.

Gebruik:
    python compare_clouds.py --ifc ifc_cloud.ply                          # één cloud
    python compare_clouds.py --ifc ifc_cloud.ply --mast3r mast3r_cloud.ply  # twee clouds
    python compare_clouds.py --ifc ifc_cloud.ply --mast3r mast3r_filtered.ply --no-normalize
"""
import argparse
import sys
import time

import numpy as np


def load_cloud(path, label=""):
    import open3d as o3d
    t0 = time.time()
    pcd = o3d.io.read_point_cloud(path)
    if pcd is None or len(pcd.points) == 0:
        print(f"  [FOUT] Kon '{path}' niet laden.")
        sys.exit(1)
    pts = np.asarray(pcd.points)
    span = pts.max(axis=0) - pts.min(axis=0)
    print(f"  {label}: {len(pcd.points):,} punten  "
          f"X={span[0]:.1f}m  Y={span[1]:.1f}m  Z={span[2]:.1f}m  "
          f"langste={float(np.max(span)):.1f}m  ({time.time()-t0:.2f}s)")
    return pcd


def normalize(pcd):
    bbox = pcd.get_axis_aligned_bounding_box()
    center = bbox.get_center()
    extent = bbox.get_extent()
    m = float(max(extent[0], extent[1], extent[2]))
    if m > 0:
        pcd.translate(-center)
        pcd.scale(1.0 / m, center=[0.0, 0.0, 0.0])
    return pcd, center, m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc",    "-i", required=True,       help="Eerste cloud (blauw)")
    parser.add_argument("--mast3r", "-m", default=None,        help="Tweede cloud (rood) — optioneel")
    parser.add_argument("--no-normalize", action="store_true", help="Toon in originele coördinaten")
    parser.add_argument("--point-size",   type=float, default=2.0)
    args = parser.parse_args()

    try:
        import open3d as o3d
    except ImportError:
        print("Open3D niet gevonden.  pip install open3d")
        sys.exit(1)

    print(f"\n=== {args.ifc} ===")
    ifc = load_cloud(args.ifc, "Cloud 1")
    ifc.paint_uniform_color([0.0, 0.4, 1.0])

    geoms = [ifc]
    title = args.ifc

    if args.mast3r:
        print(f"\n=== {args.mast3r} ===")
        mast3r = load_cloud(args.mast3r, "Cloud 2")
        if mast3r.has_colors():
            print("  Originele scan-kleuren behouden.")
            title = "Blauw = IFC   Kleur = MASt3R (origineel)"
        else:
            mast3r.paint_uniform_color([1.0, 0.3, 0.0])
            title = "Blauw = IFC   Rood = MASt3R"
        geoms.append(mast3r)

    if not args.no_normalize:
        ifc, ic, iscale = normalize(ifc)
        print(f"\nNormalisatie: IFC center={np.round(ic,1).tolist()}  scale=1/{iscale:.1f}m")
        if args.mast3r:
            mast3r, mc, mscale = normalize(mast3r)
            print(f"              MASt3R center={np.round(mc,1).tolist()}  scale=1/{mscale:.1f}m")
            print("  Gebruik --no-normalize om in echte meters te bekijken.")

    from viz_utils import show_windows
    show_windows((geoms, title), point_size=args.point_size)


if __name__ == "__main__":
    main()
