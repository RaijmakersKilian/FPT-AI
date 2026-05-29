from __future__ import annotations

import numpy as np

from AI.src.ftp_ai.config import PipelineConfig
from AI.src.ftp_ai.models import Segment, SegmentLabel, SectionStatus
from AI.src.ftp_ai.progress import estimate_progress


def test_progress_marks_completed_section_when_completed_deck_dominates() -> None:
    mask = np.ones((10, 50), dtype=bool)
    segment = Segment(
        id=1,
        mask=mask,
        bbox_xyxy=(0, 0, 50, 10),
        area=500,
        label=SegmentLabel.COMPLETED_DECK,
        confidence=0.9,
    )

    report = estimate_progress(
        segments=[segment],
        image_shape=(10, 100),
        config=PipelineConfig(sections=2),
    )

    assert report.sections[0].status == SectionStatus.COMPLETE
    assert report.sections[0].completion == 1.0
    assert report.sections[1].status == SectionStatus.NOT_STARTED
    assert report.overall_completion == 0.5


def test_progress_counts_formwork_as_partial_completion() -> None:
    mask = np.ones((10, 100), dtype=bool)
    segment = Segment(
        id=1,
        mask=mask,
        bbox_xyxy=(0, 0, 100, 10),
        area=1000,
        label=SegmentLabel.FORMWORK,
        confidence=0.7,
    )

    report = estimate_progress(
        segments=[segment],
        image_shape=(10, 100),
        config=PipelineConfig(sections=1),
    )

    assert report.sections[0].status == SectionStatus.PARTIAL
    assert report.sections[0].completion == 0.35
    assert report.label_coverage["formwork"] == 1.0

