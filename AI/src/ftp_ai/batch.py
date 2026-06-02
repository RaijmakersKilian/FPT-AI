from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from .classification import SegmentClassifier
from .config import PipelineConfig
from .models import ProgressReport
from .pipeline import run_image_pipeline
from .roi import RoiDetector
from .segmentation import Segmenter


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class BatchItem:
    image: Path
    output_dir: Path
    report: ProgressReport | None
    duration_seconds: float
    error: str | None = None


def run_roi_batch(
    images_dir: Path,
    output_dir: Path,
    config: PipelineConfig,
    limit: int = 10,
    segmenter: Segmenter | None = None,
    classifier: SegmentClassifier | None = None,
    roi_detector: RoiDetector | None = None,
    analysis_max_dimension: int | None = None,
) -> list[BatchItem]:
    image_paths = _select_spread(_list_images(images_dir), limit)
    if not image_paths:
        raise ValueError(f"No images found in {images_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    items: list[BatchItem] = []

    for index, image_path in enumerate(image_paths, start=1):
        item_dir = output_dir / f"{index:03d}_{image_path.stem}"
        started = perf_counter()
        try:
            report = run_image_pipeline(
                [image_path],
                item_dir,
                config,
                segmenter=segmenter,
                classifier=classifier,
                roi_detector=roi_detector,
                analysis_max_dimension=analysis_max_dimension,
                inputs={"image": str(image_path), "batch_index": str(index)},
            )
            items.append(
                BatchItem(
                    image=image_path,
                    output_dir=item_dir,
                    report=report,
                    duration_seconds=perf_counter() - started,
                )
            )
        except Exception as exc:
            items.append(
                BatchItem(
                    image=image_path,
                    output_dir=item_dir,
                    report=None,
                    duration_seconds=perf_counter() - started,
                    error=str(exc),
                )
            )

    _write_summary(items, output_dir / "summary.json")
    return items


def _list_images(images_dir: Path) -> list[Path]:
    return sorted(
        path for path in images_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _select_spread(paths: list[Path], limit: int) -> list[Path]:
    if limit <= 0 or len(paths) <= limit:
        return paths
    step = len(paths) / limit
    return [paths[min(len(paths) - 1, int(index * step))] for index in range(limit)]


def _write_summary(items: list[BatchItem], output_path: Path) -> None:
    successes = [item for item in items if item.report is not None]
    overall_values = [item.report.overall_completion for item in successes if item.report]
    summary = {
        "count": len(items),
        "succeeded": len(successes),
        "failed": len(items) - len(successes),
        "average_completion": round(sum(overall_values) / len(overall_values), 4)
        if overall_values
        else 0.0,
        "items": [
            {
                "image": str(item.image),
                "output_dir": str(item.output_dir),
                "duration_seconds": round(item.duration_seconds, 2),
                "overall_completion": round(item.report.overall_completion, 4)
                if item.report
                else None,
                "roi_bbox_xyxy": item.report.inputs.get("roi_bbox_xyxy")
                if item.report
                else None,
                "roi_confidence": item.report.inputs.get("roi_confidence")
                if item.report
                else None,
                "error": item.error,
            }
            for item in items
        ],
    }
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
