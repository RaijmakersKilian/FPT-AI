from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class SegmentLabel(str, Enum):
    COMPLETED_DECK = "completed_deck"
    FORMWORK = "formwork"
    EXPOSED_REBAR = "exposed_rebar"
    SUPPORT_COLUMN = "support_column"
    EQUIPMENT = "equipment"
    UNKNOWN = "unknown"


class SectionStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    NOT_STARTED = "not_started"


@dataclass(frozen=True)
class Keyframe:
    path: Path
    frame_index: int
    timestamp_seconds: float
    blur_score: float
    motion_score: float


@dataclass
class Segment:
    id: int
    mask: np.ndarray
    bbox_xyxy: tuple[int, int, int, int]
    area: int
    label: SegmentLabel = SegmentLabel.UNKNOWN
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SectionProgress:
    index: int
    start_ratio: float
    end_ratio: float
    status: SectionStatus
    completion: float
    dominant_label: str


@dataclass(frozen=True)
class ProgressReport:
    project_name: str
    sections: list[SectionProgress]
    overall_completion: float
    label_coverage: dict[str, float]
    inputs: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "project_name": self.project_name,
            "overall_completion": round(self.overall_completion, 4),
            "label_coverage": {k: round(v, 4) for k, v in self.label_coverage.items()},
            "sections": [
                {
                    "index": section.index,
                    "start_ratio": round(section.start_ratio, 4),
                    "end_ratio": round(section.end_ratio, 4),
                    "status": section.status.value,
                    "completion": round(section.completion, 4),
                    "dominant_label": section.dominant_label,
                }
                for section in self.sections
            ],
            "inputs": self.inputs,
        }

