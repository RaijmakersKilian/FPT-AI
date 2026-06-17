#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
"""
Batch per-element-type coverage voor alle gealigneerde scans.

Stap 1 (eenmalig, ~6 min):  IFC bestand verwerken → element samples cachen
Stap 2 (snel, ~10s/scan):   Per scan KD-tree → coverage per groep berekenen

Uitvoer: coverage_results_DDMMYYYY.json in coverage_results/
Formaat identiek aan coverage_results.json (leesbaar door inspector.js).

Gebruik:
    python batch_per_type.py --ifc brug.ifc --dir coverage_results
    python batch_per_type.py --ifc brug.ifc --dir coverage_results --threshold 5.0
"""

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np


BUILT_THRESHOLD   = 0.80
PARTIAL_THRESHOLD = 0.30

NAME_MAPPING = [
    ("KCPT_BAN MAT",        "Ban mat cau",          "Road deck"),
    ("KCPT_LOP",            "Lop mat cau",          "Road deck layer"),
    ("KCPT_I24",            "Dam I",                "Support beam"),
    ("KCPT_I33",            "Dam I",                "Support beam"),
    ("KCPD_XA MU",          "Xa mu",                "Column cap"),
    ("KCPD_COC",            "Coc mong",             "Pile"),
    ("KCPD_THAN TRU",       "Than tru",             "Pier body"),
    ("KCPD_THAN MO",        "Than mo",              "Abutment body"),
    ("KCPT_K101",           "Ket cau K101",         "Road-pier connector"),
    ("KCPT_Ki",             "Cau kien Ki",          "Road support element"),
    ("KCPT_DOT TREN",       "Dot tren",             "Upper segment"),
    ("KCPD_BTL",            "Ban tam lot",          "Bottom slab"),
    ("KCPD_BE TRU",         "Be tong tru",          "Pier concrete"),
    ("KCPD_BE MO",          "Be tong mo",           "Abutment concrete"),
    ("KCPD_TUONG",          "Tuong dau cau",        "End wall"),
    ("KCK_BAN QUA",         "Ban qua do",           "Transition slab"),
    ("KCK_TUONG CHAN",       "Tuong chan",           "Retaining wall"),
    ("KCPT_GO LAN CAN",     "Go lan can",           "Railing post"),
    ("LOAI1_Thep hop",      "Thep hop lan can",     "Railing bar"),
    ("KCK_M2-BAN QUA DO",   "Be tong lot",          "Approach concrete"),
]

# Vietnamese names (with diacritics) for display
VN_NAMES = {
    "Road deck":            "Ban mat cau",
    "Road deck layer":      "Lop mat cau",
    "Support beam":         "Dam I",
    "Column cap":           "Xa mu",
    "Pile":                 "Coc mong",
    "Pier body":            "Than tru",
    "Abutment body":        "Than mo",
    "Road-pier connector":  "Ket cau K101",
    "Road support element": "Cau kien Ki",
    "Upper segment":        "Dot tren",
    "Bottom slab":          "Ban tam lot",
    "Pier concrete":        "Be tong tru",
    "Abutment concrete":    "Be tong mo",
    "End wall":             "Tuong dau cau",
    "Transition slab":      "Ban qua do",
    "Retaining wall":       "Tuong chan",
    "Railing post":         "Go lan can",
    "Railing bar":          "Thep hop lan can",
    "Approach concrete":    "Be tong lot",
}

# Vietnamese names WITH diacritics for the JSON (readable by inspector)
VN_DISPLAY = {
    "Road deck":            "Bản mặt cầu",
    "Road deck layer":      "Lớp mặt cầu",
    "Support beam":         "Dầm I",
    "Column cap":           "Xà mũ",
    "Pile":                 "Cọc móng",
    "Pier body":            "Thân trụ",
    "Abutment body":        "Thân mố",
    "Road-pier connector":  "Kết cấu K101",
    "Road support element": "Cấu kiện Ki",
    "Upper segment":        "Đốt trên",
    "Bottom slab":          "Bản tấm lót",
    "Pier concrete":        "Bê tông trụ",
    "Abutment concrete":    "Bê tông mố",
    "End wall":             "Tường đầu cầu",
    "Transition slab":      "Bản quá độ",
    "Retaining wall":       "Tường chắn",
    "Railing post":         "Gờ lan can",
    "Railing bar":          "Thép hộp lan can",
    "Approach concrete":    "Bê tông lót",
}


