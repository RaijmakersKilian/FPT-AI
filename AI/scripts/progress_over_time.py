"""Build the progress-over-time summary from per-date pipeline runs.

Reads every AI/outputs/runs/<DDMMYYYY>/manifest.json, parses the date from the
run name, sorts chronologically, and produces:
  - progress_over_time.png   line chart of bridge built % per date
  - progress_over_time.md    table of date / built % / strict / sections

This is the deliverable the dated Google Drive videos unlock: actual
construction progress tracked across time.

    AI/.venv-sam3/Scripts/python.exe AI/scripts/progress_over_time.py \
        --runs AI/outputs/runs --output AI/outputs/runs
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=Path("AI/outputs/runs"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output_dir = args.output or args.runs

    rows = []
    for manifest_path in sorted(args.runs.glob("*/manifest.json")):
        run_name = manifest_path.parent.name
        parsed = _parse_date(run_name)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        compare = manifest.get("compare", {})
        if compare.get("status") != "ok":
            continue
        rows.append({
            "name": run_name,
            "date": parsed,
            "date_str": parsed.isoformat() if parsed else run_name,
            "built": compare.get("model_built_pct"),
            "strict": compare.get("model_built_pct_strict"),
            "non_bridge": compare.get("likely_non_bridge_pct"),
            "sections": compare.get("per_section", []),
        })

    rows.sort(key=lambda r: (r["date"] or date.max))
    if not rows:
        print("no completed comparison runs found yet")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_table(output_dir / "progress_over_time.md", rows)
    _write_chart(output_dir / "progress_over_time.png", rows)
    print(f"wrote progress_over_time.md and .png for {len(rows)} dates")
    for row in rows:
        print(f"  {row['date_str']}: built {row['built']}% (strict {row['strict']}%)")


def _parse_date(name: str):
    m = re.search(r"(\d{2})(\d{2})(\d{4})", name)
    if not m:
        return None
    day, month, year = (int(g) for g in m.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _write_table(path: Path, rows: list[dict]) -> None:
    lines = [
        "# Bridge construction progress over time",
        "",
        "Built % = fraction of the final-model points that have as-built evidence",
        "in the reconstruction (scale-normalized estimate; calibrate with a control",
        "point / GPS / Unity pose for survey-grade numbers).",
        "",
        "| Date | Built % | Strict built % | Non-bridge % |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['date_str']} | {row['built']} | {row['strict']} | {row['non_bridge']} |")
    lines += [
        "",
        "Notes:",
        "- One row per dated drone video processed through the pipeline.",
        "- A rising curve = more of the planned bridge present over time.",
        "- Dips usually mean a weaker reconstruction (less coverage that flight), not demolition.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_chart(path: Path, rows: list[dict]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("matplotlib not installed; skipping chart (table still written)")
        return

    dated = [r for r in rows if r["date"]]
    if not dated:
        return
    xs = [r["date"] for r in dated]
    built = [r["built"] for r in dated]
    strict = [r["strict"] for r in dated]

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(xs, built, "-o", color="#28c850", linewidth=2, label="built % (threshold 0.04)")
    ax.plot(xs, strict, "--o", color="#3aa0ff", linewidth=2, label="strict built % (0.02)")
    ax.set_title("Bridge construction progress over time (drone video vs final model)")
    ax.set_ylabel("estimated built %")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    for x, y in zip(xs, built):
        ax.annotate(f"{y:.0f}%", (x, y), textcoords="offset points", xytext=(0, 8), fontsize=8, ha="center")
    fig.tight_layout()
    fig.savefig(str(path), dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
