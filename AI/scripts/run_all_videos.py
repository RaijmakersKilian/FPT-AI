"""Batch the bridge AI pipeline over a whole folder of dated videos.

Point this at the folder where the Google Drive videos are downloaded and it
runs the full pipeline on each one, producing one run folder per video plus a
combined index. Designed for the "all bridge videos, ordered by date" workflow.

    AI/.venv-sam3/Scripts/python.exe AI/scripts/run_all_videos.py \
        --video-dir AI/data/raw \
        --final-model AI/data/BridgePointcloud/coverage_result.ply

Each video -> AI/outputs/runs/<video-stem>/ (REPORT.md + manifest.json + stages).
A combined AI/outputs/runs/INDEX.md lists every run with its headline numbers.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AI_DIR = SCRIPT_DIR.parent
PYTHON = sys.executable
PIPELINE = SCRIPT_DIR / "run_bridge_ai_pipeline.py"

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video-dir", type=Path, required=True)
    parser.add_argument("--final-model", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=AI_DIR / "outputs" / "runs")
    parser.add_argument("--subsample", type=int, default=15)
    parser.add_argument("--skip-existing", action="store_true", help="Skip videos that already have a REPORT.md")
    parser.add_argument("--skip-vision", action="store_true", help="Skip the slow vision stage (get the progress curve faster)")
    parser.add_argument("--continue-on-error", action="store_true", default=True)
    args = parser.parse_args()

    videos = sorted(p for p in args.video_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        raise SystemExit(f"no videos found in {args.video_dir}")
    print(f"found {len(videos)} videos in {args.video_dir}")

    results = []
    for index, video in enumerate(videos, start=1):
        name = _run_name(video)
        run_dir = args.output_root / name
        if args.skip_existing and (run_dir / "REPORT.md").exists():
            print(f"[{index}/{len(videos)}] {video.name}: already done, skipping")
            results.append((name, run_dir))
            continue

        print(f"\n[{index}/{len(videos)}] === {video.name} ===")
        cmd = [PYTHON, str(PIPELINE), "--video", str(video), "--name", name, "--subsample", str(args.subsample)]
        if args.final_model:
            cmd += ["--final-model", str(args.final_model)]
        if args.skip_vision:
            cmd += ["--skip-vision"]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            print(f"  pipeline failed for {video.name}: {exc}")
            if not args.continue_on_error:
                raise
        results.append((name, run_dir))

    _write_index(args.output_root, results)
    print(f"\nALL DONE. Index: {args.output_root / 'INDEX.md'}")


def _run_name(video: Path) -> str:
    """Clean run name from a video file, stripping double extensions like .MP4.mp4."""
    stem = video.stem
    for ext in (".MP4", ".mp4", ".MOV", ".mov", ".AVI", ".avi", ".MKV", ".mkv"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
    return _safe_name(stem)


def _safe_name(stem: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in stem).strip("_")


def _write_index(output_root: Path, results: list[tuple[str, Path]]) -> None:
    lines = [f"# Bridge AI runs index", "", f"Generated: {datetime.now():%Y-%m-%d %H:%M}", "", "| Video | Built % | Construction frames | Report |", "|---|---|---|---|"]
    for name, run_dir in results:
        manifest = _read_json(run_dir / "manifest.json")
        compare = manifest.get("compare", {})
        vision = manifest.get("vision", {})
        built = compare.get("model_built_pct", "-") if compare.get("status") == "ok" else "-"
        frames = vision.get("frames_checked", "-") if vision.get("status") == "ok" else "-"
        report = run_dir / "REPORT.md"
        report_link = f"`{report}`" if report.exists() else "(no report)"
        lines.append(f"| {name} | {built} | {frames} | {report_link} |")
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def _read_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    main()
