"""Vision-only bridge segmentation on a single drone frame.

Implements the teacher's recommended direction: instead of comparing the
MASt3R-SLAM point cloud, isolate the bridge structure in a single video frame
with Segment Anything (SAM3 text prompts), color the structures, and remove
the background. The background-removed frame is what later gets compared 1:1
against the Unity / 3D-model render (which also has no background) once the
digital twin provides the drone pose.

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


# Structure prompts (the bridge being built) and their overlay colors (BGR).
STRUCTURE_PROMPTS: list[tuple[SegmentLabel, str]] = [
    (SegmentLabel.COMPLETED_DECK, "elevated bridge deck"),
    (SegmentLabel.COMPLETED_DECK, "concrete bridge road"),
    (SegmentLabel.SUPPORT_COLUMN, "bridge pylon tower"),
    (SegmentLabel.SUPPORT_COLUMN, "bridge concrete pier"),
    (SegmentLabel.FORMWORK, "bridge construction formwork"),
    (SegmentLabel.EQUIPMENT, "construction crane"),
]

LABEL_COLORS: dict[SegmentLabel, tuple[int, int, int]] = {
    SegmentLabel.COMPLETED_DECK: (80, 220, 80),     # green  - finished/usable deck
    SegmentLabel.SUPPORT_COLUMN: (240, 180, 40),    # blue   - pylon/piers
    SegmentLabel.FORMWORK: (40, 180, 250),          # orange - active construction
    SegmentLabel.EQUIPMENT: (60, 60, 230),          # red    - equipment (not bridge)
}

LABEL_NAMES: dict[SegmentLabel, str] = {
    SegmentLabel.COMPLETED_DECK: "deck",
    SegmentLabel.SUPPORT_COLUMN: "pylon/pier",
    SegmentLabel.FORMWORK: "formwork",
    SegmentLabel.EQUIPMENT: "equipment",
}

# Structure classes that count as "the bridge" for background removal.
BRIDGE_LABELS = {SegmentLabel.COMPLETED_DECK, SegmentLabel.SUPPORT_COLUMN, SegmentLabel.FORMWORK}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--min-score", type=float, default=0.3)
    parser.add_argument("--include-equipment", action="store_true", help="Keep cranes/equipment in the background-removed image")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    frame = cv2.imread(str(args.image))
    if frame is None:
        raise SystemExit(f"could not read {args.image}")
    height, width = frame.shape[:2]

    segmenter = Sam3TextPromptSegmenter(
        prompts=STRUCTURE_PROMPTS,
        min_score=args.min_score,
        max_segments_per_prompt=20,
        min_area_ratio=0.001,
        source_name="bridge_structure",
    )
    segments = segmenter.segment(args.image)
    print(f"{args.image.name}: {len(segments)} structure segments")

    overlay = frame.copy()
    label_masks: dict[SegmentLabel, np.ndarray] = {}
    for segment in segments:
        label = segment.label if segment.label in LABEL_COLORS else SegmentLabel.COMPLETED_DECK
        label_masks.setdefault(label, np.zeros((height, width), dtype=bool))
        label_masks[label] |= segment.mask

    # Paint structures, deck first so thin pylons/formwork stay visible on top.
    paint_order = [SegmentLabel.COMPLETED_DECK, SegmentLabel.SUPPORT_COLUMN, SegmentLabel.FORMWORK, SegmentLabel.EQUIPMENT]
    for label in paint_order:
        mask = label_masks.get(label)
        if mask is None or not mask.any():
            continue
        color = np.array(LABEL_COLORS[label], dtype=np.uint8)
        overlay[mask] = (0.45 * frame[mask] + 0.55 * color).astype(np.uint8)
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, [int(c) for c in color], 2)

    _draw_legend(overlay, label_masks)

    # Background removal: keep bridge structures, black out everything else.
    bridge_mask = np.zeros((height, width), dtype=bool)
    for label in BRIDGE_LABELS:
        if label in label_masks:
            bridge_mask |= label_masks[label]
    if args.include_equipment and SegmentLabel.EQUIPMENT in label_masks:
        bridge_mask |= label_masks[SegmentLabel.EQUIPMENT]
    bridge_mask = _clean_mask(bridge_mask)

    bridge_only = frame.copy()
    bridge_only[~bridge_mask] = 0
    rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
    rgba[~bridge_mask, 3] = 0

    overlay_path = args.output / "structures_overlay.jpg"
    bridge_path = args.output / "bridge_only.jpg"
    rgba_path = args.output / "bridge_only_transparent.png"
    mask_path = args.output / "bridge_mask.png"
    cv2.imwrite(str(overlay_path), overlay)
    cv2.imwrite(str(bridge_path), bridge_only)
    cv2.imwrite(str(rgba_path), rgba)
    cv2.imwrite(str(mask_path), (bridge_mask * 255).astype(np.uint8))

    summary = {
        "image": str(args.image),
        "segments": len(segments),
        "structure_pixel_pct": {
            LABEL_NAMES[label]: round(float(mask.mean()) * 100.0, 2)
            for label, mask in label_masks.items()
        },
        "bridge_pixel_pct": round(float(bridge_mask.mean()) * 100.0, 2),
        "outputs": {
            "structures_overlay": str(overlay_path),
            "bridge_only": str(bridge_path),
            "bridge_only_transparent": str(rgba_path),
            "bridge_mask": str(mask_path),
        },
    }
    (args.output / "segmentation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["structure_pixel_pct"], indent=2))
    print(f"bridge covers {summary['bridge_pixel_pct']}% of the frame")


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        return mask
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    closed = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    return closed.astype(bool)


def _draw_legend(image: np.ndarray, label_masks: dict[SegmentLabel, np.ndarray]) -> None:
    y = 30
    cv2.putText(image, "SAM3 bridge segmentation", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    y += 30
    for label in [SegmentLabel.COMPLETED_DECK, SegmentLabel.SUPPORT_COLUMN, SegmentLabel.FORMWORK, SegmentLabel.EQUIPMENT]:
        if label not in label_masks:
            continue
        color = LABEL_COLORS[label]
        cv2.rectangle(image, (15, y - 14), (35, y + 2), [int(c) for c in color], -1)
        cv2.putText(image, LABEL_NAMES[label], (42, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        y += 26


if __name__ == "__main__":
    main()
