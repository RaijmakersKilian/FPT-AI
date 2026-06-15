"""Compose the vision-comparison presentation figure.

Stitches the three-step story the teacher recommended into one panel:
  1. raw drone frame (input, with background)
  2. SAM3 bridge segmentation -> background removed (the AI vision step)
  3. planned 3D/BIM model render (reference, no background)

    AI/.venv-sam3/Scripts/python.exe AI/scripts/build_vision_comparison.py \
        --frame AI/outputs/bridgevid1_masked_frames_s15/frames/frame_00120.png \
        --overlay AI/outputs/vision_compare/frame_00120/structures_overlay.jpg \
        --bridge-only AI/outputs/vision_compare/frame_00120/bridge_only.jpg \
        --model-render AI/outputs/vision_compare/model_render.jpg \
        --output AI/outputs/vision_compare/frame_00120/comparison_figure.jpg
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--bridge-only", type=Path, required=True)
    parser.add_argument("--model-render", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--panel-width", type=int, default=640)
    args = parser.parse_args()

    panels = [
        (args.frame, "1. Drone frame (input)", "real world + background"),
        (args.overlay, "2. SAM3 segmentation", "bridge structures detected"),
        (args.bridge_only, "3. Background removed", "as-built bridge isolated"),
        (args.model_render, "4. Planned 3D model", "reference, no background"),
    ]

    rendered = [_panel(path, title, subtitle, args.panel_width) for path, title, subtitle in panels]
    strip = np.hstack(rendered)

    caption_height = 70
    canvas = np.full((strip.shape[0] + caption_height, strip.shape[1], 3), 25, dtype=np.uint8)
    canvas[:strip.shape[0]] = strip
    cv2.putText(
        canvas,
        "Vision-only progress check: SAM isolates the as-built bridge from one frame and removes background; compared against the planned model.",
        (20, strip.shape[0] + 28),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        "With Unity drone-pose mapping this comparison becomes automatic and 1:1 (same viewpoint, both background-free).",
        (20, strip.shape[0] + 52),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (170, 200, 255), 1, cv2.LINE_AA,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), canvas)
    print(f"saved comparison figure -> {args.output}")


def _panel(path: Path, title: str, subtitle: str, width: int) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit(f"could not read {path}")
    scale = width / image.shape[1]
    resized = cv2.resize(image, (width, int(image.shape[0] * scale)))

    header = 56
    panel = np.full((resized.shape[0] + header, width, 3), 25, dtype=np.uint8)
    panel[header:] = resized
    cv2.putText(panel, title, (14, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(panel, subtitle, (14, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.line(panel, (width - 1, 0), (width - 1, panel.shape[0]), (60, 60, 60), 1)
    return panel


if __name__ == "__main__":
    main()
