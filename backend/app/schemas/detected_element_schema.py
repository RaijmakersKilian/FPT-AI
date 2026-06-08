import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator


UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def validate_uuid(v: str | None, field_name: str) -> str | None:
    if v is None:
        return None
    if not UUID_RE.match(v):
        raise ValueError(f"{field_name} must be a valid UUID")
    return v


class DetectedElementCreate(BaseModel):
    run_id: str
    element_type_id: str
    frame_id: int = Field(ge=0)
    confidence: Annotated[float | None, Field(ge=0, le=1)] = None
    bbox_x1: Annotated[float | None, Field(ge=0)] = None
    bbox_y1: Annotated[float | None, Field(ge=0)] = None
    bbox_x2: Annotated[float | None, Field(ge=0)] = None
    bbox_y2: Annotated[float | None, Field(ge=0)] = None
    mask_polygon: dict[str, Any] | None = None
    depth_estimate_m: Annotated[float | None, Field(ge=0)] = None

    _normalize_run_id: classmethod = field_validator("run_id")(lambda v: validate_uuid(v, "run_id"))
    _normalize_element_type_id: classmethod = field_validator("element_type_id")(lambda v: validate_uuid(v, "element_type_id"))


class DetectedElementUpdate(BaseModel):
    run_id: str | None = None
    element_type_id: str | None = None
    frame_id: Annotated[int | None, Field(ge=0)] = None
    confidence: Annotated[float | None, Field(ge=0, le=1)] = None
    bbox_x1: Annotated[float | None, Field(ge=0)] = None
    bbox_y1: Annotated[float | None, Field(ge=0)] = None
    bbox_x2: Annotated[float | None, Field(ge=0)] = None
    bbox_y2: Annotated[float | None, Field(ge=0)] = None
    mask_polygon: dict[str, Any] | None = None
    depth_estimate_m: Annotated[float | None, Field(ge=0)] = None
    detected_at: datetime | None = None

    _normalize_run_id: classmethod = field_validator("run_id")(lambda v: validate_uuid(v, "run_id"))
    _normalize_element_type_id: classmethod = field_validator("element_type_id")(lambda v: validate_uuid(v, "element_type_id"))


class DetectedElementResponse(BaseModel):
    id: str
    run_id: str
    element_type_id: str
    frame_id: int
    confidence: float | None = None
    bbox_x1: float | None = None
    bbox_y1: float | None = None
    bbox_x2: float | None = None
    bbox_y2: float | None = None
    mask_polygon: dict[str, Any] | None = None
    depth_estimate_m: float | None = None
    detected_at: datetime | None = None

    @field_validator("confidence", "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2", "depth_estimate_m", mode="before")
    @classmethod
    def convert_decimal(cls, v):
        if isinstance(v, Decimal):
            return float(v)
        return v
