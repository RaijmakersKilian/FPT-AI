#!/usr/bin/env python3
"""
ICP alignment + Coverage Analysis

Stap 1 : ICP fine-alignment       → fitness score + RMSE
Stap 2 : Verdeel IFC in segmenten → coverage per segment langs de brug-as
Stap 3 : Kleur per status         → Groen (Built) / Oranje (Partial) / Rood (Missing)
Stap 4 : Twee vensters            → overzicht + coverage-kaart

Gebruik:
    python coverage_analysis.py --ifc ifc_cloud.ply --mast3r mast3r_filtered.ply
    python coverage_analysis.py --ifc ifc_cloud.ply --mast3r mast3r_filtered.ply --segments 20 --threshold 3.0
    python coverage_analysis.py --ifc ifc_cloud.ply --mast3r mast3r_filtered.ply --no-icp
"""
import argparse
import sys
import numpy as np


# ── drempelwaarden voor status ───────────────────────────────────────────────
BUILT_THRESHOLD   = 0.80   # ≥ 80 %  → Built   (groen)
PARTIAL_THRESHOLD = 0.30   # ≥ 30 %  → Partial (oranje)
                           # < 30 %  → Missing (rood)

COLOR_BUILT   = [0.10, 0.85, 0.20]   # groen
COLOR_PARTIAL = [1.00, 0.55, 0.00]   # oranje
COLOR_MISSING = [0.90, 0.10, 0.10]   # rood
COLOR_MAST3R  = [0.55, 0.55, 0.55]   # grijs voor MASt3R in venster 1


# ── laden ────────────────────────────────────────────────────────────────────

def load(path, label=""):
    import open3d as o3d
    pcd = o3d.io.read_point_cloud(path)
    if pcd is None or len(pcd.points) == 0:
        print(f"[FOUT] Kan '{path}' niet laden.")
        sys.exit(1)
    pts = np.asarray(pcd.points)
    span = pts.ptp(axis=0)
    print(f"  {label}: {len(pts):,} punten  langste={float(np.max(span)):.2f}m")
    return pcd


# ── stap 1: ICP ──────────────────────────────────────────────────────────────

def run_icp(source, target, voxel_size, max_iter=2000):
    """
    source = MASt3R (wordt bewogen)
    target = IFC    (blijft staan)
    Geeft gealigneerde source terug + fitness/RMSE.
    Gebruikt multi-schaal ICP: eerst grof, dan fijn.
    """
    import open3d as o3d

    print(f"\n── ICP (voxel={voxel_size:.2f}m  max_iter={max_iter}) ──")

    # Multi-schaal: 3 rondes van grof naar fijn
    scales = [4.0, 2.0, 1.0]
    T = np.eye(4)

    for scale in scales:
        v = voxel_size * scale
        src_ds = source.voxel_down_sample(v)
        tgt_ds = target.voxel_down_sample(v)

        src_ds.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=v * 2, max_nn=30))
        tgt_ds.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=v * 2, max_nn=30))

        max_dist = v * 2   # klein houden zodat ICP geen verkeerde punten matcht

        result = o3d.pipelines.registration.registration_icp(
            source=src_ds,
            target=tgt_ds,
            max_correspondence_distance=max_dist,
            init=T,
            estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPlane(),
            criteria=o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=max_iter)
        )
        T = result.transformation
        print(f"  schaal×{scale:.0f}  voxel={v:.2f}m  max_dist={max_dist:.2f}m  "
              f"fitness={result.fitness:.4f}  RMSE={result.inlier_rmse:.4f}m")

    print(f"\n  Eindresultaat — Fitness: {result.fitness:.4f}   RMSE: {result.inlier_rmse:.4f}m")

    # Veiligheidscheck: als fitness te laag is, gebruik de transformatie NIET
    if result.fitness < 0.20:
        print("  [WAARSCHUWING] Fitness < 0.20 — ICP heeft de alignment verslechterd.")
        print("  Transformatie NIET toegepast. Gebruik --no-icp als pre-alignment al goed was.")
        return o3d.geometry.PointCloud(source), result.fitness, result.inlier_rmse

    aligned = o3d.geometry.PointCloud(source)
    aligned.transform(T)
    return aligned, result.fitness, result.inlier_rmse


# ── stap 2: segmenteer IFC langs brug-as ────────────────────────────────────

