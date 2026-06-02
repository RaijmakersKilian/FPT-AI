from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from .report import render_annotated_image
from .segmentation import Segmenter


def build_segmentation_overlay_video(
    video_path: Path,
    output_dir: Path,
    segmenter: Segmenter,
    sample_every_n_frames: int = 60,
    max_dimension: int = 960,
    output_fps: float = 6.0,
    max_frames: int | None = None,
) -> dict[str, object]:
    """Create a sampled video with segmentation masks overlaid on each frame."""

    cv2 = _import_cv2()
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"
    annotated_dir = output_dir / "annotated_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    annotated_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    output_path = output_dir / "sam2_overlay.mp4"

    writer = None
    processed = 0
    frame_index = -1
    started = perf_counter()
    segment_counts: list[int] = []

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frame_index += 1
            if frame_index % sample_every_n_frames != 0:
                continue
            if max_frames is not None and processed >= max_frames:
                break

            frame = _fit_within(cv2, frame, max_dimension)
            frame_path = frames_dir / f"frame_{frame_index:08d}.jpg"
            cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])

            segments = segmenter.segment(frame_path)
            segment_counts.append(len(segments))
            annotated = render_annotated_image(frame, segments)

            if writer is None:
                height, width = annotated.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(output_path), fourcc, output_fps, (width, height))
                if not writer.isOpened():
                    raise RuntimeError(f"Could not open video writer: {output_path}")

            writer.write(annotated)
            cv2.imwrite(
                str(annotated_dir / f"annotated_{frame_index:08d}.jpg"),
                annotated,
                [cv2.IMWRITE_JPEG_QUALITY, 92],
            )
            processed += 1
    finally:
        cap.release()
        if writer is not None:
            writer.release()

    if processed == 0:
        raise RuntimeError("No frames were processed for the overlay video.")

    summary: dict[str, object] = {
        "video": str(video_path),
        "output_video": str(output_path),
        "source_fps": round(float(source_fps), 3),
        "source_total_frames": total_frames,
        "sample_every_n_frames": sample_every_n_frames,
        "output_fps": output_fps,
        "processed_frames": processed,
        "max_dimension": max_dimension,
        "average_segments_per_frame": round(sum(segment_counts) / len(segment_counts), 2),
        "duration_seconds": round(perf_counter() - started, 2),
    }
    (output_dir / "overlay_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _fit_within(cv2, image, max_dimension: int):
    height, width = image.shape[:2]
    largest = max(height, width)
    if largest <= max_dimension:
        return image
    scale = max_dimension / largest
    size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(image, size)


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for video overlay output.") from exc
    return cv2
