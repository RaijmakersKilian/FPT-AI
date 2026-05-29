from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from .models import SegmentLabel
from .segmentation import Sam3TextPromptSegmenter


@dataclass(frozen=True)
class RoiResult:
    bbox_xyxy: tuple[int, int, int, int]
    mask_path: Path
    image_path: Path
    prompt: str
    confidence: float


class RoiDetector(Protocol):
    def detect(self, image_path: Path, output_dir: Path) -> RoiResult | None:
        """Find and crop the construction region of interest."""


class Sam3ConstructionRoiDetector:
    def __init__(
        self,
        prompt: str = "construction site",
        min_score: float = 0.2,
        expansion_ratio: float = 0.08,
    ) -> None:
        self.prompt = prompt
        self.min_score = min_score
        self.expansion_ratio = expansion_ratio

    def detect(self, image_path: Path, output_dir: Path) -> RoiResult | None:
        segmenter = Sam3TextPromptSegmenter(
            prompts={SegmentLabel.UNKNOWN: self.prompt},
            min_score=self.min_score,
            max_segments_per_prompt=5,
        )
        try:
            segments = segmenter.segment(image_path)
        finally:
            _empty_cuda_cache()

        if not segments:
            return None

        best = max(segments, key=lambda segment: segment.area * max(segment.confidence, 0.01))
        cv2 = _import_cv2()
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")

        height, width = image.shape[:2]
        bbox = _expand_bbox(best.bbox_xyxy, width, height, self.expansion_ratio)
        x1, y1, x2, y2 = bbox
        roi_image = image[y1:y2, x1:x2]

        roi_mask = np.zeros((height, width), dtype=np.uint8)
        roi_mask[best.mask] = 255

        output_dir.mkdir(parents=True, exist_ok=True)
        mask_path = output_dir / "roi_mask.jpg"
        image_path_out = output_dir / "roi_image.jpg"
        if not cv2.imwrite(str(mask_path), roi_mask):
            raise RuntimeError(f"Could not write ROI mask: {mask_path}")
        if not cv2.imwrite(str(image_path_out), roi_image):
            raise RuntimeError(f"Could not write ROI image: {image_path_out}")

        return RoiResult(
            bbox_xyxy=bbox,
            mask_path=mask_path,
            image_path=image_path_out,
            prompt=self.prompt,
            confidence=best.confidence,
        )


def _expand_bbox(
    bbox_xyxy: tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    ratio: float,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox_xyxy
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    pad_x = int(width * ratio)
    pad_y = int(height * ratio)
    return (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(image_width, x2 + pad_x),
        min(image_height, y2 + pad_y),
    )


def _empty_cuda_cache() -> None:
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for ROI detection. Install opencv-python.") from exc
    return cv2