def segment_ifc(ifc, n_segments):
    """
    Verdeelt de IFC cloud in n_segments gelijke stukken langs de PCA-hoofdas.
    Geeft een array terug met segment-index per punt (0 … n_segments-1).
    """
    pts = np.asarray(ifc.points)
    centroid = pts.mean(axis=0)
    cov = (pts - centroid).T @ (pts - centroid) / len(pts)
    _, vecs = np.linalg.eigh(cov)
    main_axis = vecs[:, -1]                        # grootste eigenwaarde = brug-as

    proj = (pts - centroid) @ main_axis            # projectie op brug-as
    p_min, p_max = proj.min(), proj.max()
    edges = np.linspace(p_min, p_max, n_segments + 1)
    labels = np.searchsorted(edges[1:], proj)       # 0 … n_segments-1
    labels = np.clip(labels, 0, n_segments - 1)
    return labels, main_axis, proj


# ── stap 3: coverage per segment ────────────────────────────────────────────

def coverage_per_segment(ifc, mast3r_aligned, segment_labels, n_segments, threshold):
    """
    Per IFC-segment: bereken coverage = fractie punten binnen `threshold` meter
    van de dichtstbijzijnde MASt3R punt.
    """
    dists = np.asarray(ifc.compute_point_cloud_distance(mast3r_aligned))
    covered = dists < threshold

    results = []
    for seg in range(n_segments):
        mask = segment_labels == seg
        total = int(mask.sum())
        if total == 0:
            results.append((seg, 0, 0, 0.0))
            continue
        n_covered = int((covered & mask).sum())
        pct = n_covered / total
        results.append((seg, total, n_covered, pct))
    return results, covered


# ── status + kleur ───────────────────────────────────────────────────────────

def status(pct):
    if pct >= BUILT_THRESHOLD:   return "Built"
    if pct >= PARTIAL_THRESHOLD: return "Partial"
    return "Missing"


def seg_color(pct):
    if pct >= BUILT_THRESHOLD:   return COLOR_BUILT
    if pct >= PARTIAL_THRESHOLD: return COLOR_PARTIAL
    return COLOR_MISSING


# ── print tabel ──────────────────────────────────────────────────────────────

def print_table(results, bridge_len):
    seg_len = bridge_len / len(results)
    print(f"\n{'Seg':>4}  {'Van':>7}  {'Tot':>7}  {'Punten':>8}  {'Gedekt':>8}  {'%':>6}  Status")
    print("─" * 60)
    for seg, total, n_cov, pct in results:
        v = seg * seg_len
        t = (seg + 1) * seg_len
        st = status(pct)
        bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
        print(f"  {seg:2d}  {v:7.1f}m {t:7.1f}m  {total:8,}  {n_cov:8,}  {pct*100:5.1f}%  {st:<8}  {bar}")

    # Samenvatting
    all_pts  = sum(r[1] for r in results)
    all_cov  = sum(r[2] for r in results)
    n_built   = sum(1 for r in results if status(r[3]) == "Built")
    n_partial = sum(1 for r in results if status(r[3]) == "Partial")
    n_missing = sum(1 for r in results if status(r[3]) == "Missing")
    print("─" * 60)
    print(f"  Totaal: {all_cov/all_pts*100:.1f}% gedekt  |  "
          f"Built={n_built}  Partial={n_partial}  Missing={n_missing}")


# ── export ───────────────────────────────────────────────────────────────────

def export_coverage_ply(ifc, segment_labels, results, path):
    import open3d as o3d
    colors = np.zeros((len(segment_labels), 3))
    for seg, _, _, pct in results:
        colors[segment_labels == seg] = seg_color(pct)
    ifc_cov = o3d.geometry.PointCloud(ifc)
    ifc_cov.colors = o3d.utility.Vector3dVector(colors)
    o3d.io.write_point_cloud(path, ifc_cov)
    print(f"  Coverage PLY opgeslagen: {path}")


