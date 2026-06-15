"""Vision-only segmentation of the bridge CONSTRUCTION zone on a drone frame.

The progress that matters is not the already-finished roadways, but the active
construction happening between/alongside them - the formwork, new concrete
piers, the pylon, rebar and the unfinished span. This isolates that
construction zone with SAM3 and removes everything else (finished roads, city,
river, trees), which is exactly what gets compared against the planned model.

Matches the teacher's brief: "search for everything that is currently being
built for the bridge and ignore/remove the rest."

    AI/.venv-sam3/Scripts/python.exe AI/scripts/segment_bridge_frame.py \
        --image AI/outputs/bridgevid1_masked_frames_s15/frames/frame_00120.png \
        --output AI/outputs/vision_compare/frame_00120
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent / "src"))

from ftp_ai.models import SegmentLabel  # noqa: E402
from ftp_ai.segmentation import Sam3TextPromptSegmenter  # noqa: E402


# Construction-zone prompts: what is actively being built between the roads.
# Chosen from a SAM3 prompt probe on frame 120 - broad terms like
# "bridge construction formwork" over-fire onto the finished deck, while these
# localize the central construction apparatus.
CONSTRUCTION_PROMPTS: list[tuple[SegmentLabel, str]] = [
    # Structures / machines being built (clean, low false-positive set)
    (SegmentLabel.FORMWORK, "yellow steel gantry"),
    (SegmentLabel.FORMWORK, "scaffolding"),
    (SegmentLabel.SUPPORT_COLUMN, "bridge pylon tower"),
    (SegmentLabel.EQUIPMENT, "construction crane"),
]

# Optional construction-ground zone (--include-ground): staging, materials,
# earthworks/sand. Captures more of the real construction area but also
# over-fires onto shipping containers/trucks, so it is off by default.
GROUND_PROMPTS: list[tuple[SegmentLabel, str]] = [
    (SegmentLabel.EXPOSED_REBAR, "construction laydown area"),
    (SegmentLabel.EXPOSED_REBAR, "construction materials"),
    (SegmentLabel.EXPOSED_REBAR, "bare soil construction ground"),
]

# Full-bridge prompts (the old behavior), kept for --focus full-bridge.
FULL_BRIDGE_PROMPTS: list[tuple[SegmentLabel, str]] = [
    (SegmentLabel.COMPLETED_DECK, "elevated bridge deck"),
    (SegmentLabel.COMPLETED_DECK, "concrete bridge road"),
    (SegmentLabel.SUPPORT_COLUMN, "bridge pylon tower"),
    (SegmentLabel.SUPPORT_COLUMN, "bridge concrete pier"),
    (SegmentLabel.FORMWORK, "bridge construction formwork"),
    (SegmentLabel.EQUIPMENT, "construction crane"),
]

LABEL_COLORS: dict[SegmentLabel, tuple[int, int, int]] = {
    SegmentLabel.COMPLETED_DECK: (90, 90, 90),      # grey   - finished road (context, dimmed)
    SegmentLabel.FORMWORK: (40, 180, 250),          # orange - active construction / formwork
    SegmentLabel.SUPPORT_COLUMN: (240, 180, 40),    # blue   - new piers / pylon
    SegmentLabel.EXPOSED_REBAR: (200, 80, 220),     # purple - rebar
    SegmentLabel.EQUIPMENT: (60, 60, 230),          # red    - cranes / equipment
}

LABEL_NAMES: dict[SegmentLabel, str] = {
    SegmentLabel.COMPLETED_DECK: "finished road",
    SegmentLabel.FORMWORK: "formwork/new span",
    SegmentLabel.SUPPORT_COLUMN: "new pier/pylon",
    SegmentLabel.EXPOSED_REBAR: "construction area/materials",
    SegmentLabel.EQUIPMENT: "equipment",
}

# Classes that make up the construction zone we isolate.
CONSTRUCTION_LABELS = {SegmentLabel.FORMWORK, SegmentLabel.SUPPORT_COLUMN, SegmentLabel.EXPOSED_REBAR}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--focus", choices=["construction", "full-bridge"], default="construction")
    parser.add_argument("--min-score", type=float, default=0.3)
    parser.add_argument("--include-ground", action="store_true", help="Also detect the construction ground zone (staging/materials/sand); noisier")
    parser.add_argument("--include-equipment", action="store_true", help="Keep cranes/equipment in the isolated construction image")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    frame = cv2.imread(str(args.image))
    if frame is None:
        raise SystemExit(f"could not read {args.image}")
    height, width = frame.shape[:2]

    if args.focus == "construction":
        prompts = list(CONSTRUCTION_PROMPTS)
        if args.include_ground:
            prompts += GROUND_PROMPTS
        foreground_labels = set(CONSTRUCTION_LABELS)
        title = "SAM3 construction-zone segmentation"
    else:
        prompts = FULL_BRIDGE_PROMPTS
        foreground_labels = {SegmentLabel.COMPLETED_DECK, SegmentLabel.SUPPORT_COLUMN, SegmentLabel.FORMWORK}
        title = "SAM3 bridge segmentation"
    if args.include_equipment:
        foreground_labels.add(SegmentLabel.EQUIPMENT)

    segmenter = Sam3TextPromptSegmenter(
        prompts=prompts,
        min_score=args.min_score,
        max_segments_per_prompt=20,
        min_area_ratio=0.001,
        source_name="bridge_construction",
    )
    segments = segmenter.segment(args.image)
    print(f"{args.image.name}: {len(segments)} segments (focus={args.focus})")

    label_masks: dict[SegmentLabel, np.ndarray] = {}
    for segment in segments:
        label = segment.label if segment.label in LABEL_COLORS else SegmentLabel.FORMWORK
        label_masks.setdefault(label, np.zeros((height, width), dtype=bool))
        label_masks[label] |= segment.mask

    overlay = frame.copy()
    # Paint finished road first (dim context), then construction classes on top.
    paint_order = [SegmentLabel.COMPLETED_DECK, SegmentLabel.SUPPORT_COLUMN, SegmentLabel.FORMWORK, SegmentLabel.EXPOSED_REBAR, SegmentLabel.EQUIPMENT]
    for label in paint_order:
        mask = label_masks.get(label)
        if mask is None or not mask.any():
            continue
        color = np.array(LABEL_COLORS[label], dtype=np.uint8)
        blend = 0.35 if label == SegmentLabel.COMPLETED_DECK else 0.55
        overlay[mask] = ((1 - blend) * frame[mask] + blend * color).astype(np.uint8)
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, [int(c) for c in color], 2)

    _draw_legend(overlay, label_masks, title)

    # Isolate the construction zone: keep construction classes, black out the rest.
    construction_mask = np.zeros((height, width), dtype=bool)
    for label in foreground_labels:
        if label in label_masks:
            construction_mask |= label_masks[label]
    construction_mask = _clean_mask(construction_mask)

    isolated = frame.copy()
    isolated[~construction_mask] = 0
    rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
    rgba[~construction_mask, 3] = 0

    overlay_path = args.output / "structures_overlay.jpg"
    isolated_path = args.output / "bridge_only.jpg"
    rgba_path = args.output / "bridge_only_transparent.png"
    mask_path = args.output / "bridge_mask.png"
    cv2.imwrite(str(overlay_path), overlay)
    cv2.imwrite(str(isolated_path), isolated)
    cv2.imwrite(str(rgba_path), rgba)
    cv2.imwrite(str(mask_path), (construction_mask * 255).astype(np.uint8))

    summary = {
        "image": str(args.image),
        "focus": args.focus,
        "segments": len(segments),
        "class_pixel_pct": {
            LABEL_NAMES[label]: round(float(mask.mean()) * 100.0, 2)
            for label, mask in label_masks.items()
        },
        "construction_pixel_pct": round(float(construction_mask.mean()) * 100.0, 2),
        "outputs": {
            "structures_overlay": str(overlay_path),
            "construction_isolated": str(isolated_path),
            "construction_isolated_transparent": str(rgba_path),
            "construction_mask": str(mask_path),
        },
    }
    (args.output / "segmentation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    # Keep the pipeline's expected key too.
    summary["bridge_pixel_pct"] = summary["construction_pixel_pct"]
    (args.output / "segmentation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["class_pixel_pct"], indent=2))
    print(f"construction zone covers {summary['construction_pixel_pct']}% of the frame")


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        return mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    closed = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    return closed.astype(bool)


def _draw_legend(image: np.ndarray, label_masks: dict[SegmentLabel, np.ndarray], title: str) -> None:
    y = 30
    cv2.putText(image, title, (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    y += 30
    for label in [SegmentLabel.FORMWORK, SegmentLabel.SUPPORT_COLUMN, SegmentLabel.EXPOSED_REBAR, SegmentLabel.EQUIPMENT, SegmentLabel.COMPLETED_DECK]:
        if label not in label_masks:
            continue
        color = LABEL_COLORS[label]
        cv2.rectangle(image, (15, y - 14), (35, y + 2), [int(c) for c in color], -1)
        cv2.putText(image, LABEL_NAMES[label], (42, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        y += 26


if __name__ == "__main__":
    main()
