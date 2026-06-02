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


def extract_panorama_frames(
    video_path: Path,
    output_dir: Path,
    sample_every_n_frames: int = 3,
    blur_threshold: float = 150.0,
    motion_threshold: float = 0.003,
    target_frames: int = 600,
    start_frame: int = 0,
) -> list[Path]:
    """Extract sharp, overlapping frames from a drone video for panorama stitching.

    Uses denser sampling and a looser motion threshold compared to
    :func:`extract_keyframes` so that consecutive frames share enough overlap for
    reliable feature matching.  The blur threshold is intentionally stricter so
    that only in-focus frames reach the stitcher.

    Args:
        video_path: Path to the drone video file.
        output_dir: Directory where extracted JPEG frames are written.
        sample_every_n_frames: Examine one frame out of every N (default 3 for
            dense overlap; reduce to 1 for very short clips).
        blur_threshold: Laplacian variance below this value marks a frame as
            blurry and skips it.  Higher = stricter sharpness filter.
        motion_threshold: Minimum fraction of changed pixels between the current
            and previous sampled frame.  Very low (0.003) so nearly-static
            camera positions are accepted for good overlap.
        target_frames: Stop after collecting this many frames.

    Returns:
        Sorted list of paths to the extracted frame images.
    """
    cv2 = _import_cv2()
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    selected: list[Path] = []
    previous_gray = None
    frame_index = start_frame - 1

    try:
        while len(selected) < target_frames:
            ok, frame = cap.read()
            if not ok:
                break

            frame_index += 1
            if (frame_index - start_frame) % sample_every_n_frames != 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur = _blur_score(cv2, gray)
            motion = _motion_score(cv2, previous_gray, gray)
            previous_gray = gray

            if blur < blur_threshold or motion < motion_threshold:
                continue

            frame_path = output_dir / f"pano_{frame_index:08d}.jpg"
            cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            selected.append(frame_path)
    finally:
        cap.release()

    return sorted(selected)


def extract_mosaic_tiles(
    video_path: Path,
    output_dir: Path,
    n_tiles: int = 40,
    blur_threshold: float = 80.0,
    sample_every_n_frames: int = 5,
) -> list[Path]:
    """Extract *n_tiles* evenly-spaced tiles from a drone video for mosaic stitching.

    The video is divided into *n_tiles* equal-duration windows.  Within each
    window every *sample_every_n_frames*-th frame is evaluated and the
    sharpest frame that passes *blur_threshold* is saved as a tile.  If no
    frame in a window passes the threshold the sharpest frame regardless of
    blur is used as a fallback so every section of the bridge is represented.

    This approach guarantees full bridge coverage independent of drone speed
    and avoids the drift / failure modes of optical-flow based selection.

    Args:
        video_path: Path to the drone video.
        output_dir: Directory where tile JPEG images are written.
        n_tiles: Number of tiles to extract (one per equal-length window).
        blur_threshold: Minimum Laplacian variance; lower = more permissive.
        sample_every_n_frames: Check one frame in every N within each window
            (reduces CPU time while still finding a sharp candidate).

    Returns:
        Sorted list of tile image paths.
    """
    cv2 = _import_cv2()
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        total_frames = 999_999  # unknown length — read until EOF

    window_size = max(1.0, total_frames / n_tiles)

    selected: list[Path] = []
    current_window = 0
    best_frame = None
    best_blur = 0.0
    best_blur_any = 0.0   # best in window ignoring threshold (fallback)
    best_frame_any = None
    frame_index = -1

    def _commit(buf_frame):
        frame_path = output_dir / f"tile_{len(selected):04d}.jpg"
        cv2.imwrite(str(frame_path), buf_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        selected.append(frame_path)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_index += 1
            window = int(frame_index / window_size)

            if window > current_window:
                # Commit the sharpest frame from the finished window
                if best_frame is not None:
                    _commit(best_frame)
                elif best_frame_any is not None:
                    # No frame passed the threshold — use the least-blurry one
                    _commit(best_frame_any)
                if len(selected) >= n_tiles:
                    break
                current_window = window
                best_frame = None
                best_blur = 0.0
                best_frame_any = None
                best_blur_any = 0.0

            if frame_index % sample_every_n_frames != 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur = _blur_score(cv2, gray)

            if blur > best_blur_any:
                best_blur_any = blur
                best_frame_any = frame.copy()

            if blur >= blur_threshold and blur > best_blur:
                best_blur = blur
                best_frame = frame.copy()

        # Commit the last window
        if len(selected) < n_tiles:
            if best_frame is not None:
                _commit(best_frame)
            elif best_frame_any is not None:
                _commit(best_frame_any)
    finally:
        cap.release()

    return sorted(selected)

