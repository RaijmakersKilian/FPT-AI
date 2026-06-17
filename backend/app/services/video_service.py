import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.db.supabase_storage import delete_file, get_db, path_from_public_url, upload_file
from app.schemas.video_schema import VideoDeleteResponse, VideoUpdate

VIDEOS_BUCKET = os.getenv("SUPABASE_VIDEOS_BUCKET", "videos")
TABLE = "video"

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def validate_video_file(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS and not (
        file.content_type and file.content_type.startswith("video/")
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only video files are allowed")


async def upload_video_file(file: UploadFile, notes: str | None = None):
    validate_video_file(file)

    video_id = str(uuid4())
    suffix = Path(file.filename).suffix.lower() or ".mp4"
    storage_path = f"{video_id}{suffix}"

    chunks = []
    while chunk := await file.read(1024 * 1024):
        chunks.append(chunk)
    file_bytes = b"".join(chunks)
    file_size_mb = round(len(file_bytes) / (1024 * 1024), 2)

    try:
        public_url = upload_file(VIDEOS_BUCKET, storage_path, file_bytes, file.content_type or "video/mp4")
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Failed to upload video to storage: {error}")

    try:
        result = get_db().table(TABLE).insert({
            "id": video_id,
            "filename": file.filename,
            "file_path": public_url,
            "file_size_mb": file_size_mb,
            "notes": notes,
        }).execute()
        return result.data[0]
    except Exception as error:
        delete_file(VIDEOS_BUCKET, storage_path)
        raise HTTPException(status_code=500, detail=f"Failed to save video metadata: {error}")


def get_all_videos(skip: int = 0, limit: int = 10):
    result = get_db().table(TABLE).select("*").order("uploaded_at", desc=True).limit(limit).offset(skip).execute()
    return result.data


def get_video_by_id(video_id: str):
    result = get_db().table(TABLE).select("*").eq("id", video_id).execute()
    return result.data[0] if result.data else None


def delete_video(video_id: str) -> VideoDeleteResponse:
    result = get_db().table(TABLE).select("file_path").eq("id", video_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    file_path = result.data[0]["file_path"]
    storage_path = path_from_public_url(file_path, VIDEOS_BUCKET)
    if storage_path:
        delete_file(VIDEOS_BUCKET, storage_path)

    get_db().table(TABLE).delete().eq("id", video_id).execute()
    return VideoDeleteResponse(id=video_id, deleted_file_path=file_path)


def update_video(video_id: str, data: VideoUpdate) -> dict:
    updates = {}
    if data.filename is not None:        updates["filename"] = data.filename
    if data.file_path is not None:       updates["file_path"] = data.file_path
    if data.duration_seconds is not None: updates["duration_seconds"] = data.duration_seconds
    if data.total_frames is not None:    updates["total_frames"] = data.total_frames
    if data.notes is not None:           updates["notes"] = data.notes

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    check = get_db().table(TABLE).select("id").eq("id", video_id).execute()
    if not check.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    result = get_db().table(TABLE).update(updates).eq("id", video_id).execute()
    return result.data[0]
