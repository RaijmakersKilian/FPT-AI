from __future__ import annotations

from math import ceil, sqrt
from pathlib import Path


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for panorama generation. Install opencv-python.") from exc
    return cv2


def stitch_images(
    image_paths: list[Path],
    output_path: Path,
    max_images: int = 24,
    max_dimension: int = 4096,
) -> Path:
    if not image_paths:
        raise ValueError("No images were provided for panorama generation.")

    cv2 = _import_cv2()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chosen = _spread_selection(image_paths, max_images)
    images = [cv2.imread(str(path)) for path in chosen]
    images = [image for image in images if image is not None]
    if not images:
        raise ValueError("None of the provided images could be loaded.")
    if len(images) == 1:
        _write_image(cv2, output_path, _fit_within(cv2, images[0], max_dimension))
        return output_path

    stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
    status, stitched = stitcher.stitch(images)

    if status == cv2.Stitcher_OK:
        stitched = _fit_within(cv2, stitched, max_dimension)
        _write_image(cv2, output_path, stitched)
        return output_path

    fallback = _grid_contact_sheet(cv2, images, max_dimension=max_dimension)
    _write_image(cv2, output_path, fallback)
    return output_path


def _spread_selection(paths: list[Path], limit: int) -> list[Path]:
    if len(paths) <= limit:
        return paths
    step = len(paths) / limit
    return [paths[int(i * step)] for i in range(limit)]


def _grid_contact_sheet(cv2, images, max_dimension: int):
    columns = ceil(sqrt(len(images)))
    rows = ceil(len(images) / columns)
    tile_width = max(1, max_dimension // columns)
    tile_height = max(1, max_dimension // rows)

    resized = []
    for image in images:
        height, width = image.shape[:2]
        scale = min(1.0, tile_width / width, tile_height / height)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        resized.append(cv2.resize(image, new_size))

    sheet = None
    for row_index in range(rows):
        row_images = resized[row_index * columns : (row_index + 1) * columns]
        if not row_images:
            continue
        row = _pad_row(cv2, row_images, tile_width, tile_height, columns)
        sheet = row if sheet is None else cv2.vconcat([sheet, row])
    return sheet


def _pad_row(cv2, images, tile_width: int, tile_height: int, columns: int):
    import numpy as np

    tiles = []
    for image in images:
        canvas = np.zeros((tile_height, tile_width, 3), dtype=image.dtype)
        height, width = image.shape[:2]
        canvas[:height, :width] = image
        tiles.append(canvas)

    while len(tiles) < columns:
        tiles.append(np.zeros((tile_height, tile_width, 3), dtype=tiles[0].dtype))
    return cv2.hconcat(tiles)


def _fit_within(cv2, image, max_dimension: int):
    height, width = image.shape[:2]
    largest = max(height, width)
    if largest <= max_dimension:
        return image
    scale = max_dimension / largest
    size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(image, size)


def _write_image(cv2, output_path: Path, image) -> None:
    if image is None or not cv2.imwrite(str(output_path), image):
        raise RuntimeError(f"Could not write panorama image: {output_path}")
