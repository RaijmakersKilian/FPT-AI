from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.video_schema import VideoDeleteResponse, VideoResponse, VideoUpdate
from app.services.video_service import (
    delete_video,
    get_all_videos,
    get_video_by_id,
    update_video,
    upload_video_file,
)

router = APIRouter()


@router.get("", response_model=list[VideoResponse])
def read_videos(skip: int = 0, limit: int = 10):
    return get_all_videos(skip=skip, limit=limit)


@router.get("/{video_id}", response_model=VideoResponse)
def read_video(video_id: str):
    video = get_video_by_id(video_id)

    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    return video


@router.patch("/{video_id}", response_model=VideoResponse)
def patch_video(video_id: str, data: VideoUpdate):
    return update_video(video_id=video_id, data=data)


@router.post(
    "/upload",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_video(
    file: UploadFile = File(...),
    notes: str | None = Form(default=None)
):
    return await upload_video_file(file=file, notes=notes)


@router.delete("/{video_id}", response_model=VideoDeleteResponse)
def delete_video_endpoint(video_id: str):
    return delete_video(video_id)