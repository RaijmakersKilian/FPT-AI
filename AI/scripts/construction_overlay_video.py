"""Whole-video construction overlay, next to the finished 3D model.

Runs the construction-zone segmentation (same prompts as segment_bridge_frame.py)
across every sampled frame of the flyover and writes an annotated MP4. Each
output frame shows:

  [ drone frame + highlighted construction ]  [ finished 3D model render ]
  [ construction-coverage timeline along the whole flyover ]

This is the "for the whole video" deliverable. A pixel-level 1:1 overlay onto
the model needs the drone pose (Unity); until then this is the visual
comparison, and the quantitative one is the 3D point-cloud-vs-model per-section
result (AI/src/ftp_ai/model_comparison.py).

    AI/.venv-sam3/Scripts/python.exe AI/scripts/construction_overlay_video.py \
        --frames AI/outputs/bridgevid1_masked_frames_s15/frames \
        --model-render AI/outputs/vision_compare/model_render.jpg \
        --output AI/outputs/vision_compare/construction_overlay.mp4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))

from ftp_ai.models import SegmentLabel  # noqa: E402
from ftp_ai.segmentation import Sam3TextPromptSegmenter  # noqa: E402
from segment_bridge_frame import (  # noqa: E402
    CONSTRUCTION_LABELS,
    CONSTRUCTION_PROMPTS,
    LABEL_COLORS,
    LABEL_NAMES,
    _clean_mask,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, default=None, help="Directory of frame_*.png (preferred)")
    parser.add_argument("--video", type=Path, default=None, help="Video file (used if --frames not given)")
    parser.add_argument("--model-render", type=Path, default=None, help="Static finished-model render for the side panel")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-every", type=int, default=2, help="When reading a video, take every Nth frame")
    parser.add_argument("--min-score", type=float, default=0.4)
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument("--main-width", type=int, default=1280)
    args = parser.parse_args()

    frames = _gather_frames(args)
    if not frames:
        raise SystemExit("no frames found")
    print(f"processing {len(frames)} frames")

    segmenter = Sam3TextPromptSegmenter(
        prompts=CONSTRUCTION_PROMPTS,
        min_score=args.min_score,
        max_segments_per_prompt=20,
        min_area_ratio=0.001,
        source_name="bridge_construction",
    )

    model_panel = None
    if args.model_render and args.model_render.exists():
        model_panel = cv2.imread(str(args.model_render))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    coverage: list[float] = []

    # First pass over a few frames is unnecessary; segment as we go, but we need
    # the coverage series for the timeline, so compute overlays first, then write.
    annotated_frames: list[np.ndarray] = []
    for index, (name, frame) in enumerate(frames):
        overlay, pct = _annotate(frame, segmenter)
        coverage.append(pct)
        annotated_frames.append(overlay)
        print(f"[{index + 1}/{len(frames)}] {name}: construction {pct:.2f}%", flush=True)

    peak = max(coverage) if coverage else 1.0
    for index, overlay in enumerate(annotated_frames):
        composed = _compose(overlay, model_panel, coverage, index, peak, args.main_width)
        if writer is None:
            height, width = composed.shape[:2]
            writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (width, height))
        writer.write(composed)
    if writer is not None:
        writer.release()

    summary = {
        "frames": len(frames),
        "mean_construction_pct": round(float(np.mean(coverage)), 3),
        "peak_construction_pct": round(float(peak), 3),
        "frames_with_construction": int(sum(1 for c in coverage if c > 0.3)),
        "output": str(args.output),
        "note": "Pixel-level overlay onto the 3D model needs drone pose; quantitative comparison is the 3D per-section result.",
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def _gather_frames(args) -> list[tuple[str, np.ndarray]]:
    frames: list[tuple[str, np.ndarray]] = []
    if args.frames and args.frames.exists():
        for path in sorted(args.frames.glob("frame_*.png")):
            image = cv2.imread(str(path))
            if image is not None:
                frames.append((path.name, image))
        return frames
    if args.video and args.video.exists():
        cap = cv2.VideoCapture(str(args.video))
        idx = -1
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            idx += 1
            if idx % args.sample_every == 0:
                frames.append((f"frame_{idx:05d}", frame))
        cap.release()
    return frames


def _annotate(frame: np.ndarray, segmenter: Sam3TextPromptSegmenter) -> tuple[np.ndarray, float]:
    height, width = frame.shape[:2]
    # Sam3TextPromptSegmenter reads from a path; write a temp frame in-memory via cv2 is not
    # supported, so we round-trip through a temp file kept by the OS cache.
    tmp = Path(_tmp_path())
    cv2.imwrite(str(tmp), frame)
    try:
        segments = segmenter.segment(tmp)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass

    label_masks: dict[SegmentLabel, np.ndarray] = {}
    for segment in segments:
        label = segment.label if segment.label in LABEL_COLORS else SegmentLabel.FORMWORK
        label_masks.setdefault(label, np.zeros((height, width), dtype=bool))
        label_masks[label] |= segment.mask

    overlay = frame.copy()
    for label in [SegmentLabel.SUPPORT_COLUMN, SegmentLabel.FORMWORK, SegmentLabel.EXPOSED_REBAR, SegmentLabel.EQUIPMENT]:
        mask = label_masks.get(label)
        if mask is None or not mask.any():
            continue
        color = np.array(LABEL_COLORS[label], dtype=np.uint8)
        overlay[mask] = (0.45 * frame[mask] + 0.55 * color).astype(np.uint8)
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, [int(c) for c in color], 2)

    construction = np.zeros((height, width), dtype=bool)
    for label in CONSTRUCTION_LABELS:
        if label in label_masks:
            construction |= label_masks[label]
    construction = _clean_mask(construction)
    return overlay, float(construction.mean()) * 100.0


def _compose(overlay, model_panel, coverage, index, peak, main_width) -> np.ndarray:
    scale = main_width / overlay.shape[1]
    main = cv2.resize(overlay, (main_width, int(overlay.shape[0] * scale)))
    h = main.shape[0]

    cv2.putText(main, "AI: active construction (between finished roads)", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(main, f"construction in view: {coverage[index]:.1f}%", (15, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 200, 255), 2, cv2.LINE_AA)

    side_w = 460
    if model_panel is not None:
        ms = side_w / model_panel.shape[1]
        side = cv2.resize(model_panel, (side_w, int(model_panel.shape[0] * ms)))
        panel = np.zeros((h, side_w, 3), dtype=np.uint8)
        y = max(0, (h - side.shape[0]) // 2)
        panel[y:y + side.shape[0]] = side[: h - y]
        cv2.putText(panel, "Finished 3D model", (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    else:
        panel = np.zeros((h, side_w, 3), dtype=np.uint8)
    body = np.hstack([main, panel])

    # Construction-coverage timeline along the whole flyover.
    strip_h = 90
    strip = np.full((strip_h, body.shape[1], 3), 22, dtype=np.uint8)
    cv2.putText(strip, "Construction along the flyover (whole video)", (15, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
    n = len(coverage)
    left, right, base, top = 15, body.shape[1] - 15, strip_h - 12, 34
    for i, value in enumerate(coverage):
        x = int(left + (right - left) * i / max(n - 1, 1))
        bar = int((base - top) * (value / max(peak, 1e-6)))
        color = (40, 200, 255) if i == index else (70, 110, 90)
        cv2.line(strip, (x, base), (x, base - bar), color, 1)
    cursor_x = int(left + (right - left) * index / max(n - 1, 1))
    cv2.line(strip, (cursor_x, top), (cursor_x, base), (255, 255, 255), 1)

    return np.vstack([body, strip])


def _tmp_path() -> str:
    import tempfile
    return str(Path(tempfile.gettempdir()) / f"_constr_frame_{np.random.randint(0, 1_000_000_000)}.png")


if __name__ == "__main__":
    main()
