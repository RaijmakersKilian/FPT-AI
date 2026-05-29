from __future__ import annotations

from pathlib import Path

from .models import Keyframe


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for video processing. Install opencv-python.") from exc
    return cv2


def _blur_score(cv2, gray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _motion_score(cv2, previous_gray, gray) -> float:
    if previous_gray is None:
        return 1.0
    diff = cv2.absdiff(previous_gray, gray)
    changed = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]
    return float(changed.mean() / 255.0)


def extract_keyframes(
    video_path: Path,
    output_dir: Path,
    sample_every_n_frames: int = 10,
    blur_threshold: float = 120.0,
    motion_threshold: float = 0.015,
    target_keyframes: int = 400,
) -> list[Keyframe]:
    cv2 = _import_cv2()
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    selected: list[Keyframe] = []
    previous_gray = None
    frame_index = -1

    try:
        while len(selected) < target_keyframes:
            ok, frame = cap.read()
            if not ok:
                break

            frame_index += 1
            if frame_index % sample_every_n_frames != 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur = _blur_score(cv2, gray)
            motion = _motion_score(cv2, previous_gray, gray)
            previous_gray = gray

            if blur < blur_threshold or motion < motion_threshold:
                continue

            frame_path = output_dir / f"frame_{frame_index:08d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            selected.append(
                Keyframe(
                    path=frame_path,
                    frame_index=frame_index,
                    timestamp_seconds=frame_index / fps,
                    blur_score=blur,
                    motion_score=motion,
                )
            )
    finally:
        cap.release()

    return selected