def export_coverage_json(results, bridge_len, fitness, rmse, path):
    import json
    seg_len = bridge_len / len(results)
    all_pts = sum(r[1] for r in results)
    all_cov = sum(r[2] for r in results)
    data = {
        "icp": {"fitness": round(fitness, 4), "rmse": round(rmse, 4)},
        "bridge_length_m": round(bridge_len, 2),
        "segments": [
            {
                "seg": seg,
                "from_m": round(seg * seg_len, 2),
                "to_m":   round((seg + 1) * seg_len, 2),
                "total_pts": total,
                "covered_pts": n_cov,
                "coverage_pct": round(pct * 100, 1),
                "status": status(pct),
                "color_rgb": seg_color(pct),
            }
            for seg, total, n_cov, pct in results
        ],
        "summary": {
            "built":   sum(1 for r in results if status(r[3]) == "Built"),
            "partial": sum(1 for r in results if status(r[3]) == "Partial"),
            "missing": sum(1 for r in results if status(r[3]) == "Missing"),
            "total_coverage_pct": round(all_cov / all_pts * 100, 1) if all_pts else 0.0,
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  Coverage JSON opgeslagen: {path}")


# ── vensters ─────────────────────────────────────────────────────────────────


def show_windows(ifc, mast3r_aligned, segment_labels, results):
    import open3d as o3d
    from viz_utils import show_windows as _show

    from viz_utils import color_cloud
    ifc_v = color_cloud(o3d.geometry.PointCloud(ifc), [0.0, 0.4, 1.0])
    m_v   = color_cloud(o3d.geometry.PointCloud(mast3r_aligned), list(COLOR_MAST3R))

    colors = np.zeros((len(segment_labels), 3))
    for seg, _, _, pct in results:
        colors[segment_labels == seg] = seg_color(pct)
    ifc_cov = o3d.geometry.PointCloud(ifc)
    ifc_cov.colors = o3d.utility.Vector3dVector(colors)

    print("\nVenster 1 — Blauw=IFC  Grijs=MASt3R")
    print("Venster 2 — Groen=Built  Oranje=Partial  Rood=Missing")

    _show(
        ([ifc_v, m_v], "Venster 1 — IFC (blauw) vs MASt3R (grijs)"),
        ([ifc_cov],    "Venster 2 — Coverage per segment"),
    )


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ifc",    "-i", required=True,  help="IFC point cloud (PLY)")
    parser.add_argument("--mast3r", "-m", required=True,  help="Gealigneerde MASt3R cloud (PLY)")
    parser.add_argument("--output", "-o", default="mast3r_icp.ply", help="Opslaan ICP-gealigneerde cloud")

    parser.add_argument("--no-icp",       action="store_true", help="Sla ICP over")
    parser.add_argument("--no-view",      action="store_true")
    parser.add_argument("--segments",     type=int,   default=10,  help="Aantal segmenten langs brug-as (default 10)")
    parser.add_argument("--threshold",    type=float, default=5.0, help="Coveragedrempel in meter (default 5.0)")
    parser.add_argument("--icp-voxel",    type=float, default=0.0, help="Voxelgrootte voor ICP downsample (0 = auto)")
    parser.add_argument("--export-ply",   default="coverage_result.ply",
                        help="Pad voor gekleurde coverage PLY (frontend, default: coverage_result.ply)")
    parser.add_argument("--export-json",  default="coverage_data.json",
                        help="Pad voor coverage JSON samenvatting (frontend, default: coverage_data.json)")
    args = parser.parse_args()

    try:
        import open3d as o3d
    except ImportError:
        print("Open3D niet gevonden. pip install open3d")
        sys.exit(1)

    print("=== Laden ===")
    ifc    = load(args.ifc,    "IFC   ")
    mast3r = load(args.mast3r, "MASt3R")

    ifc_span = np.asarray(ifc.points).ptp(axis=0)
    bridge_len = float(np.max(ifc_span))

    # ── ICP ──
    mast3r_aligned = mast3r
    fitness, rmse = 0.0, 0.0
    if not args.no_icp:
        voxel = args.icp_voxel if args.icp_voxel > 0 else bridge_len / 200.0
        mast3r_aligned, fitness, rmse = run_icp(mast3r, ifc, voxel_size=voxel)
        o3d.io.write_point_cloud(args.output, mast3r_aligned)
        print(f"  ICP cloud opgeslagen: {args.output}")
    else:
        print("\n── ICP overgeslagen (--no-icp) ──")

    # ── Segmentatie + coverage ──
    print(f"\n── Coverage analyse: {args.segments} segmenten  drempel={args.threshold}m ──")
    seg_labels, bridge_axis, proj = segment_ifc(ifc, args.segments)
    results, _ = coverage_per_segment(ifc, mast3r_aligned, seg_labels, args.segments, args.threshold)
    print_table(results, bridge_len)

    # ── Export voor frontend ──
    export_coverage_ply(ifc, seg_labels, results, args.export_ply)
    export_coverage_json(results, bridge_len, fitness, rmse, args.export_json)

    # ── Visualisatie ──
    if not args.no_view:
        show_windows(ifc, mast3r_aligned, seg_labels, results)


if __name__ == "__main__":
    main()
