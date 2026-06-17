#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
"""
Batch Coverage Analysis – verwerkt alle point clouds in een map tegen de IFC brug.

Voor elke gedateerde scan (bijv. pointcloud_27122023.ply) wordt:
  - ICP alignment uitgevoerd tegen de IFC brug
  - coverage per segment berekend
  - coverage_<datum>.ply + coverage_<datum>.json opgeslagen
  - twee vensters getoond: overlap + coverage-kleuren (sluit om door te gaan)

Tot slot wordt een tijdlijn-JSON gemaakt (timeline.json) met de coverage-ontwikkeling.

Gebruik:
    python batch_coverage.py --ifc ifc_straight.ply --dir Allpointclouds
    python batch_coverage.py --ifc ifc_straight.ply --dir Allpointclouds --output results --segments 15 --threshold 4.0
    python batch_coverage.py --ifc ifc_straight.ply --dir Allpointclouds --no-icp
    python batch_coverage.py --ifc ifc_straight.ply --dir Allpointclouds --no-view
"""

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime

import numpy as np

# ── hergebruik functies uit coverage_analysis + filter_pipeline ──────────────
sys.path.insert(0, str(Path(__file__).parent))
from coverage_analysis import (
    load, run_icp, segment_ifc, coverage_per_segment,
    status, seg_color, export_coverage_ply, export_coverage_json, print_table,
)
from filter_pipeline import (
    step_pca_align, step_bbox_crop, step_sor, step_ror,
)
from viz_utils import show_windows, color_cloud


def raw_digits_from_filename(path: Path) -> str:
    """Geeft de ruwe cijfers terug uit de bestandsnaam, bijv. pointcloud_27122023.ply → '27122023'."""
    m = re.search(r"(\d{8})", path.stem)
    return m.group(1) if m else path.stem


