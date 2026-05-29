from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

import numpy as np

from .models import Segment, SegmentLabel


DEFAULT_SAM3_PROMPTS: dict[SegmentLabel, str] = {
    SegmentLabel.COMPLETED_DECK: "bridge deck",
    SegmentLabel.FORMWORK: "construction formwork",
    SegmentLabel.EXPOSED_REBAR: "steel rebar",
    SegmentLabel.SUPPORT_COLUMN: "bridge column",
    SegmentLabel.EQUIPMENT: "construction equipment",
}


class Segmenter(Protocol):
    def segment(self, image_path: Path) -> list[Segment]:
        """Return pixel masks for meaningful image regions."""


class ClassicalSegmenter:
    """OpenCV fallback that approximates SAM-style masks using contours."""

    def __init__(self, min_area_ratio: float = 0.0015, max_segments: int = 120) -> None:
        self.min_area_ratio = min_area_ratio
        self.max_segments = max_segments

    def segment(self, image_path: Path) -> list[Segment]:
        cv2 = _import_cv2()
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")

        height, width = image.shape[:2]
        min_area = int(height * width * self.min_area_ratio)

        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        channels = cv2.split(lab)
        edges = cv2.Canny(channels[0], 60, 140)
        edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        segments: list[Segment] = []
        for contour in contours:
            area = int(cv2.contourArea(contour))
            if area < min_area:
                continue

            mask = np.zeros((height, width), dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 1, thickness=-1)
            x, y, w, h = cv2.boundingRect(contour)
            segments.append(
                Segment(
                    id=len(segments),
                    mask=mask.astype(bool),
                    bbox_xyxy=(x, y, x + w, y + h),
                    area=int(mask.sum()),
                    metadata={"source": "classical_contour"},
                )
            )
            if len(segments) >= self.max_segments:
                break

        return segments


class Sam2AutomaticSegmenter:
    """Adapter placeholder for SAM2 automatic mask generation.

    The repository intentionally does not vendor model weights. Wire this class to
    the installed SAM2 package/checkpoint when the team has the model available.
    """

    def __init__(self, checkpoint_path: Path, model_config: Path | None = None) -> None:
        self.checkpoint_path = checkpoint_path
        self.model_config = model_config

    def segment(self, image_path: Path) -> list[Segment]:
        raise NotImplementedError(
            "SAM2 is not configured yet. Use ClassicalSegmenter for the baseline, "
            "or implement this adapter with the team's SAM2 checkpoint."
        )


class Sam3TextPromptSegmenter:
    """SAM3 adapter for open-vocabulary text-prompted segmentation.

    Requires Meta's optional `sam3` package, PyTorch, CUDA, and accepted Hugging
    Face access to the SAM3 checkpoints. Dependencies are imported lazily so the
    baseline pipeline still works without them.
    """

    def __init__(
        self,
        prompts: dict[SegmentLabel, str] | None = None,
        min_score: float = 0.2,
        max_segments_per_prompt: int = 20,
        resolution: int = 1008,
    ) -> None:
        self.prompts = prompts or DEFAULT_SAM3_PROMPTS
        self.min_score = min_score
        self.max_segments_per_prompt = max_segments_per_prompt
        self.resolution = resolution
        self._processor = None

    def segment(self, image_path: Path) -> list[Segment]:
        processor = self._get_processor()
        image = self._open_image(image_path)
        autocast_context = self._autocast_context()
        with autocast_context:
            inference_state = processor.set_image(image)

        segments: list[Segment] = []
        for label, prompt in self.prompts.items():
            with autocast_context:
                output = processor.set_text_prompt(state=inference_state, prompt=prompt)
            masks = self._to_numpy(output.get("masks"))
            boxes = self._to_numpy(output.get("boxes"))
            scores = self._to_numpy(output.get("scores"))

            for mask, box, score in self._iter_predictions(masks, boxes, scores):
                if float(score) < self.min_score:
                    continue
                binary_mask = mask.astype(bool)
                area = int(binary_mask.sum())
                if area == 0:
                    continue
                segments.append(
                    Segment(
                        id=len(segments),
                        mask=binary_mask,
                        bbox_xyxy=self._box_to_xyxy(box, binary_mask),
                        area=area,
                        label=label,
                        confidence=float(score),
                        metadata={"source": "sam3_text_prompt", "prompt": prompt},
                    )
                )
                if len([segment for segment in segments if segment.label == label]) >= self.max_segments_per_prompt:
                    break
            self._empty_cuda_cache()

        return segments

    def _get_processor(self):
        if self._processor is not None:
            return self._processor
        _load_local_env()
        try:
            from sam3.model.sam3_image_processor import Sam3Processor  # type: ignore
            from sam3.model_builder import build_sam3_image_model  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "SAM3 is not installed. Install Meta's sam3 package and checkpoints first. "
                "See README.md for the optional SAM3 setup commands."
            ) from exc

        model = build_sam3_image_model()
        self._processor = Sam3Processor(
            model,
            resolution=self.resolution,
            confidence_threshold=self.min_score,
        )
        return self._processor

    def _autocast_context(self):
        import contextlib

        try:
            import torch
        except ImportError:
            return contextlib.nullcontext()

        if torch.cuda.is_available():
            return torch.autocast(device_type="cuda", dtype=torch.bfloat16)
        return contextlib.nullcontext()

    def _empty_cuda_cache(self) -> None:
        try:
            import torch
        except ImportError:
            return
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _open_image(self, image_path: Path):
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Pillow is required for SAM3 image loading.") from exc
        return Image.open(image_path).convert("RGB")

    def _to_numpy(self, value):
        if value is None:
            return np.array([])
        if hasattr(value, "detach"):
            value = value.detach().cpu()
            if getattr(value, "is_floating_point", lambda: False)():
                value = value.float()
        if hasattr(value, "numpy"):
            return value.numpy()
        return np.asarray(value)

    def _iter_predictions(self, masks: np.ndarray, boxes: np.ndarray, scores: np.ndarray):
        if masks.size == 0:
            return
        if masks.ndim == 4:
            masks = masks[:, 0]
        if boxes.size == 0:
            boxes = np.zeros((len(masks), 4), dtype=float)
        if scores.size == 0:
            scores = np.ones((len(masks),), dtype=float)
        for index, mask in enumerate(masks):
            yield mask, boxes[index], scores[index]

    def _box_to_xyxy(self, box: np.ndarray, mask: np.ndarray) -> tuple[int, int, int, int]:
        if box.size >= 4 and np.any(box):
            x1, y1, x2, y2 = [int(round(float(value))) for value in box[:4]]
            return x1, y1, x2, y2

        ys, xs = np.where(mask)
        if len(xs) == 0 or len(ys) == 0:
            return 0, 0, 0, 0
        return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for segmentation. Install opencv-python.") from exc
    return cv2


def _load_local_env() -> None:
    for env_path in (Path(".env"), Path("data/.env")):
        if not env_path.exists():
            continue

        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
