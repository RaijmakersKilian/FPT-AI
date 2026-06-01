from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .models import ProgressReport, Segment


PALETTE = {
    "completed_deck": (40, 230, 80),
    "formwork": (20, 120, 255),
    "exposed_rebar": (40, 40, 255),
    "support_column": (255, 120, 20),
    "equipment": (0, 245, 255),
    "unknown": (190, 190, 190),
}

DRAW_LABELS = {"completed_deck", "formwork", "equipment", "support_column", "exposed_rebar"}
MAX_DRAWN_SEGMENTS = 18


def write_json_report(report: ProgressReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return output_path


def write_annotated_image(image_path: Path, segments: list[Segment], output_path: Path) -> Path:
    cv2 = _import_cv2()
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")

    overlay = image.copy()
    drawable_segments = [
        segment
        for segment in sorted(segments, key=lambda item: item.area * item.confidence, reverse=True)
        if segment.label.value in DRAW_LABELS
    ][:MAX_DRAWN_SEGMENTS]

    for segment in drawable_segments:
        label = segment.label.value
        color = PALETTE.get(label, PALETTE["unknown"])
        mask = segment.mask.astype(bool)
        color_layer = np.zeros_like(image)
        color_layer[mask] = color
        overlay = cv2.addWeighted(overlay, 1.0, color_layer, 0.42, 0)

        x1, y1, x2, y2 = segment.bbox_xyxy
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 3)
        text = f"{label} {segment.confidence:.2f}"
        (text_width, text_height), baseline = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            2,
        )
        label_y = max(text_height + baseline + 4, y1)
        cv2.rectangle(
            overlay,
            (x1, label_y - text_height - baseline - 4),
            (x1 + text_width + 8, label_y + baseline),
            color,
            thickness=-1,
        )
        cv2.putText(
            overlay,
            text,
            (x1 + 4, label_y - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), overlay)
    return output_path


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for annotated output. Install opencv-python.") from exc
    return cv2
