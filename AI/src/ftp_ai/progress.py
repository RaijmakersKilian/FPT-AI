from __future__ import annotations

from collections import defaultdict

from .config import PipelineConfig
from .models import ProgressReport, SectionProgress, SectionStatus, Segment


def estimate_progress(
    segments: list[Segment],
    image_shape: tuple[int, int],
    config: PipelineConfig,
    inputs: dict[str, str] | None = None,
) -> ProgressReport:
    height, width = image_shape
    if height <= 0 or width <= 0:
        raise ValueError("Image shape must contain positive height and width.")

    sections = [
        _estimate_section(index, segments, width, config)
        for index in range(config.sections)
    ]

    if sections:
        overall_completion = sum(section.completion for section in sections) / len(sections)
    else:
        overall_completion = 0.0

    label_coverage = _label_coverage(segments, height * width)
    return ProgressReport(
        project_name=config.project_name,
        sections=sections,
        overall_completion=overall_completion,
        label_coverage=label_coverage,
        inputs=inputs or {},
    )


def _estimate_section(
    index: int,
    segments: list[Segment],
    image_width: int,
    config: PipelineConfig,
) -> SectionProgress:
    start_x = int(index * image_width / config.sections)
    end_x = int((index + 1) * image_width / config.sections)
    start_ratio = start_x / image_width
    end_ratio = end_x / image_width

    weighted_area = 0.0
    total_area = 0.0
    label_area: dict[str, float] = defaultdict(float)

    for segment in segments:
        x1, _, x2, _ = segment.bbox_xyxy
        overlap = max(0, min(x2, end_x) - max(x1, start_x))
        bbox_width = max(1, x2 - x1)
        if overlap <= 0:
            continue

        area_share = segment.area * (overlap / bbox_width)
        label = segment.label.value
        total_area += area_share
        weighted_area += area_share * config.weights.for_label(label)
        label_area[label] += area_share

    completion = 0.0 if total_area == 0 else min(1.0, weighted_area / total_area)
    dominant_label = max(label_area.items(), key=lambda item: item[1])[0] if label_area else "unknown"

    if completion >= 0.75:
        status = SectionStatus.COMPLETE
    elif completion >= 0.2:
        status = SectionStatus.PARTIAL
    else:
        status = SectionStatus.NOT_STARTED

    return SectionProgress(
        index=index,
        start_ratio=start_ratio,
        end_ratio=end_ratio,
        status=status,
        completion=completion,
        dominant_label=dominant_label,
    )


def _label_coverage(segments: list[Segment], image_area: int) -> dict[str, float]:
    if image_area <= 0:
        return {}

    coverage: dict[str, float] = defaultdict(float)
    for segment in segments:
        coverage[segment.label.value] += segment.area / image_area
    return dict(sorted(coverage.items()))