def name_to_group(name, obj_type):
    raw = (name or obj_type or "").strip()
    raw_upper = raw.upper()
    for keyword, _, label_en in NAME_MAPPING:
        if keyword.upper() in raw_upper:
            vn = VN_DISPLAY.get(label_en, label_en)
            return f"{vn}  [{label_en}]"
    prefix = re.sub(r'[\s_\-\.]*\d+[\s_\-\.]*$', '', raw).strip()
    return prefix if prefix else "Onbekend"


def status(pct):
    if pct >= BUILT_THRESHOLD:   return "Built"
    if pct >= PARTIAL_THRESHOLD: return "Partial"
    return "Missing"


CACHE_FILE = "ifc_element_cache.npz"


def build_or_load_cache(ifc_path: str, script_dir: Path, pts_per_element=200):
    cache_path = script_dir / CACHE_FILE
    if cache_path.exists():
        print(f"Cache laden: {cache_path.name}")
        data = np.load(str(cache_path), allow_pickle=True)
        groups = data["groups"].item()
        print(f"  {len(groups)} groepen geladen uit cache")
        return groups

    print(f"IFC verwerken: {ifc_path}  (dit duurt ~6 min)")
    try:
        import ifcopenshell
        import ifcopenshell.geom
        import trimesh
    except ImportError as e:
        print(f"[FOUT] Ontbrekend pakket: {e}\npip install ifcopenshell trimesh")
        sys.exit(1)

    model    = ifcopenshell.open(ifc_path)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    iterator = ifcopenshell.geom.iterator(settings, model)

    groups = {}
    count  = 0
    t0     = time.time()

    if not iterator.initialize():
        print("[FOUT] Iterator kan niet starten.")
        sys.exit(1)

    while True:
        shape = iterator.get()
        geo   = shape.geometry
        try:
            el    = model.by_id(shape.id)
            name  = getattr(el, "Name", None) or ""
            obj_t = getattr(el, "ObjectType", None) or ""
            group = name_to_group(name, obj_t)
        except Exception:
            group = "Onbekend"

        verts = np.array(geo.verts, dtype=np.float64).reshape(-1, 3)
        faces = np.array(geo.faces, dtype=np.int64).reshape(-1, 3)

        if len(verts) > 0 and len(faces) > 0:
            try:
                mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
                if mesh.area > 1e-6:
                    n   = min(pts_per_element, max(10, int(mesh.area / 0.5)))
                    pts, _ = trimesh.sample.sample_surface(mesh, n)
                    g = groups.setdefault(group, {"pts": [], "count": 0})
                    g["pts"].append(pts)
                    g["count"] += 1
            except Exception:
                pass

        count += 1
        if count % 200 == 0:
            print(f"  {count} elementen  ({time.time()-t0:.0f}s)  groepen: {len(groups)}")

        if not iterator.next():
            break

    print(f"  Klaar: {count} elementen in {time.time()-t0:.0f}s  groepen: {len(groups)}")

    # Consolideer pts per groep
    consolidated = {}
    for grp, data in groups.items():
        if data["pts"]:
            consolidated[grp] = {
                "pts":   np.vstack(data["pts"]),
                "count": data["count"],
            }

    np.savez_compressed(str(cache_path), groups=consolidated)
    print(f"Cache opgeslagen: {cache_path.name}")
    return consolidated


