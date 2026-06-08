from pydantic import BaseModel, Field


class ExtractFramesRequest(BaseModel):
    """
    Optional request body for POST /processing-runs/{run_id}/extract-frames.
    If no body is provided, the default values will be used.
    """
    interval_seconds: float = Field(
        default=5.0,
        gt=0,
        description="Extract one frame every N seconds. Takes priority over interval_frames.",
    )
    interval_frames: int | None = Field(
        default=None,
        gt=0,
        description="Extract one frame every N frames. Used when interval_seconds is None.",
    )
    blur_threshold: float = Field(
        default=100.0,
        gt=0,
        description=(
            "The Variance of Laplacian must be greater than or equal to this threshold "
            "for the frame to be kept. Used for blur filtering."
        ),
    )
    diff_threshold: float = Field(
        default=5.0,
        ge=0,
        description=(
            "The minimum mean pixel difference between consecutive frames, measured "
            "on a 0-255 scale. Frames that are too similar will be skipped."
        ),
    )
    jpeg_quality: int = Field(
        default=90,
        ge=10,
        le=100,
        description="JPEG quality used when saving extracted frames. Value must be between 10 and 100.",
    )


class ExtractFramesResponse(BaseModel):
    run_id: str
    video_id: str
    video_duration_seconds: float
    video_total_frames: int
    frames_extracted: int
    frames_dir: str
    status: str