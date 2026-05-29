from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ProgressWeights:
    completed_deck: float = 1.0
    support_column: float = 0.8
    formwork: float = 0.35
    exposed_rebar: float = 0.2
    equipment: float = 0.0
    unknown: float = 0.0

    def for_label(self, label: str) -> float:
        return float(getattr(self, label, self.unknown))


@dataclass(frozen=True)
class PipelineConfig:
    project_name: str = "GOT Bridge"
    sample_every_n_frames: int = 10
    blur_threshold: float = 120.0
    motion_threshold: float = 0.015
    target_keyframes: int = 400
    sections: int = 12
    weights: ProgressWeights = field(default_factory=ProgressWeights)

    @classmethod
    def from_json(cls, path: Path) -> "PipelineConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        weights = ProgressWeights(**data.pop("weights", {}))
        return cls(**data, weights=weights)

