from pydantic import BaseModel, Field


class ProcessingRunCreate(BaseModel):
    video_id: str = Field(..., min_length=1)
    element_type_id: int | None = None


class ProcessingRunResponse(BaseModel):
    run_id: str
    video_id: str
    status: str
    message: str


class ProcessingStatusResponse(BaseModel):
    run_id: str
    status: str
    progress: int
    current_stage: str