from decimal import Decimal

from pydantic import BaseModel, field_validator

from app.schemas.report_schema import ProgressReportResponse


class ElementTypeBrief(BaseModel):
    name: str
    description: str | None = None
    color_hex: str | None = None


class ProgressReportEnrichedResponse(ProgressReportResponse):
    element_type: ElementTypeBrief | None = None

    @field_validator("completion_pct", mode="before")
    @classmethod
    def convert_decimal(cls, v):
        if isinstance(v, Decimal):
            return float(v)
        return v