def coverage_for_scan(groups: dict, scan_path: Path, threshold: float):
    from scipy.spatial import KDTree
    import open3d as o3d

    pcd  = o3d.io.read_point_cloud(str(scan_path))
    pts  = np.asarray(pcd.points)
    if len(pts) == 0:
        return []

    kd = KDTree(pts)
    results = []
    for group, data in sorted(groups.items()):
        all_pts  = data["pts"]
        dists, _ = kd.query(all_pts)
        covered  = float((dists < threshold).sum()) / len(dists)
        results.append({
            "group":      group,
            "n_elements": int(data["count"]),
            "n_points":   len(all_pts),
            "coverage":   round(covered, 4),
        })

    results.sort(key=lambda r: -r["coverage"])
    return results


def raw_digits(path: Path) -> str:
    m = re.search(r"(\d{8})", path.stem)
    return m.group(1) if m else path.stem


def main():
    parser = argparse.ArgumentParser(description="Batch per-type coverage voor alle gealigneerde scans")
    parser.add_argument("--ifc",       "-i", default="brug.ifc",
                        help="IFC bestand (default: brug.ifc)")
    parser.add_argument("--dir",       "-d", default="coverage_results",
                        help="Map met icp_*.ply scans EN uitvoermap (default: coverage_results)")
    parser.add_argument("--threshold", "-t", type=float, default=5.0,
                        help="Coveragedrempel in meter (default: 5.0)")
    parser.add_argument("--rebuild-cache", action="store_true",
                        help="Cache opnieuw opbouwen, ook als die al bestaat")
    args = parser.parse_args()

    try:
        import open3d as o3d
        from scipy.spatial import KDTree
    except ImportError as e:
        print(f"[FOUT] Ontbrekend: {e}\npip install open3d scipy")
        sys.exit(1)

    script_dir = Path(__file__).parent
    ifc_path   = Path(args.ifc) if Path(args.ifc).is_absolute() else script_dir / args.ifc
    out_dir    = Path(args.dir) if Path(args.dir).is_absolute()  else script_dir / args.dir

    if not ifc_path.exists():
        print(f"[FOUT] IFC bestand niet gevonden: {ifc_path}")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    cache_path = script_dir / CACHE_FILE
    if args.rebuild_cache and cache_path.exists():
        cache_path.unlink()

    # Stap 1: IFC elementen verwerken / cache laden
    groups = build_or_load_cache(str(ifc_path), script_dir)

    # Stap 2: Per scan coverage berekenen
    scans = sorted(f for f in out_dir.glob("icp_*.ply") if re.search(r"\d{8}", f.stem))
    print(f"\n{len(scans)} scans gevonden in {out_dir.name}/")
    print(f"Threshold: {args.threshold}m\n")

    for i, scan_path in enumerate(scans, 1):
        key = raw_digits(scan_path)
        print(f"[{i}/{len(scans)}] {scan_path.name} ...", end=" ", flush=True)
        t0 = time.time()

        results = coverage_for_scan(groups, scan_path, args.threshold)

        built   = sum(1 for r in results if r["coverage"] >= BUILT_THRESHOLD)
        partial = sum(1 for r in results if PARTIAL_THRESHOLD <= r["coverage"] < BUILT_THRESHOLD)
        missing = sum(1 for r in results if r["coverage"] < PARTIAL_THRESHOLD)
        total_pts = sum(r["n_points"] for r in results)
        total_cov = sum(int(r["n_points"] * r["coverage"]) for r in results)
        total_pct = round(total_cov / total_pts * 100, 1) if total_pts else 0.0

        payload = {
            "threshold": args.threshold,
            "results":   results,
            "summary": {
                "built":              built,
                "partial":            partial,
                "missing":            missing,
                "total_coverage_pct": total_pct,
            },
        }

        out_json = out_dir / f"coverage_results_{key}.json"
        out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        elapsed = time.time() - t0
        print(f"{total_pct:.1f}%  Built={built} Partial={partial} Missing={missing}  ({elapsed:.1f}s)")
        print(f"  -> {out_json.name}")

    print(f"\nKlaar! {len(scans)} scans verwerkt.")


if __name__ == "__main__":
    main()
