from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .models import ProgressReport, Segment


PALETTE = {
    "completed_deck": (70, 180, 90),
    "formwork": (35, 130, 210),
    "exposed_rebar": (60, 70, 190),
    "support_column": (210, 170, 65),
    "equipment": (35, 210, 230),
    "unknown": (180, 180, 180),
}


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
    for segment in segments:
        label = segment.label.value
        color = PALETTE.get(label, PALETTE["unknown"])
        mask = segment.mask.astype(bool)
        color_layer = np.zeros_like(image)
        color_layer[mask] = color
        overlay = cv2.addWeighted(overlay, 1.0, color_layer, 0.35, 0)

        x1, y1, x2, y2 = segment.bbox_xyxy
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            overlay,
            f"{label} {segment.confidence:.2f}",
            (x1, max(16, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            color,
            1,
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

