import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.db.database import get_connection
from app.schemas.video_schema import VideoDeleteResponse, VideoUpdate

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "storage/videos"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm"
}


def row_to_video_dict(row):
    return {
        "id": str(row[0]),
        "filename": row[1],
        "file_path": row[2],
        "duration_seconds": row[3],
        "total_frames": row[4],
        "file_size_mb": float(row[5]) if row[5] is not None else None,
        "uploaded_at": row[6],
        "notes": row[7],
    }


def validate_video_file(file: UploadFile):
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )

    suffix = Path(file.filename).suffix.lower()

    is_valid_extension = suffix in ALLOWED_VIDEO_EXTENSIONS
    is_valid_content_type = (
        file.content_type is not None
        and file.content_type.startswith("video/")
    )

    if not is_valid_extension and not is_valid_content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only video files are allowed"
        )


async def upload_video_file(file: UploadFile, notes: str | None = None):
    validate_video_file(file)

    video_id = str(uuid4())
    suffix = Path(file.filename).suffix.lower() or ".mp4"
    saved_filename = f"{video_id}{suffix}"
    save_path = UPLOAD_DIR / saved_filename

    file_size_bytes = 0

    try:
        with save_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                file_size_bytes += len(chunk)
                buffer.write(chunk)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save video file: {error}"
        )

    file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO video (
                        id,
                        filename,
                        file_path,
                        file_size_mb,
                        notes
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        filename,
                        file_path,
                        duration_seconds,
                        total_frames,
                        file_size_mb,
                        uploaded_at,
                        notes;
                    """,
                    (
                        video_id,
                        file.filename,
                        str(save_path),
                        file_size_mb,
                        notes,
                    )
                )

                row = cur.fetchone()
                conn.commit()

        return row_to_video_dict(row)

    except Exception as error:
        if save_path.exists():
            save_path.unlink()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save video metadata to database: {error}"
        )


def get_all_videos(skip: int = 0, limit: int = 10):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    filename,
                    file_path,
                    duration_seconds,
                    total_frames,
                    file_size_mb,
                    uploaded_at,
                    notes
                FROM video
                ORDER BY uploaded_at DESC
                LIMIT %s OFFSET %s;
                """,
                (limit, skip)
            )

            rows = cur.fetchall()

    return [row_to_video_dict(row) for row in rows]


def get_video_by_id(video_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    filename,
                    file_path,
                    duration_seconds,
                    total_frames,
                    file_size_mb,
                    uploaded_at,
                    notes
                FROM video
                WHERE id = %s;
                """,
                (video_id,)
            )

            row = cur.fetchone()

    if row is None:
        return None

    return row_to_video_dict(row)


def delete_video(video_id: str) -> VideoDeleteResponse:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT file_path FROM video WHERE id = %s;",
                (video_id,)
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )

    file_path = row[0]

    try:
        Path(file_path).unlink(missing_ok=True)
    except OSError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete video file: {error}"
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM video WHERE id = %s;",
                (video_id,)
            )
            conn.commit()

    return VideoDeleteResponse(id=video_id, deleted_file_path=file_path)


def update_video(video_id: str, data: VideoUpdate) -> dict:
    updates = {}
    if data.filename is not None:
        updates["filename"] = data.filename
    if data.file_path is not None:
        updates["file_path"] = data.file_path
    if data.duration_seconds is not None:
        updates["duration_seconds"] = data.duration_seconds
    if data.total_frames is not None:
        updates["total_frames"] = data.total_frames
    if data.notes is not None:
        updates["notes"] = data.notes

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [video_id]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM video WHERE id = %s;",
                (video_id,)
            )
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video not found"
                )

            cur.execute(
                f"UPDATE video SET {set_clause} WHERE id = %s "
                "RETURNING id, filename, file_path, duration_seconds, "
                "total_frames, file_size_mb, uploaded_at, notes;",
                values
            )
            row = cur.fetchone()
            conn.commit()

    return row_to_video_dict(row)