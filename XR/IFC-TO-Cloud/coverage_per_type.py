#!/usr/bin/env python3
"""
Coverage analyse per IFC element groep.

Omdat alle elementen IfcBuildingElementProxy zijn, wordt geclassificeerd
op basis van de element-Naam (bijv. "Pijler_01" → groep "Pijler").

Gebruik de snelle iterator (zelfde als ifctocloud.py) — niet create_shape() per element.
Duurt ~6 min (zelfde als de originele IFC verwerking).

Gebruik:
    python coverage_per_type.py --ifc brug.ifc --ifc-cloud ifc_cloud.ply --mast3r mast3r_filtered.ply
    python coverage_per_type.py --ifc brug.ifc --ifc-cloud ifc_cloud.ply --mast3r mast3r_filtered.ply --threshold 3.0 --top 15
"""
import argparse
import json
import pathlib
import re
import sys
import time

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import trimesh

BUILT_THRESHOLD   = 0.80
PARTIAL_THRESHOLD = 0.30

COLOR_BUILT   = np.array([0.10, 0.85, 0.20])
COLOR_PARTIAL = np.array([1.00, 0.55, 0.00])
COLOR_MISSING = np.array([0.90, 0.10, 0.10])


def status(pct):
    if pct >= BUILT_THRESHOLD:   return "Built"
    if pct >= PARTIAL_THRESHOLD: return "Partial"
    return "Missing"


def seg_color(pct):
    if pct >= BUILT_THRESHOLD:   return COLOR_BUILT
    if pct >= PARTIAL_THRESHOLD: return COLOR_PARTIAL
    return COLOR_MISSING


# ── naam-mapping op basis van Naming BIM (1).docx ────────────────────────────

# Elke entry: (naam_bevat, groepslabel_NL, groepslabel_EN)
NAME_MAPPING = [
    # Mặt cầu (road deck)
    ("KCPT_BAN MAT",              "Bản mặt cầu",          "Road deck"),
    ("KCPT_LOP",                  "Lớp mặt cầu",          "Road deck layer"),
    # Dầm (beams)
    ("KCPT_I24",                  "Dầm I",                "Support beam"),
    ("KCPT_I33",                  "Dầm I",                "Support beam"),
    ("KCPD_XA MU",                "Xà mũ",                "Column cap"),
    # Trụ / mố (piers & abutments)
    ("KCPD_COC",                  "Cọc móng",             "Pile"),
    ("KCPD_THAN TRU",             "Thân trụ",             "Pier body"),
    ("KCPD_THAN MO",              "Thân mố",              "Abutment body"),
    # Kết cấu liên kết (connection structures)
    ("KCPT_K101",                 "Kết cấu K101",         "Road-pier connector"),
    ("KCPT_Ki",                   "Cấu kiện Ki",          "Road support element"),
    ("KCPT_DOT TREN",             "Đốt trên",             "Upper segment"),
    # Bản đáy / bê tông (bottom slabs & concrete)
    ("KCPD_BTL",                  "Bản tấm lót",          "Bottom slab"),
    ("KCPD_BE TRU",               "Bê tông trụ",          "Pier concrete"),
    ("KCPD_BE MO",                "Bê tông mố",           "Abutment concrete"),
    # Đầu cầu (bridge ends)
    ("KCPD_TUONG",                "Tường đầu cầu",        "End wall"),
    ("KCK_BAN QUA",               "Bản quá độ",           "Transition slab"),
    ("KCK_TUONG CHAN",             "Tường chắn",           "Retaining wall"),
    # Lan can (railing)
    ("KCPT_GO LAN CAN",           "Gờ lan can",           "Railing post"),
    ("LOAI1_Thep hop",            "Thép hộp lan can",     "Railing bar"),
    # Bê tông lót (approach)
    ("KCK_M2-BAN QUA DO",         "Bê tông lót",          "Approach concrete"),
]


def name_to_group(name, obj_type):
    """
    Kijk of de elementnaam een bekende prefix bevat (uit Naming BIM (1).docx).
    Geeft (groepslabel_NL, groepslabel_EN) terug, of de rauwe naam als fallback.
    """
    raw = (name or obj_type or "").strip()
    raw_upper = raw.upper()
    for keyword, label_nl, label_en in NAME_MAPPING:
        if keyword.upper() in raw_upper:
            return f"{label_nl}  [{label_en}]"
    # Fallback: verwijder trailing nummers
    prefix = re.sub(r'[\s_\-\.]*\d+[\s_\-\.]*$', '', raw).strip()
    return prefix if prefix else "Onbekend"


# ── transform laden ───────────────────────────────────────────────────────────

