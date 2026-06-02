from pydantic import BaseModel, Field


class ElementTypeProgress(BaseModel):
    element_type: str
    completed_percent: float = Field(..., ge=0, le=100)


class ReportResponse(BaseModel):
    run_id: str
    overall_progress: float = Field(..., ge=0, le=100)
    completed_elements: int = Field(..., ge=0)
    partial_elements: int = Field(..., ge=0)
    remaining_elements: int = Field(..., ge=0)
    element_type_progress: list[ElementTypeProgress]