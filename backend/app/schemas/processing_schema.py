import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

VALID_STATUSES = frozenset(["pending", "running", "completed", "failed"])


def validate_uuid(v: str | None, field_name: str) -> str | None:
    if v is None:
        return None
    if not UUID_RE.match(v):
        raise ValueError(f"{field_name} must be a valid UUID")
    return v


class ProcessingRunCreate(BaseModel):
    video_id: str
    element_type_id: str | None = None

    _normalize_video_id: classmethod = field_validator("video_id")(lambda v: validate_uuid(v, "video_id"))
    _normalize_element_type_id: classmethod = field_validator("element_type_id")(lambda v: validate_uuid(v, "element_type_id"))


class ProcessingRunUpdate(BaseModel):
    element_type_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: str | None = None
    frames_extracted: int | None = Field(default=None, ge=0)
    pointcloud_path: str | None = None
    detections_path: str | None = None
    bim_model_path: str | None = None

    _normalize_element_type_id: classmethod = field_validator("element_type_id")(lambda v: validate_uuid(v, "element_type_id"))
    _validate_status: classmethod = field_validator("status")(lambda v: v if v is None or v in VALID_STATUSES else (_ for _ in ()).throw(ValueError("status must be one of: pending, running, completed, failed")))


class ProcessingRunResponse(BaseModel):
    id: str
    video_id: str
    element_type_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: str
    frames_extracted: int | None = None
    pointcloud_path: str | None = None
    detections_path: str | None = None
    bim_model_path: str | None = None