def load_transform(ifc_cloud_path):
    p = pathlib.Path(ifc_cloud_path).with_suffix(".transform.json")
    if not p.exists():
        print(f"  [INFO] Geen transform.json gevonden — scale=1 gebruikt (geen herschaling).")
        return np.zeros(3), 1.0
    info = json.loads(p.read_text())
    center = np.array(info["center"])
    scale  = float(info["scale"])
    print(f"  scale={scale:.6f}  center={np.round(center,1).tolist()}")
    return center, scale


# ── MASt3R KD-tree ────────────────────────────────────────────────────────────

def build_kdtree(mast3r_path, voxel=0.5):
    import open3d as o3d
    from scipy.spatial import KDTree
    pcd = o3d.io.read_point_cloud(mast3r_path)
    print(f"  Origineel: {len(pcd.points):,} punten")
    if voxel > 0:
        pcd = pcd.voxel_down_sample(voxel)
        print(f"  Na voxel ({voxel}m): {len(pcd.points):,} punten")
    pts = np.asarray(pcd.points)
    kd  = KDTree(pts)
    return kd


# ── IFC iterator: geometrie + naam ───────────────────────────────────────────

def process_ifc(ifc_path, center, scale, kd, threshold, pts_per_element=200):
    """
    Itereert alle elementen in één pass (snel), groepeert op naam-prefix,
    berekent coverage per groep.
    """
    model    = ifcopenshell.open(ifc_path)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    iterator = ifcopenshell.geom.iterator(settings, model)

    # groepen: group_key → {"pts": [...], "names": set()}
    groups = {}
    count  = 0
    t0     = time.time()

    if not iterator.initialize():
        print("  [FOUT] Iterator kan niet starten.")
        return {}, np.empty((0,3)), np.empty((0,3))

    while True:
        shape = iterator.get()
        geo   = shape.geometry

        # Element-naam ophalen
        try:
            el      = model.by_id(shape.id)
            name    = getattr(el, "Name", None) or ""
            obj_t   = getattr(el, "ObjectType", None) or ""
            group   = name_to_group(name, obj_t)
        except Exception:
            group = "Onbekend"

        # Geometrie → punten
        verts = np.array(geo.verts, dtype=np.float64).reshape(-1, 3)
        faces = np.array(geo.faces, dtype=np.int64).reshape(-1, 3)

        if len(verts) > 0 and len(faces) > 0:
            try:
                mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
                if mesh.area > 1e-6:
                    n = min(pts_per_element, max(10, int(mesh.area / 0.5)))
                    pts, _ = trimesh.sample.sample_surface(mesh, n)
                    pts = (pts - center) * scale + center   # zelfde transform als IFC cloud
                    g = groups.setdefault(group, {"pts": [], "count": 0})
                    g["pts"].append(pts)
                    g["count"] += 1
            except Exception:
                pass

        count += 1
        if count % 200 == 0:
            elapsed = time.time() - t0
            print(f"  {count} elementen verwerkt  ({elapsed:.0f}s)  groepen: {len(groups)}")

        if not iterator.next():
            break

    print(f"  Klaar: {count} elementen in {time.time()-t0:.0f}s  groepen: {len(groups)}")

    # Coverage per groep berekenen
    results         = []
    all_colored_pts = []
    all_colored_clrs= []

    for group, data in sorted(groups.items(), key=lambda x: -len(x[1]["pts"])):
        if not data["pts"]:
            continue
        all_pts  = np.vstack(data["pts"])
        dists, _ = kd.query(all_pts)
        covered  = dists < threshold
        cov      = float(covered.sum()) / len(covered)
        results.append((group, data["count"], len(all_pts), cov))

        c = seg_color(cov)
        all_colored_pts.append(all_pts)
        all_colored_clrs.append(np.tile(c, (len(all_pts), 1)))

    colored_pts  = np.vstack(all_colored_pts)  if all_colored_pts  else np.empty((0,3))
    colored_clrs = np.vstack(all_colored_clrs) if all_colored_clrs else np.empty((0,3))
    return results, colored_pts, colored_clrs


# ── tabel ─────────────────────────────────────────────────────────────────────

def print_table(results, top=None):
    rows = sorted(results, key=lambda x: -x[3])
    if top:
        rows = rows[:top]
    print(f"\n{'Groep (naam-prefix)':<35} {'Elem':>5} {'Punten':>8} {'%':>6}  Status")
    print("-" * 75)
    for group, n_el, n_pts, cov in rows:
        bar = "#" * int(cov * 15) + "." * (15 - int(cov * 15))
        safe = group.encode("ascii", errors="replace").decode("ascii")
        print(f"  {safe:<33} {n_el:5d} {n_pts:8,} {cov*100:5.1f}%  {status(cov):<8}  {bar}")

    built   = sum(1 for _, _, _, c in results if c >= BUILT_THRESHOLD)
    partial = sum(1 for _, _, _, c in results if PARTIAL_THRESHOLD <= c < BUILT_THRESHOLD)
    missing = sum(1 for _, _, _, c in results if c < PARTIAL_THRESHOLD)
    print("-" * 75)
    print(f"  Totaal groepen: {len(results)}  Built={built}  Partial={partial}  Missing={missing}")


