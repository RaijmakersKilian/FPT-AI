"""One-command bridge AI pipeline: video in, progress report out.

Wraps every AI step we built into a single product-style command so the client
does not have to run the stages by hand:

    drone video
      -> 1. extract frames + mask moving traffic (SAM3)
      -> 2. MASt3R-SLAM reconstruction (runs in WSL)
      -> 3. clean point cloud (remove blackout + smear/noise)
      -> 4. compare to the final bridge model (per-section progress)
      -> 5. vision check (segment bridge in sample frames, remove background)
      -> 6. write REPORT.md

Everything lands in one run folder. Each stage is resumable and skippable, so a
re-run with --skip-slam reuses the existing cloud, etc.

Run with the Windows AI/.venv-sam3 environment (it has SAM3, trimesh, scipy):

    AI/.venv-sam3/Scripts/python.exe AI/scripts/run_bridge_ai_pipeline.py \
        --video AI/data/raw/BridgeVid1-271223.mp4 \
        --final-model AI/data/BridgePointcloud/coverage_result.ply \
        --name bridgevid1_demo
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AI_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(AI_DIR / "src"))

PYTHON = sys.executable
SLAM_DIR = AI_DIR / ".external" / "MASt3R-SLAM"
SLAM_SCRIPT = SCRIPT_DIR / "run_mast3r_bridge1_masked.sh"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--final-model", type=Path, default=None, help="Completed bridge model/cloud for the comparison (.ply/.glb)")
    parser.add_argument("--name", default=None, help="Run name (default: video stem + timestamp)")
    parser.add_argument("--output-root", type=Path, default=AI_DIR / "outputs" / "runs")
    parser.add_argument("--subsample", type=int, default=15, help="Use every Nth video frame")
    parser.add_argument("--vision-frames", type=int, default=6, help="How many evenly spaced frames to run the vision check on")
    parser.add_argument("--wsl-distro", default="Ubuntu-24.04")
    parser.add_argument("--anchor-current", type=Path, default=None, help="Optional anchor JSON to lock bridge orientation (pick_control_points.py)")
    parser.add_argument("--anchor-reference", type=Path, default=None)
    parser.add_argument("--skip-mask", action="store_true")
    parser.add_argument("--skip-slam", action="store_true", help="Reuse an existing 02_slam/pointcloud.ply")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--skip-compare", action="store_true")
    parser.add_argument("--skip-vision", action="store_true")
    args = parser.parse_args()

    if not args.video.exists():
        raise SystemExit(f"video not found: {args.video}")

    name = args.name or f"{args.video.stem}_{datetime.now():%Y%m%d_%H%M%S}"
    run_dir = (args.output_root / name).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(run_dir)
    manifest.setdefault("video", str(args.video))
    manifest.setdefault("name", name)
    manifest["subsample"] = args.subsample
    print(f"== Bridge AI pipeline ==\nrun: {run_dir}\n")

    frames_dir = run_dir / "01_frames"
    masked_dir = frames_dir / "masked"
    cloud_dir = run_dir / "02_slam"
    clean_dir = run_dir / "03_clean"
    compare_dir = run_dir / "04_comparison"
    vision_dir = run_dir / "05_vision"

    if not args.skip_mask:
        _stage_mask(args, frames_dir, manifest)
    if not args.skip_slam:
        _stage_slam(args, masked_dir, cloud_dir, name, manifest)
    if not args.skip_clean:
        _stage_clean(cloud_dir, clean_dir, manifest)
    if args.final_model and not args.skip_compare:
        _stage_compare(args, clean_dir, compare_dir, manifest)
    if not args.skip_vision:
        _stage_vision(args, masked_dir, frames_dir, vision_dir, manifest)

    _save_manifest(run_dir, manifest)
    _write_report(run_dir, manifest)
    print(f"\nDONE. Report: {run_dir / 'REPORT.md'}")


def _stage_mask(args, frames_dir: Path, manifest: dict) -> None:
    print("[1/6] Extracting + masking frames (SAM3)...")
    start = time.time()
    _run([
        PYTHON, str(SCRIPT_DIR / "mask_dynamic_objects.py"),
        "--video", str(args.video), "--output", str(frames_dir),
        "--subsample", str(args.subsample),
    ])
    summary = _read_json(frames_dir / "masking_summary.json")
    manifest["mask"] = {
        "frames": summary.get("frames_written"),
        "mean_masked_pct": round((summary.get("mean_masked_pixel_ratio") or 0) * 100, 2),
        "seconds": round(time.time() - start),
    }


def _stage_slam(args, masked_dir: Path, cloud_dir: Path, name: str, manifest: dict) -> None:
    print("[2/6] MASt3R-SLAM reconstruction (WSL)...")
    if not masked_dir.exists():
        manifest["slam"] = {"status": "skipped", "reason": "no masked frames"}
        print("  no masked frames; skipping")
        return
    start = time.time()
    save_as = f"pipeline_{name}"
    frames_wsl = _to_wsl(masked_dir)
    script_wsl = _to_wsl(SLAM_SCRIPT)
    cmd = [
        "wsl", "-d", args.wsl_distro, "-u", "root", "-e", "bash", "-lc",
        f"FRAMES='{frames_wsl}' SAVE_AS='{save_as}' bash '{script_wsl}'",
    ]
    try:
        _run(cmd)
    except subprocess.CalledProcessError as exc:
        manifest["slam"] = {"status": "failed", "error": str(exc)}
        print(f"  SLAM failed: {exc}")
        return

    logs_dir = SLAM_DIR / "logs" / save_as
    plys = sorted(logs_dir.glob("*.ply"), key=lambda p: p.stat().st_size, reverse=True)
    if not plys:
        manifest["slam"] = {"status": "failed", "error": f"no .ply in {logs_dir}"}
        print(f"  no point cloud produced in {logs_dir}")
        return
    cloud_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plys[0], cloud_dir / "pointcloud.ply")
    traj = next(logs_dir.glob("*.txt"), None)
    if traj:
        shutil.copy2(traj, cloud_dir / "trajectory.txt")
    manifest["slam"] = {"status": "ok", "points": _count_ply_vertices(cloud_dir / "pointcloud.ply"), "seconds": round(time.time() - start)}


def _stage_clean(cloud_dir: Path, clean_dir: Path, manifest: dict) -> None:
    cloud = cloud_dir / "pointcloud.ply"
    if not cloud.exists():
        manifest["clean"] = {"status": "skipped", "reason": "no point cloud"}
        print("[3/6] Cleaning skipped (no point cloud)")
        return
    print("[3/6] Cleaning point cloud (blackout + smear/noise)...")
    clean_dir.mkdir(parents=True, exist_ok=True)
    filtered = clean_dir / "pointcloud_filtered.ply"
    clean = clean_dir / "pointcloud_clean.ply"
    _run([PYTHON, str(SCRIPT_DIR / "remove_black_points.py"), "--input", str(cloud), "--output", str(filtered), "--threshold", "20"])
    _run([PYTHON, str(SCRIPT_DIR / "clean_pointcloud.py"), "--input", str(filtered), "--output", str(clean)])
    stats = _read_json(clean.with_suffix(".clean_stats.json"))
    manifest["clean"] = {"status": "ok", "points_out": stats.get("points_out"), "removed_pct": stats.get("removed_pct")}


def _stage_compare(args, clean_dir: Path, compare_dir: Path, manifest: dict) -> None:
    from ftp_ai.model_comparison import compare_reconstruction_to_model

    cloud = clean_dir / "pointcloud_clean.ply"
    if not cloud.exists():
        manifest["compare"] = {"status": "skipped", "reason": "no clean cloud"}
        print("[4/6] Comparison skipped (no clean cloud)")
        return
    print("[4/6] Comparing to final bridge model (per-section)...")
    summary = compare_reconstruction_to_model(
        current_ply=cloud,
        final_model=args.final_model,
        output_dir=compare_dir,
        anchor_current=args.anchor_current,
        anchor_reference=args.anchor_reference,
    )
    progress = summary["progress_estimate"]
    manifest["compare"] = {
        "status": "ok",
        "model_built_pct": progress["model_built_pct"],
        "model_built_pct_strict": progress["model_built_pct_strict"],
        "likely_non_bridge_pct": summary["likely_non_bridge_current_pct"],
        "alignment_method": summary["alignment"].get("method", "auto_pca_icp"),
        "per_section": [{"section": e["section"], "built_pct": e["built_pct"]} for e in progress["per_section"]],
    }


def _stage_vision(args, masked_dir: Path, frames_dir: Path, vision_dir: Path, manifest: dict) -> None:
    raw_dir = frames_dir / "frames"
    source_dir = raw_dir if raw_dir.exists() else masked_dir
    if not source_dir.exists():
        manifest["vision"] = {"status": "skipped", "reason": "no frames"}
        print("[5/6] Vision check skipped (no frames)")
        return
    print("[5/6] Vision check (segment bridge, remove background)...")
    vision_dir.mkdir(parents=True, exist_ok=True)
    frames = sorted(source_dir.glob("frame_*.png"))
    if not frames:
        manifest["vision"] = {"status": "skipped", "reason": "no frame_*.png"}
        return
    picks = _evenly_spaced(frames, args.vision_frames)

    model_render = vision_dir / "model_render.jpg"
    if args.final_model and str(args.final_model).lower().endswith((".glb", ".gltf", ".obj")):
        try:
            _run([PYTHON, str(SCRIPT_DIR / "render_bridge_model.py"), "--model", str(args.final_model), "--output", str(model_render), "--azimuth", "35", "--elevation", "25"])
        except subprocess.CalledProcessError:
            model_render = None
    else:
        model_render = None

    results = []
    for frame in picks:
        out = vision_dir / frame.stem
        try:
            _run([PYTHON, str(SCRIPT_DIR / "segment_bridge_frame.py"), "--image", str(frame), "--output", str(out)])
        except subprocess.CalledProcessError:
            continue
        summary = _read_json(out / "segmentation_summary.json")
        bridge_pct = summary.get("bridge_pixel_pct", 0)
        results.append({"frame": frame.name, "bridge_pct": bridge_pct, "dir": str(out)})
        if model_render and (out / "bridge_only.jpg").exists():
            _run([
                PYTHON, str(SCRIPT_DIR / "build_vision_comparison.py"),
                "--frame", str(frame),
                "--overlay", str(out / "structures_overlay.jpg"),
                "--bridge-only", str(out / "bridge_only.jpg"),
                "--model-render", str(model_render),
                "--output", str(out / "comparison_figure.jpg"),
            ])
    # Whole-flyover construction overlay video next to the finished model.
    overlay_video = vision_dir / "construction_overlay.mp4"
    overlay_status = "skipped"
    try:
        cmd = [PYTHON, str(SCRIPT_DIR / "construction_overlay_video.py"), "--frames", str(source_dir), "--output", str(overlay_video), "--fps", "8"]
        if model_render:
            cmd += ["--model-render", str(model_render)]
        _run(cmd)
        overlay_status = "ok"
    except subprocess.CalledProcessError:
        overlay_status = "failed"

    results.sort(key=lambda r: r["bridge_pct"], reverse=True)
    manifest["vision"] = {
        "status": "ok",
        "frames_checked": len(results),
        "best": results[:3],
        "overlay_video": str(overlay_video) if overlay_status == "ok" else None,
    }


def _write_report(run_dir: Path, manifest: dict) -> None:
    lines = [
        f"# Bridge AI Report - {manifest.get('name')}",
        "",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
        f"Video: `{manifest.get('video')}`",
        f"Frame subsample: every {manifest.get('subsample')}th",
        "",
        "## Pipeline stages",
        "",
    ]
    mask = manifest.get("mask")
    if mask:
        lines.append(f"- **Frames + masking**: {mask.get('frames')} frames, mean {mask.get('mean_masked_pct')}% pixels masked (traffic removed)")
    slam = manifest.get("slam")
    if slam:
        if slam.get("status") == "ok":
            lines.append(f"- **MASt3R-SLAM reconstruction**: {slam.get('points'):,} points")
        else:
            lines.append(f"- **MASt3R-SLAM reconstruction**: {slam.get('status')} ({slam.get('error', slam.get('reason', ''))})")
    clean = manifest.get("clean")
    if clean and clean.get("status") == "ok":
        lines.append(f"- **Cleaning**: {clean.get('points_out'):,} points kept ({clean.get('removed_pct')}% removed)")

    compare = manifest.get("compare")
    if compare and compare.get("status") == "ok":
        lines += [
            "",
            "## Progress vs final model",
            "",
            f"- **Bridge built (estimate): {compare['model_built_pct']}%** (strict {compare['model_built_pct_strict']}%)",
            f"- Likely non-bridge points in scan: {compare['likely_non_bridge_pct']}%",
            f"- Alignment: {compare['alignment_method']}",
            "",
            "| Section | Built % |",
            "|---|---|",
        ]
        for entry in compare["per_section"]:
            lines.append(f"| {entry['section']} | {entry['built_pct']}% |")

    vision = manifest.get("vision")
    if vision and vision.get("status") == "ok":
        lines += ["", "## Vision check (active construction isolated)", ""]
        if vision.get("overlay_video"):
            lines.append(f"- **Whole-flyover construction overlay video**: `{vision['overlay_video']}`")
        for item in vision.get("best", []):
            fig = Path(item["dir"]) / "comparison_figure.jpg"
            tag = f" - figure: `{fig}`" if fig.exists() else ""
            lines.append(f"- `{item['frame']}`: construction covers {item['bridge_pct']}% of frame{tag}")

    lines += [
        "",
        "## Caveats",
        "",
        "- Progress % is a scale-normalized estimate, not survey-grade. Use an anchor pick or GPS/Unity pose for calibrated numbers.",
        "- Vision segmentation is viewpoint-dependent; oblique side views work best.",
        "- Quality depends on the capture: planned, repeatable, high-overlap flights give the best result.",
        "",
        "See `AI/docs/ai_handoff_for_claude.md` for the full method background.",
    ]
    (run_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


# ---- helpers ---------------------------------------------------------------

def _run(cmd: list[str]) -> None:
    print("  $ " + " ".join(str(c) for c in cmd[:6]) + (" ..." if len(cmd) > 6 else ""))
    subprocess.run(cmd, check=True)


def _to_wsl(path: Path) -> str:
    resolved = Path(path).resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix()[len(resolved.drive):]
    return f"/mnt/{drive}{rest}"


def _evenly_spaced(items: list, count: int) -> list:
    if count >= len(items):
        return items
    step = len(items) / count
    return [items[int(i * step)] for i in range(count)]


def _read_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_manifest(run_dir: Path) -> dict:
    return _read_json(run_dir / "manifest.json")


def _save_manifest(run_dir: Path, manifest: dict) -> None:
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _count_ply_vertices(path: Path) -> int:
    try:
        import trimesh
        return int(len(trimesh.load(str(path), process=False).vertices))
    except Exception:
        return -1


if __name__ == "__main__":
    main()
