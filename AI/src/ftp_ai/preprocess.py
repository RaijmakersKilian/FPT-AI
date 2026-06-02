from __future__ import annotations

from pathlib import Path


def crop_black_borders(image_path: Path, output_path: Path, threshold: int = 8) -> Path:
    cv2 = _import_cv2()
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    coords = cv2.findNonZero(mask)
    if coords is None:
        _write_image(cv2, output_path, image)
        return output_path

    x, y, width, height = cv2.boundingRect(coords)
    cropped = image[y : y + height, x : x + width]
    _write_image(cv2, output_path, cropped)
    return output_path


def resize_to_max_dimension(image_path: Path, output_path: Path, max_dimension: int) -> Path:
    cv2 = _import_cv2()
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Could not load image: {image_path}")

    height, width = image.shape[:2]
    largest = max(height, width)
    if max_dimension <= 0 or largest <= max_dimension:
        _write_image(cv2, output_path, image)
        return output_path

    scale = max_dimension / largest
    resized = cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))))
    _write_image(cv2, output_path, resized)
    return output_path


def _write_image(cv2, output_path: Path, image) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), image):
        raise RuntimeError(f"Could not write image: {output_path}")


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for preprocessing. Install opencv-python.") from exc
    return cv2
