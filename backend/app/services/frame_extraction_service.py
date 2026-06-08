"""
frame_extraction_service.py
----------------------------
Reads a video using OpenCV, extracts representative frames, and saves them to
storage/frames/{run_id}/.

Frame extraction logic
~~~~~~~~~~~~~~~~~~~~~~
1. Calculate the extraction interval in frames using interval_seconds × FPS
   (or use interval_frames if it is provided).
2. For each candidate frame:
   a. **Blur detection** – compute the Variance of Laplacian on the grayscale image;
      if it is below blur_threshold, skip the frame because it is blurry.
   b. **Motion/difference filtering** – compute the mean absolute difference
      compared to the most recently saved frame; if it is below diff_threshold,
      skip the frame because it is too similar to the previous saved frame.
3. Valid frames are saved as JPEG files with the name `frame_{idx:06d}.jpg`
   where idx is the frame index in the original video.

DB updates
~~~~~~~~~~
- video.duration_seconds, video.total_frames
- processing_run.frames_extracted
- processing_run.status  →  'completed'  (or 'failed' if an error occurs)
- processing_run.completed_at
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException, status

from app.db.database import get_connection
from app.schemas.frame_extraction_schema import (
    ExtractFramesRequest,
    ExtractFramesResponse,
)

logger = logging.getLogger(__name__)

FRAMES_BASE_DIR = Path(os.getenv("FRAMES_DIR", "storage/frames"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_run_and_video(run_id: str) -> tuple[str, str]:
    """
    Returns (video_id, file_path) from processing_run JOIN video.
    Raises 404 if run_id does not exist, and 500 if the video has no file_path.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pr.video_id, v.file_path
                FROM processing_run pr
                JOIN video v ON v.id = pr.video_id
                WHERE pr.id = %s;
                """,
                (run_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Processing run '{run_id}' not found",
        )

    video_id, file_path = str(row[0]), row[1]

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Video file_path is empty – the video may not have been uploaded yet",
        )

    return video_id, file_path


def _mark_run_failed(run_id: str, reason: str) -> None:
    """Updates processing_run.status to 'failed' when an error occurs."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE processing_run
                    SET status = 'failed',
                        completed_at = %s
                    WHERE id = %s;
                    """,
                    (datetime.now(timezone.utc), run_id),
                )
                conn.commit()
    except Exception as db_err:  # noqa: BLE001
        logger.error("Could not mark run %s as failed: %s", run_id, db_err)
    logger.error("Run %s failed: %s", run_id, reason)


def _is_blurry(gray: np.ndarray, threshold: float) -> bool:
    """Returns True if the frame is blurry (Variance of Laplacian < threshold)."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var()) < threshold


def _mean_diff(frame_bgr: np.ndarray, prev_bgr: np.ndarray | None) -> float:
    """Mean absolute pixel difference compared to the previous frame (0-255)."""
    if prev_bgr is None:
        return float("inf")
    return float(np.mean(np.abs(frame_bgr.astype(np.int16) - prev_bgr.astype(np.int16))))


# ---------------------------------------------------------------------------
# DB update helpers
# ---------------------------------------------------------------------------

def _update_video_meta(video_id: str, duration_seconds: float, total_frames: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video
                SET duration_seconds = %s,
                    total_frames     = %s
                WHERE id = %s;
                """,
                (round(duration_seconds, 3), total_frames, video_id),
            )
            conn.commit()


def _update_run_completed(run_id: str, frames_extracted: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE processing_run
                SET frames_extracted = %s,
                    status           = 'completed',
                    completed_at     = %s
                WHERE id = %s;
                """,
                (frames_extracted, datetime.now(timezone.utc), run_id),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Public service function
# ---------------------------------------------------------------------------

def extract_frames(run_id: str, params: ExtractFramesRequest) -> ExtractFramesResponse:
    video_id, file_path = _get_run_and_video(run_id)

    video_path = Path(file_path)
    if not video_path.exists():
        _mark_run_failed(run_id, f"Video file not found: {file_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video file not found on disk: {file_path}",
        )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        _mark_run_failed(run_id, "cv2 could not open video")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot open video file with OpenCV",
        )

    try:
        fps: float = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds: float = total_frames / fps if fps > 0 else 0.0

        logger.info(
            "Run %s | video %s | FPS=%.2f total_frames=%d duration=%.1fs",
            run_id, video_id, fps, total_frames, duration_seconds,
        )

        if params.interval_frames is not None:
            interval: int = max(1, params.interval_frames)
        else:
            interval = max(1, int(round(fps * params.interval_seconds)))


        out_dir = FRAMES_BASE_DIR / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        saved_count = 0
        prev_frame_bgr: np.ndarray | None = None
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if _is_blurry(gray, params.blur_threshold):
                    logger.debug("Frame %d skipped (blurry)", frame_idx)
                    frame_idx += 1
                    continue

                diff = _mean_diff(frame, prev_frame_bgr)
                if diff < params.diff_threshold:
                    logger.debug("Frame %d skipped (too similar, diff=%.2f)", frame_idx, diff)
                    frame_idx += 1
                    continue

                out_name = f"frame_{frame_idx:06d}.jpg"
                out_path = out_dir / out_name
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, params.jpeg_quality]
                cv2.imwrite(str(out_path), frame, encode_params)

                prev_frame_bgr = frame.copy()
                saved_count += 1
                logger.debug("Saved %s (diff=%.2f)", out_name, diff)

            frame_idx += 1

    except Exception as exc:
        _mark_run_failed(run_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Frame extraction failed: {exc}",
        ) from exc
    finally:
        cap.release()

    _update_video_meta(video_id, duration_seconds, total_frames)
    _update_run_completed(run_id, saved_count)

    logger.info("Run %s complete – %d frames saved to %s", run_id, saved_count, out_dir)

    return ExtractFramesResponse(
        run_id=run_id,
        video_id=video_id,
        video_duration_seconds=round(duration_seconds, 3),
        video_total_frames=total_frames,
        frames_extracted=saved_count,
        frames_dir=str(out_dir),
        status="completed",
    )
