import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated

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


class ProgressReportCreate(BaseModel):
    run_id: str
    element_type_id: str
    total_elements: Annotated[int, Field(ge=0)] = 0
    completed: Annotated[int, Field(ge=0)] = 0
    partial: Annotated[int, Field(ge=0)] = 0
    not_built: Annotated[int, Field(ge=0)] = 0
    completion_pct: Annotated[float | None, Field(ge=0, le=100)] = None
    current_stage: str | None = None
    pdf_path: str | None = None

    _normalize_run_id: classmethod = field_validator("run_id")(lambda v: validate_uuid(v, "run_id"))
    _normalize_element_type_id: classmethod = field_validator("element_type_id")(lambda v: validate_uuid(v, "element_type_id"))


class ProgressReportUpdate(BaseModel):
    run_id: str | None = None
    element_type_id: str | None = None
    total_elements: Annotated[int | None, Field(ge=0)] = None
    completed: Annotated[int | None, Field(ge=0)] = None
    partial: Annotated[int | None, Field(ge=0)] = None
    not_built: Annotated[int | None, Field(ge=0)] = None
    completion_pct: Annotated[float | None, Field(ge=0, le=100)] = None
    current_stage: str | None = None
    pdf_path: str | None = None
    generated_at: datetime | None = None

    _normalize_run_id: classmethod = field_validator("run_id")(lambda v: validate_uuid(v, "run_id"))
    _normalize_element_type_id: classmethod = field_validator("element_type_id")(lambda v: validate_uuid(v, "element_type_id"))


class ProgressReportResponse(BaseModel):
    id: str
    run_id: str
    element_type_id: str
    total_elements: int | None = None
    completed: int | None = None
    partial: int | None = None
    not_built: int | None = None
    completion_pct: float | None = None
    current_stage: str | None = None
    pdf_path: str | None = None
    generated_at: datetime | None = None

    @field_validator("completion_pct", mode="before")
    @classmethod
    def convert_decimal(cls, v):
        if isinstance(v, Decimal):
            return float(v)
        return v
