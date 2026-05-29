from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np

from .models import Segment, SegmentLabel


class SegmentClassifier(Protocol):
    def classify(self, image_path: Path, segments: list[Segment]) -> list[Segment]:
        """Attach labels and confidence scores to segments."""


class IdentitySegmentClassifier:
    """Leave labels unchanged when the segmenter already classified masks."""

    def classify(self, image_path: Path, segments: list[Segment]) -> list[Segment]:
        return segments


class RuleBasedSegmentClassifier:
    """Baseline classifier using color, brightness, and texture heuristics."""

    def classify(self, image_path: Path, segments: list[Segment]) -> list[Segment]:
        cv2 = _import_cv2()
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        for segment in segments:
            pixels = image[segment.mask]
            hsv_pixels = hsv[segment.mask]
            gray_pixels = gray[segment.mask]
            if len(pixels) == 0:
                continue

            mean_bgr = pixels.mean(axis=0)
            mean_hsv = hsv_pixels.mean(axis=0)
            texture = float(gray_pixels.std())
            label, confidence = self._label_from_features(mean_bgr, mean_hsv, texture)
            segment.label = label
            segment.confidence = confidence
            segment.metadata.update(
                {
                    "mean_bgr": [round(float(value), 2) for value in mean_bgr],
                    "mean_hsv": [round(float(value), 2) for value in mean_hsv],
                    "texture": round(texture, 2),
                }
            )

        return segments

    def _label_from_features(
        self, mean_bgr: np.ndarray, mean_hsv: np.ndarray, texture: float
    ) -> tuple[SegmentLabel, float]:
        hue, saturation, value = mean_hsv
        blue, green, red = mean_bgr

        if value > 145 and saturation < 55 and texture < 45:
            return SegmentLabel.COMPLETED_DECK, 0.66
        if red > 95 and green > 75 and blue < 90 and saturation > 45:
            return SegmentLabel.FORMWORK, 0.58
        if texture > 55 and saturation < 95 and value < 145:
            return SegmentLabel.EXPOSED_REBAR, 0.52
        if 70 <= value <= 170 and saturation < 80 and texture < 55:
            return SegmentLabel.SUPPORT_COLUMN, 0.48
        if 15 <= hue <= 40 and saturation > 75 and value > 110:
            return SegmentLabel.EQUIPMENT, 0.45
        return SegmentLabel.UNKNOWN, 0.25


class UltralyticsSegmentClassifier:
    """Adapter placeholder for a trained YOLO/Ultralytics classifier."""

    def __init__(self, weights_path: Path) -> None:
        self.weights_path = weights_path

    def classify(self, image_path: Path, segments: list[Segment]) -> list[Segment]:
        raise NotImplementedError(
            "YOLO classification is not configured yet. Train/export weights first, "
            "then implement this adapter using ultralytics.YOLO."
        )


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for classification. Install opencv-python.") from exc
    return cv2
