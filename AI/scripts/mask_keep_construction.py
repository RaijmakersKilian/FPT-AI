"""Keep ONLY the active construction zone in each frame, black out everything else.

This is the inverse of mask_dynamic_objects.py and tests the teacher's
"remove the background first, then build the position map" idea, narrowed to the
construction between the finished roads. SAM3 finds the construction apparatus
(yellow gantry / scaffolding / new pier / pylon), we keep those pixels (+ a small
context margin) and blacken the rest, then the masked frames can be fed to
MASt3R-SLAM.

Expectation to test: the construction zone is a tiny fraction of each frame and
only visible for part of the flyover, so SLAM may have too little to track. This
script reports per-frame kept-coverage so we can judge viability BEFORE running
SLAM.

    AI/.venv-sam3/Scripts/python.exe AI/scripts/mask_keep_construction.py \
        --frames-dir AI/outputs/runs/bridgevid1_full/01_frames/frames \
        --output AI/outputs/keep_construction_bridge1 --step 1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))

from ftp_ai.models import SegmentLabel  # noqa: E402
from ftp_ai.segmentation import Sam3TextPromptSegmenter  # noqa: E402

# Static construction structure to KEEP (cranes excluded: they move, bad for SLAM).
KEEP_PROMPTS: list[tuple[SegmentLabel, str]] = [
    (SegmentLabel.FORMWORK, "yellow steel gantry"),
    (SegmentLabel.FORMWORK, "scaffolding"),
    (SegmentLabel.FORMWORK, "bridge construction formwork"),
    (SegmentLabel.SUPPORT_COLUMN, "bridge pylon tower"),
    (SegmentLabel.SUPPORT_COLUMN, "bridge concrete pier"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--frames-dir", type=Path, help="Folder of already-extracted frame_*.png")
    src.add_argument("--video", type=Path, help="Extract every --subsample-th frame from this video")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--subsample", type=int, default=15, help="(video mode) take every Nth frame")
    parser.add_argument("--step", type=int, default=1, help="Process every Nth input frame (probe faster with >1)")
    parser.add_argument("--min-score", type=float, default=0.4)
    parser.add_argument("--dilate-px", type=int, default=14, help="Context margin kept around the construction")
    parser.add_argument("--resolution", type=int, default=1008, help="SAM3 inference resolution (must match the model's RoPE size; 1008)")
    args = parser.parse_args()

    masked_dir = args.output / "masked"
    debug_dir = args.output / "debug"
    for d in (masked_dir, debug_dir):
        d.mkdir(parents=True, exist_ok=True)

    # gather frames
    if args.frames_dir:
        frames = sorted(args.frames_dir.glob("frame_*.png"))[:: args.step]
        loader = lambda p: (p.name, cv2.imread(str(p)))  # noqa: E731
        items = [(p.name, p) for p in frames]
    else:
        cap = cv2.VideoCapture(str(args.video))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        idxs = list(range(0, total, args.subsample))[:: args.step]
        items = [(f"frame_{i:05d}.png", fi) for i, fi in enumerate(idxs)]

    print(f"frames to process: {len(items)} (step {args.step})")

    segmenter = Sam3TextPromptSegmenter(
        prompts=KEEP_PROMPTS,
        min_score=args.min_score,
        max_segments_per_prompt=30,
        resolution=args.resolution,
        min_area_ratio=0.0004,
        source_name="sam3_keep_construction",
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (args.dilate_px * 2 + 1, args.dilate_px * 2 + 1))

    stats = []
    start = time.time()
    cap = cv2.VideoCapture(str(args.video)) if args.video else None

    for pos, (name, ref) in enumerate(items):
        if args.frames_dir:
            frame = cv2.imread(str(ref))
        else:
            cap.set(cv2.CAP_PROP_POS_FRAMES, ref)
            ok, frame = cap.read()
            if not ok:
                break
        H, W = frame.shape[:2]

        # write raw frame to a 'frames' subdir so vision/debug can reuse
        tmp = args.output / "frames"
        tmp.mkdir(exist_ok=True)
        raw_path = tmp / name
        cv2.imwrite(str(raw_path), frame)

        segments = segmenter.segment(raw_path)
        union = np.zeros((H, W), bool)
        for s in segments:
            m = s.mask
            if m.shape != (H, W):
                m = cv2.resize(m.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST).astype(bool)
            union |= m

        kept = cv2.dilate(union.astype(np.uint8), kernel).astype(bool) if union.any() else union
        masked = np.zeros_like(frame)
        masked[kept] = frame[kept]
        cv2.imwrite(str(masked_dir / name), masked)

        cov = float(kept.mean())
        if pos % 5 == 0:
            cv2.imwrite(str(debug_dir / name), np.hstack([frame, masked]))
        stats.append({"frame": name, "segments": len(segments), "kept_pct": round(cov * 100, 3)})
        print(f"[{pos+1}/{len(items)}] {name}: {len(segments)} seg, kept {cov*100:.2f}% ({time.time()-start:.0f}s)", flush=True)

    if cap:
        cap.release()

    covs = [s["kept_pct"] for s in stats]
    with_content = [s for s in stats if s["kept_pct"] >= 0.5]
    summary = {
        "frames": len(stats),
        "frames_with_construction(>=0.5%)": len(with_content),
        "mean_kept_pct": round(float(np.mean(covs)), 3) if covs else 0,
        "max_kept_pct": round(float(np.max(covs)), 3) if covs else 0,
        "prompts": [p for _, p in KEEP_PROMPTS],
        "per_frame": stats,
    }
    (args.output / "keep_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nframes with construction (>=0.5% kept): {len(with_content)}/{len(stats)}")
    print(f"mean kept {summary['mean_kept_pct']}%, max {summary['max_kept_pct']}%")
    print(f"-> {masked_dir}  (feed to MASt3R-SLAM)  summary: {args.output/'keep_summary.json'}")


if __name__ == "__main__":
    main()