# ── visualisatie ──────────────────────────────────────────────────────────────


def visualize(ifc_cloud_path, mast3r_path, colored_pts, colored_clrs):
    import open3d as o3d
    from viz_utils import show_windows

    from viz_utils import color_cloud
    ifc_v = color_cloud(o3d.io.read_point_cloud(ifc_cloud_path), [0.0, 0.4, 1.0])
    m_v   = color_cloud(o3d.io.read_point_cloud(mast3r_path),    [0.55, 0.55, 0.55])

    specs = [([ifc_v, m_v], "Venster 1 — IFC (blauw) vs MASt3R (grijs)")]

    if len(colored_pts) > 0:
        cov_pcd = o3d.geometry.PointCloud()
        cov_pcd.points = o3d.utility.Vector3dVector(colored_pts)
        cov_pcd.colors = o3d.utility.Vector3dVector(colored_clrs)
        specs.append(([cov_pcd], "Venster 2 — Coverage: Groen=Built  Oranje=Partial  Rood=Missing"))

    print(f"\n{len(specs)} vensters openen tegelijk...")
    show_windows(*specs)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc",       required=True)
    parser.add_argument("--ifc-cloud", required=True)
    parser.add_argument("--mast3r",    required=True)
    parser.add_argument("--threshold", type=float, default=5.0)
    parser.add_argument("--top",         type=int,   default=None, help="Toon alleen de top-N groepen")
    parser.add_argument("--no-view",     action="store_true")
    parser.add_argument("--export-json", default=None,
                        help="Extra pad om coverage_results.json naar te kopiëren (bijv. ../../Frontend/coverage_results.json)")
    args = parser.parse_args()

    try:
        import open3d as o3d
        from scipy.spatial import KDTree
    except ImportError as e:
        print(f"Ontbrekend: {e}\npip install open3d scipy")
        sys.exit(1)

    print("=== Transform laden ===")
    center, scale = load_transform(args.ifc_cloud)

    print("\n=== MASt3R KD-tree bouwen ===")
    kd = build_kdtree(args.mast3r, voxel=0.5)

    print(f"\n=== IFC verwerken (dit duurt ~6 min) ===")
    print(f"  Threshold: {args.threshold}m")
    results, colored_pts, colored_clrs = process_ifc(
        args.ifc, center, scale, kd, threshold=args.threshold
    )

    # ── Altijd opslaan zodat view_coverage.py later kan laden ──
    import pathlib, json as _json
    out_dir = pathlib.Path(args.ifc_cloud).parent

    cov_ply = out_dir / "coverage_colored.ply"
    if len(colored_pts) > 0:
        import open3d as o3d
        cov_pcd = o3d.geometry.PointCloud()
        cov_pcd.points = o3d.utility.Vector3dVector(colored_pts)
        cov_pcd.colors = o3d.utility.Vector3dVector(colored_clrs)
        o3d.io.write_point_cloud(str(cov_ply), cov_pcd)

    all_pts_total = sum(p for _, _, p, _ in results)
    all_cov_total = sum(int(p * c) for _, _, p, c in results)
    built   = sum(1 for _, _, _, c in results if c >= BUILT_THRESHOLD)
    partial = sum(1 for _, _, _, c in results if PARTIAL_THRESHOLD <= c < BUILT_THRESHOLD)
    missing = sum(1 for _, _, _, c in results if c < PARTIAL_THRESHOLD)

    cov_json = out_dir / "coverage_results.json"
    saved = {
        "threshold": args.threshold,
        "ifc_cloud": str(args.ifc_cloud),
        "mast3r":    str(args.mast3r),
        "coverage_colored_ply": str(cov_ply),
        "results": [
            {"group": g, "n_elements": n, "n_points": p, "coverage": round(c, 4)}
            for g, n, p, c in results
        ],
        "summary": {
            "built":   built,
            "partial": partial,
            "missing": missing,
            "total_coverage_pct": round(all_cov_total / all_pts_total * 100, 1) if all_pts_total else 0.0,
        },
    }
    cov_json.write_text(_json.dumps(saved, indent=2))

    if args.export_json:
        pathlib.Path(args.export_json).write_text(_json.dumps(saved, indent=2))
        print(f"  Frontend JSON: {args.export_json}")

    print(f"\nOpgeslagen:")
    print(f"  {cov_ply}")
    print(f"  {cov_json}")
    print(f"Snel bekijken later: python view_coverage.py")

    print_table(results, top=args.top)

    if not args.no_view:
        visualize(args.ifc_cloud, args.mast3r, colored_pts, colored_clrs)


if __name__ == "__main__":
    main()
