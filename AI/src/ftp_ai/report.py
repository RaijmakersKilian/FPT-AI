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
MAX_DRAWN_OBJECT_SEGMENTS = 60


def write_json_report(report: ProgressReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return output_path


def write_annotated_image(image_path: Path, segments: list[Segment], output_path: Path) -> Path:
    cv2 = _import_cv2()
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")

    overlay = render_annotated_image(image, segments)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), overlay)
    return output_path


def render_annotated_image(image: np.ndarray, segments: list[Segment]) -> np.ndarray:
    cv2 = _import_cv2()
    overlay = image.copy()
    object_mode = any(
        segment.metadata.get("source") in {"sam3_object_prompt", "sam2_auto"}
        for segment in segments
    )
    sorted_segments = sorted(segments, key=lambda item: item.area * item.confidence, reverse=True)
    if object_mode:
        drawable_segments = sorted_segments[:MAX_DRAWN_OBJECT_SEGMENTS]
    else:
        drawable_segments = [
            segment
            for segment in sorted_segments
            if segment.label.value in DRAW_LABELS
        ][:MAX_DRAWN_SEGMENTS]

    for segment in drawable_segments:
        label = str(segment.metadata.get("display_label") or segment.label.value)
        color = _object_color(segment.id) if object_mode else PALETTE.get(label, PALETTE["unknown"])
        mask = segment.mask.astype(bool)
        color_layer = np.zeros_like(image)
        color_layer[mask] = color
        mask_alpha = 0.24 if object_mode else 0.36
        overlay = cv2.addWeighted(overlay, 1.0, color_layer, mask_alpha, 0)

        x1, y1, x2, y2 = segment.bbox_xyxy
        box_thickness = 1 if object_mode else 2
        font_scale = 0.34 if object_mode else 0.46
        text_thickness = 1
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, box_thickness)
        text = f"{label} {segment.confidence:.2f}"
        (text_width, text_height), baseline = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            text_thickness,
        )
        label_y = max(text_height + baseline + 3, y1)
        cv2.rectangle(
            overlay,
            (x1, label_y - text_height - baseline - 3),
            (x1 + text_width + 5, label_y + baseline),
            color,
            thickness=-1,
        )
        cv2.putText(
            overlay,
            text[:32],
            (x1 + 3, label_y - 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 0, 0),
            text_thickness,
            cv2.LINE_AA,
        )

    return overlay


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for annotated output. Install opencv-python.") from exc
    return cv2


def _object_color(index: int) -> tuple[int, int, int]:
    colors = [
        (0, 255, 255),
        (255, 90, 60),
        (80, 220, 80),
        (255, 80, 220),
        (60, 160, 255),
        (180, 255, 60),
        (255, 170, 40),
        (120, 100, 255),
        (40, 240, 170),
        (230, 230, 40),
    ]
    return colors[index % len(colors)]
