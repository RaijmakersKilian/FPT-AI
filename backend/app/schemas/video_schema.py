from datetime import datetime

from pydantic import BaseModel, Field


# class VideoCreate(BaseModel):
#     filename: str = Field(..., min_length=1)
#     file_path: str = Field(..., min_length=1)
#     duration_seconds: int | None = Field(default=None, ge=0)
#     notes: str | None = None


class VideoResponse(BaseModel):
    id: str
    filename: str
    file_path: str
    duration_seconds: int | None = None
    total_frames: int | None = None
    file_size_mb: float | None = None
    uploaded_at: datetime
    notes: str | None = None


class VideoDeleteResponse(BaseModel):
    id: str
    deleted_file_path: str


class VideoUpdate(BaseModel):
    filename: str | None = None
    file_path: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    total_frames: int | None = Field(default=None, ge=0)
    notes: str | None = None