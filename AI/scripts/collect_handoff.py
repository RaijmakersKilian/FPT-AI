"""Collect the per-date 3D artifacts into one handoff folder for the frontend team.

For each AI/outputs/runs/<date>/ with a completed comparison it gathers the
artifacts the dashboard needs and, crucially, writes a decimated browser-ready
copy of each point cloud (the raw clouds are 2-10M points and will not render
smoothly with three.js). The full-resolution clouds stay in runs/<date>/ and are
referenced by path in the README.

    AI/.venv-sam3/Scripts/python.exe AI/scripts/collect_handoff.py \
        --runs AI/outputs/runs --output AI/outputs/handoff_plys --web-points 400000
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import open3d as o3d


def decimate(src: Path, dst: Path, target: int) -> tuple[int, int]:
    pcd = o3d.io.read_point_cloud(str(src))
    n = len(pcd.points)
    if n > target:
        idx = np.random.default_rng(0).choice(n, target, replace=False)
        pcd = pcd.select_by_index(sorted(idx.tolist()))
    o3d.io.write_point_cloud(str(dst), pcd)
    return n, len(pcd.points)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=Path("AI/outputs/runs"))
    parser.add_argument("--output", type=Path, default=Path("AI/outputs/handoff_plys"))
    parser.add_argument("--web-points", type=int, default=400000)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    index = []

    for manifest_path in sorted(args.runs.glob("*/manifest.json")):
        run = manifest_path.parent
        name = run.name
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("compare", {}).get("status") != "ok":
            print(f"skip {name}: no completed comparison")
            continue

        clean = run / "03_clean" / "pointcloud_clean.ply"
        coverage = run / "04_comparison" / "model_coverage_pointcloud.ply"
        summary = run / "04_comparison" / "comparison_summary.json"

        entry: dict = {"name": name, "built_pct": manifest["compare"].get("model_built_pct")}

        if clean.exists():
            n, kept = decimate(clean, args.output / f"{name}_asbuilt_web.ply", args.web_points)
            entry["asbuilt_full_points"] = n
            entry["asbuilt_full_path"] = str(clean)
            print(f"{name}: as-built {n:,} -> {kept:,} web pts")
        if coverage.exists():
            n, kept = decimate(coverage, args.output / f"{name}_coverage_web.ply", args.web_points)
            entry["coverage_full_path"] = str(coverage)
            print(f"{name}: coverage {n:,} -> {kept:,} web pts")
        if summary.exists():
            shutil.copy2(summary, args.output / f"{name}_comparison.json")
        shutil.copy2(manifest_path, args.output / f"{name}_manifest.json")

        index.append(entry)

    # copy the across-dates artifacts
    for extra in ("progress_over_time.md", "progress_over_time.png", "INDEX.md"):
        src = args.runs / extra
        if src.exists():
            shutil.copy2(src, args.output / extra)

    _write_readme(args.output, index, args.web_points)
    (args.output / "handoff_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\ndone -> {args.output} ({len(index)} dates)")


def _write_readme(out: Path, index: list[dict], web_points: int) -> None:
    lines = [
        "# Bridge Progress Monitor - 3D handoff for the frontend team",
        "",
        "One folder with the 3D artifacts per date. The `*_web.ply` clouds are",
        f"decimated to ~{web_points:,} points so three.js can render them smoothly;",
        "the full-resolution clouds stay in `AI/outputs/runs/<date>/` (paths below).",
        "",
        "## Files per date",
        "",
        "```text",
        "<date>_asbuilt_web.ply    current reconstruction (decimated)  -> 3D viewer",
        "<date>_coverage_web.ply   final model colored built/missing   -> progress 3D",
        "<date>_comparison.json    per-section built %, distances, alignment",
        "<date>_manifest.json      headline summary for the date",
        "```",
        "",
        "Across-dates: `progress_over_time.md` / `.png`, `INDEX.md`.",
        "",
        "## Dates included",
        "",
        "| Date run | Built % | Full-res as-built cloud |",
        "|---|---|---|",
    ]
    for e in index:
        lines.append(f"| {e['name']} | {e.get('built_pct','-')} | `{e.get('asbuilt_full_path','-')}` |")
    lines += [
        "",
        "## Notes (do not over-promise)",
        "",
        "- Built % is a scale-normalized COVERAGE estimate on a largely-complete",
        "  bridge, not survey-grade construction progress. Calibrate with control",
        "  points / GPS for real units.",
        "- See AI/docs/bridge_progress_monitor_report.md for the full method + limits.",
    ]
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