def parse_date_from_filename(path: Path) -> str:
    """Leesbare datum voor weergave, bijv. pointcloud_27122023.ply → '2023-12-27'."""
    raw = raw_digits_from_filename(path)
    for fmt in ("%d%m%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw


def show_scan_windows(ifc, aligned, seg_labels, results, date_str: str):
    """
    Twee vensters voor één scan:
      Venster 1 — Blauw=IFC  Grijs=scan (hoe ze overlappen)
      Venster 2 — Groen=Built  Oranje=Partial  Rood=Missing (coverage van de IFC)
    """
    import open3d as o3d

    # Venster 1: overlap
    ifc_blue = color_cloud(o3d.geometry.PointCloud(ifc), [0.0, 0.4, 1.0])
    scan_grey = color_cloud(o3d.geometry.PointCloud(aligned), [0.55, 0.55, 0.55])
    if aligned.has_colors():
        # behoud originele scan-kleuren als die er zijn
        scan_grey = o3d.geometry.PointCloud(aligned)

    # Venster 2: coverage-kleuren op de IFC
    colors = np.zeros((len(seg_labels), 3))
    for seg, _, _, pct in results:
        colors[seg_labels == seg] = seg_color(pct)
    ifc_cov = o3d.geometry.PointCloud(ifc)
    ifc_cov.colors = o3d.utility.Vector3dVector(colors)

    print(f"\n  Venster 1 — Blauw=IFC  Grijs=Scan ({date_str})")
    print(f"  Venster 2 — Groen=Built  Oranje=Partial  Rood=Missing")
    print(f"  [Sluit beide vensters om door te gaan naar de volgende scan]\n")

    show_windows(
        ([ifc_blue, scan_grey], f"{date_str} — IFC (blauw) vs Scan (grijs)"),
        ([ifc_cov],             f"{date_str} — Coverage: Groen=Built  Oranje=Partial  Rood=Missing"),
    )


def process_cloud(ifc_path: str, scan_path: Path, out_dir: Path,
                  n_segments: int, threshold: float, voxel: float,
                  no_icp: bool, no_view: bool) -> dict | None:
    """
    Verwerkt één scan en geeft een dict terug met resultaten voor de tijdlijn.
    Pipeline: PCA-align → bbox-crop → SOR → ICP → coverage
    """
    import open3d as o3d

    date_str  = parse_date_from_filename(scan_path)   # leesbaar (voor weergave + JSON)
    file_key  = raw_digits_from_filename(scan_path)   # ruwe cijfers (voor bestandsnamen)
    print(f"\n{'='*60}")
    print(f"  Scan: {scan_path.name}  →  datum: {date_str}")
    print(f"{'='*60}")

    ifc  = load(ifc_path,        "IFC  ")
    scan = load(str(scan_path),  "Scan ")

    ifc_span   = np.asarray(ifc.points).ptp(axis=0)
    bridge_len = float(np.max(ifc_span))

    # ── Stap 1: PCA alignment + schaling + Z-flip (zelfde als filter_pipeline) ──
    print("\n── Pre-processing ──")
    filtered = step_pca_align(scan, ifc)
    filtered = step_bbox_crop(filtered, ifc, crop_scale=1.2)
    filtered = step_sor(filtered, nb_neighbors=20, std_ratio=2.0)

    # ── Stap 2: ICP fine-alignment ──
    aligned = filtered
    fitness, rmse = 0.0, 0.0
    if not no_icp:
        v = voxel if voxel > 0 else bridge_len / 200.0
        aligned, fitness, rmse = run_icp(filtered, ifc, voxel_size=v)
        icp_out = out_dir / f"icp_{file_key}.ply"
        o3d.io.write_point_cloud(str(icp_out), aligned)
        print(f"  ICP cloud opgeslagen: {icp_out.name}")
    else:
        print("  ICP overgeslagen (--no-icp)")

    # ── Coverage ──
    print(f"\n── Coverage: {n_segments} segmenten  drempel={threshold}m ──")
    seg_labels, _, _ = segment_ifc(ifc, n_segments)
    results, _       = coverage_per_segment(ifc, aligned, seg_labels, n_segments, threshold)
    print_table(results, bridge_len)

    # ── Export ──
    ply_out  = out_dir / f"coverage_{file_key}.ply"
    json_out = out_dir / f"coverage_{file_key}.json"
    export_coverage_ply(ifc, seg_labels, results, str(ply_out))
    export_coverage_json(results, bridge_len, fitness, rmse, str(json_out))

    # ── Visualisatie ──
    if not no_view:
        show_scan_windows(ifc, aligned, seg_labels, results, date_str)

    # Samenvatting voor tijdlijn
    all_pts = sum(r[1] for r in results)
    all_cov = sum(r[2] for r in results)
    return {
        "date":               date_str,
        "file":               scan_path.name,
        "icp_fitness":        round(fitness, 4),
        "icp_rmse_m":         round(rmse, 4),
        "total_coverage_pct": round(all_cov / all_pts * 100, 1) if all_pts else 0.0,
        "built":              sum(1 for r in results if status(r[3]) == "Built"),
        "partial":            sum(1 for r in results if status(r[3]) == "Partial"),
        "missing":            sum(1 for r in results if status(r[3]) == "Missing"),
        "coverage_ply":       ply_out.name,
        "coverage_json":      json_out.name,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Batch coverage analyse voor alle scans vs IFC brug"
    )
    parser.add_argument("--ifc",       "-i", required=True,
                        help="IFC point cloud (PLY), bijv. ifc_straight.ply")
    parser.add_argument("--dir",       "-d", default="Allpointclouds",
                        help="Map met gedateerde scan PLY-bestanden (default: Allpointclouds)")
    parser.add_argument("--output",    "-o", default="coverage_results",
                        help="Uitvoermap voor resultaten (default: coverage_results)")
    parser.add_argument("--segments",  type=int,   default=10,
                        help="Segmenten langs brug-as (default: 10)")
    parser.add_argument("--threshold", type=float, default=5.0,
                        help="Coveragedrempel in meter (default: 5.0)")
    parser.add_argument("--icp-voxel", type=float, default=0.0,
                        help="Voxelgrootte voor ICP (0 = auto)")
    parser.add_argument("--no-icp",   action="store_true",
                        help="Sla ICP over (scans zijn al gealigneerd)")
    parser.add_argument("--no-view",  action="store_true",
                        help="Geen visualisatievensters tonen (alleen bestanden exporteren)")
    parser.add_argument("--pattern",  default="*.ply",
                        help="Glob-patroon voor scan-bestanden (default: *.ply)")
    args = parser.parse_args()

    try:
        import open3d as o3d  # noqa: F401
    except ImportError:
        print("Open3D niet gevonden. pip install open3d")
        sys.exit(1)

    # ── Paden ──
    script_dir = Path(__file__).parent
    ifc_path   = Path(args.ifc) if Path(args.ifc).is_absolute() else script_dir / args.ifc
    scan_dir   = Path(args.dir) if Path(args.dir).is_absolute()  else script_dir / args.dir
    out_dir    = Path(args.output) if Path(args.output).is_absolute() else script_dir / args.output

    if not ifc_path.exists():
        print(f"[FOUT] IFC bestand niet gevonden: {ifc_path}")
        sys.exit(1)
    if not scan_dir.is_dir():
        print(f"[FOUT] Scanmap niet gevonden: {scan_dir}")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Bestanden verzamelen + sorteren op datum ──
    scans = sorted(scan_dir.glob(args.pattern))
    if not scans:
        print(f"[FOUT] Geen bestanden gevonden in {scan_dir} met patroon '{args.pattern}'")
        sys.exit(1)

    print(f"\nIFC:     {ifc_path}")
    print(f"Scans:   {scan_dir}  ({len(scans)} bestanden)")
    print(f"Uitvoer: {out_dir}")
    icp_info = "geen ICP" if args.no_icp else f"ICP voxel={args.icp_voxel or 'auto'}"
    print(f"Instellingen: {args.segments} segmenten  drempel={args.threshold}m  {icp_info}")
    if not args.no_view:
        print(f"Visualisatie: AAN  (sluit vensters per scan om door te gaan)")

    # ── Verwerk elke scan ──
    timeline = []
    errors   = []
    for i, scan_path in enumerate(scans, 1):
        print(f"\n[{i}/{len(scans)}]", end="")
        try:
            entry = process_cloud(
                ifc_path   = str(ifc_path),
                scan_path  = scan_path,
                out_dir    = out_dir,
                n_segments = args.segments,
                threshold  = args.threshold,
                voxel      = args.icp_voxel,
                no_icp     = args.no_icp,
                no_view    = args.no_view,
            )
            if entry:
                timeline.append(entry)
        except Exception as exc:
            print(f"\n[FOUT] {scan_path.name}: {exc}")
            errors.append({"file": scan_path.name, "error": str(exc)})

    # ── Tijdlijn JSON ──
    timeline_path = out_dir / "timeline.json"
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump({
            "ifc_reference": str(ifc_path),
            "settings": {
                "segments":  args.segments,
                "threshold": args.threshold,
                "icp":       not args.no_icp,
            },
            "entries": sorted(timeline, key=lambda e: e["date"]),
            "errors":  errors,
        }, f, indent=2)

    # ── Eindsamenvatting ──
    print(f"\n{'='*60}")
    print(f"  BATCH KLAAR  —  {len(timeline)} scans verwerkt  |  {len(errors)} fout(en)")
    print(f"{'='*60}")
    if timeline:
        print(f"\n  {'Datum':<12}  {'Coverage':>10}  {'Built':>6}  {'Partial':>8}  {'Missing':>8}  {'ICP fit':>8}")
        print(f"  {'-'*60}")
        for e in sorted(timeline, key=lambda x: x["date"]):
            print(f"  {e['date']:<12}  {e['total_coverage_pct']:>9.1f}%  "
                  f"{e['built']:>6}  {e['partial']:>8}  {e['missing']:>8}  "
                  f"{e['icp_fitness']:>8.4f}")
    if errors:
        print(f"\n  Fouten:")
        for err in errors:
            print(f"    {err['file']}: {err['error']}")
    print(f"\n  Tijdlijn opgeslagen: {timeline_path}")


if __name__ == "__main__":
    main()
