"""Mask dynamic objects (traffic, people) in video frames before 3D reconstruction.

Extracts every Nth frame from a drone video (matching the MASt3R-SLAM MP4
subsample stride), runs SAM3 text-prompted segmentation for moving-object
classes, and writes both the raw and masked frames. Masked pixels are filled
with black so SLAM/photogrammetry does not anchor geometry on moving traffic.

Run with the AI/.venv-sam3 environment:

    python AI/scripts/mask_dynamic_objects.py \
        --video AI/data/raw/BridgeVid1-271223.mp4 \
        --output AI/outputs/bridgevid1_masked_frames \
        --subsample 30
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


DYNAMIC_PROMPTS: list[tuple[SegmentLabel, str]] = [
    (SegmentLabel.UNKNOWN, "car"),
    (SegmentLabel.UNKNOWN, "bus"),
    (SegmentLabel.UNKNOWN, "truck"),
    (SegmentLabel.UNKNOWN, "van"),
    (SegmentLabel.UNKNOWN, "motorcycle"),
    (SegmentLabel.UNKNOWN, "person"),
    (SegmentLabel.UNKNOWN, "boat"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--subsample", type=int, default=30)
    parser.add_argument("--min-score", type=float, default=0.35)
    parser.add_argument("--dilate-px", type=int, default=9)
    parser.add_argument("--max-mask-ratio", type=float, default=0.45, help="Skip masking a frame if the union mask exceeds this fraction (likely false positives)")
    parser.add_argument("--debug-every", type=int, default=20, help="Write a side-by-side debug image every N frames")
    args = parser.parse_args()

    frames_dir = args.output / "frames"
    masked_dir = args.output / "masked"
    debug_dir = args.output / "debug"
    for directory in (frames_dir, masked_dir, debug_dir):
        directory.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(args.video))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = list(range(0, total_frames, args.subsample))
    print(f"video: {args.video}")
    print(f"total frames: {total_frames}, extracting {len(indices)} (every {args.subsample}th)")

    segmenter = Sam3TextPromptSegmenter(
        prompts=DYNAMIC_PROMPTS,
        min_score=args.min_score,
        max_segments_per_prompt=40,
        min_area_ratio=0.00005,
        source_name="sam3_dynamic_mask",
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (args.dilate_px * 2 + 1, args.dilate_px * 2 + 1))
    stats: list[dict[str, object]] = []
    start = time.time()

    for position, frame_index in enumerate(indices):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            print(f"warning: could not read frame {frame_index}, stopping")
            break

        name = f"frame_{position:05d}.png"
        frame_path = frames_dir / name
        cv2.imwrite(str(frame_path), frame)

        segments = segmenter.segment(frame_path)
        union = np.zeros(frame.shape[:2], dtype=bool)
        for segment in segments:
            union |= segment.mask

        mask_ratio = float(union.mean())
        applied = bool(union.any()) and mask_ratio <= args.max_mask_ratio
        masked = frame.copy()
        if applied:
            dilated = cv2.dilate(union.astype(np.uint8), kernel).astype(bool)
            masked[dilated] = 0
            mask_ratio = float(dilated.mean())
        cv2.imwrite(str(masked_dir / name), masked)

        if args.debug_every and position % args.debug_every == 0:
            debug = np.hstack([frame, masked])
            cv2.imwrite(str(debug_dir / name), debug)

        stats.append(
            {
                "frame": name,
                "video_frame_index": frame_index,
                "segments": len(segments),
                "prompts_hit": sorted({segment.metadata["prompt"] for segment in segments}),
                "masked_pixel_ratio": round(mask_ratio, 5),
                "mask_applied": applied,
            }
        )
        elapsed = time.time() - start
        print(
            f"[{position + 1}/{len(indices)}] {name}: {len(segments)} segments, "
            f"masked {mask_ratio * 100:.2f}% ({elapsed:.0f}s elapsed)",
            flush=True,
        )

    capture.release()

    ratios = [entry["masked_pixel_ratio"] for entry in stats]
    summary = {
        "video": str(args.video),
        "subsample": args.subsample,
        "frames_written": len(stats),
        "prompts": [prompt for _, prompt in DYNAMIC_PROMPTS],
        "min_score": args.min_score,
        "dilate_px": args.dilate_px,
        "mean_masked_pixel_ratio": round(float(np.mean(ratios)), 5) if ratios else 0.0,
        "max_masked_pixel_ratio": round(float(np.max(ratios)), 5) if ratios else 0.0,
        "frames_with_masks": int(sum(1 for entry in stats if entry["mask_applied"])),
        "frames": stats,
    }
    summary_path = args.output / "masking_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"done: {len(stats)} frames, summary at {summary_path}")


if __name__ == "__main__":
    main()
