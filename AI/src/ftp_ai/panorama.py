from __future__ import annotations

from math import ceil, sqrt
from pathlib import Path


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for panorama generation. Install opencv-python.") from exc
    return cv2


def build_slitscan_panorama(
    image_paths: list[Path],
    output_path: Path,
    work_width: int = 1280,
    max_dimension: int = 8192,
) -> Path:
    """Build a panorama by concatenating thin strips sliced from each frame.

    Measures the average horizontal motion between the first few frame pairs
    using SIFT, then takes a strip of that width from the LEADING EDGE of every
    frame and concatenates them.  No global alignment is needed so camera
    rotation does not accumulate into artefacts.  Works best for footage where
    the drone flies at roughly constant speed with a consistent camera angle.
    """
    if not image_paths:
        raise ValueError("No images provided.")

    cv2 = _import_cv2()
    import numpy as np

    output_path.parent.mkdir(parents=True, exist_ok=True)
    images = [_read_for_strip(cv2, p, work_width) for p in image_paths]
    images = [img for img in images if img is not None]
    if len(images) < 2:
        raise ValueError("Need at least 2 readable images.")

    # Measure average step size from the first few pairs
    steps = []
    for i in range(min(8, len(images) - 1)):
        t = _estimate_drone_transform(cv2, images[i], images[i + 1])
        if t is not None:
            steps.append(abs(t[0, 2]))
    if not steps:
        raise RuntimeError("Could not estimate motion between frames — try a shorter clip or lower --blur-threshold.")

    step = max(1, int(round(float(np.median(steps)))))

    # First frame in full, then only the new leading-edge strip from each subsequent frame
    strips = [images[0]]
    for img in images[1:]:
        h, w = img.shape[:2]
        strip = img[:, max(0, w - step):]
        if strip.shape[1] > 0:
            strips.append(strip)

    panorama = cv2.hconcat(strips)
    panorama = _fit_within(cv2, panorama, max_dimension)
    _write_image(cv2, output_path, panorama)
    return output_path


def stitch_images(
    image_paths: list[Path],
    output_path: Path,
    max_images: int = 24,
    max_dimension: int = 4096,
    allow_contact_sheet: bool = True,
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

    stitched = _try_stitch(cv2, image_paths, max_images=max_images)
    if stitched is not None:
        stitched = _fit_within(cv2, stitched, max_dimension)
        _write_image(cv2, output_path, stitched)
        return output_path

    if not allow_contact_sheet:
        raise RuntimeError("Could not stitch images into a panorama.")

    fallback = _grid_contact_sheet(cv2, images, max_dimension=max_dimension)
    _write_image(cv2, output_path, fallback)
    return output_path


def build_smooth_panorama(
    image_paths: list[Path],
    output_path: Path,
    max_dimension: int = 4096,
) -> Path:
    if not image_paths:
        raise ValueError("No images were provided for panorama generation.")

    cv2 = _import_cv2()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stitched = _try_stitch(cv2, image_paths, max_images=len(image_paths))
    if stitched is None:
        raise RuntimeError(
            "Could not create a smooth panorama. Try extracting more overlapping frames "
            "or use a shorter bridge-only clip."
        )

    stitched = _fit_within(cv2, stitched, max_dimension)
    _write_image(cv2, output_path, stitched)
    return output_path


def build_strip_panorama(
    image_paths: list[Path],
    output_path: Path,
    max_images: int = 80,
    work_width: int = 960,
    max_dimension: int = 4096,
) -> Path:
    if not image_paths:
        raise ValueError("No images were provided for panorama generation.")

    cv2 = _import_cv2()
    import numpy as np

    output_path.parent.mkdir(parents=True, exist_ok=True)
    chosen = image_paths[:max_images]
    images = [_read_for_strip(cv2, path, work_width) for path in chosen]
    images = [image for image in images if image is not None]
    if len(images) < 2:
        raise ValueError("At least two readable images are required for strip panorama generation.")

    transforms = [np.eye(3, dtype=np.float64)]
    used_images = [images[0]]
    previous = images[0]
    for current in images[1:]:
        transform = _estimate_pair_transform(cv2, previous, current)
        if transform is None:
            continue
        transforms.append(transforms[-1] @ transform)
        used_images.append(current)
        previous = current

    if len(used_images) < 2:
        raise RuntimeError("Could not align neighboring frames into a strip panorama.")

    canvas_transform, canvas_size = _canvas_transform(used_images, transforms)
    panorama = _blend_warped_images(cv2, used_images, transforms, canvas_transform, canvas_size)
    panorama = _crop_non_empty(cv2, panorama)
    panorama = _fit_within(cv2, panorama, max_dimension)
    _write_image(cv2, output_path, panorama)
    return output_path


def build_drone_panorama(
    image_paths: list[Path],
    output_path: Path,
    max_images: int = 120,
    work_width: int = 1280,
    max_dimension: int = 8192,
    rotate_cw90: bool = False,
) -> Path:
    """Stitch sequential drone frames into a high-quality bridge panorama.

    Compared to :func:`build_strip_panorama` this function uses SIFT features
    (with ORB as fall-back) and a full perspective homography instead of an
    affine transform, which correctly handles the altitude and angle changes
    typical of drone footage.  Seams are softened with a wide distance-transform
    feather so the final image looks seamless.

    Args:
        image_paths: Ordered list of frame paths (typically from
            :func:`~ftp_ai.video.extract_panorama_frames`).
        output_path: Where to write the output JPEG.
        max_images: Maximum number of frames to use.  Frames are taken from
            the start of the list up to this limit.
        work_width: Frames are scaled to this width before feature extraction
            to keep memory use manageable.
        max_dimension: Longest side of the final output image.

    Returns:
        Path to the written panorama image.
    """
    if not image_paths:
        raise ValueError("No images were provided for panorama generation.")

    cv2 = _import_cv2()
    import numpy as np

    output_path.parent.mkdir(parents=True, exist_ok=True)
    chosen = image_paths[:max_images]
    images = [_read_for_strip(cv2, path, work_width) for path in chosen]
    images = [img for img in images if img is not None]
    if rotate_cw90:
        images = [cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE) for img in images]
    if len(images) < 2:
        raise ValueError("At least two readable images are required for drone panorama.")

    transforms: list = [np.eye(3, dtype=np.float64)]
    used_images = [images[0]]
    previous = images[0]

    for current in images[1:]:
        transform = _estimate_drone_transform(cv2, previous, current)
        if transform is None:
            # Skip unaligned frame but keep the previous anchor so the chain
            # does not drift.
            continue
        transforms.append(transforms[-1] @ transform)
        used_images.append(current)
        previous = current

    if len(used_images) < 2:
        raise RuntimeError(
            "Could not align drone frames into a panorama.  "
            "Try extracting denser frames (--sample-every 2) or check that the "
            "bridge is visible throughout the clip."
        )

    transforms = _correct_chain_drift(transforms)
    canvas_transform, canvas_size = _canvas_transform(used_images, transforms)
    panorama = _blend_warped_images_wide(cv2, used_images, transforms, canvas_transform, canvas_size)
    panorama = _crop_non_empty(cv2, panorama)
    panorama = _fit_within(cv2, panorama, max_dimension)
    _write_image(cv2, output_path, panorama)
    return output_path


def _correct_chain_drift(transforms: list) -> list:
    """Reduce accumulated drift in a chain of cumulative similarity matrices.

    Fits a linear trend through the translation AND rotation components and
    pulls each transform 70 % of the way toward that trend, spreading residual
    errors evenly rather than letting them pile up at the far end.
    """
    import numpy as np

    n = len(transforms)
    if n < 3:
        return transforms

    txs = np.array([T[0, 2] for T in transforms], dtype=float)
    tys = np.array([T[1, 2] for T in transforms], dtype=float)
    angles = np.array([np.arctan2(T[1, 0], T[0, 0]) for T in transforms], dtype=float)
    indices = np.arange(n, dtype=float)

    tx_trend = np.polyval(np.polyfit(indices, txs, 1), indices)
    ty_trend = np.polyval(np.polyfit(indices, tys, 1), indices)
    angle_trend = np.polyval(np.polyfit(indices, angles, 1), indices)

    corrected = []
    for i, T in enumerate(transforms):
        T_corr = T.copy()
        T_corr[0, 2] = txs[i] - 0.70 * (txs[i] - tx_trend[i])
        T_corr[1, 2] = tys[i] - 0.70 * (tys[i] - ty_trend[i])
        corrected_angle = angles[i] - 0.70 * (angles[i] - angle_trend[i])
        T_corr[0, 0] = np.cos(corrected_angle)
        T_corr[0, 1] = -np.sin(corrected_angle)
        T_corr[1, 0] = np.sin(corrected_angle)
        T_corr[1, 1] = np.cos(corrected_angle)
        corrected.append(T_corr)
    return corrected


def _estimate_drone_transform(cv2, previous, current):
    """Estimate the similarity transform (rotation + uniform scale + translation) that maps
    *current* onto *previous*.

    Uses a similarity transform instead of a full homography to prevent perspective
    distortion from accumulating across many frames. Tries SIFT first; falls back to ORB.
    Returns a 3x3 float64 matrix (affine embedded in homogeneous coords), or None.
    """
    import numpy as np

    previous_gray = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)

    try:
        detector = cv2.SIFT_create(nfeatures=3000)
        norm = cv2.NORM_L2
        min_matches = 16
    except AttributeError:
        detector = cv2.ORB_create(nfeatures=6000, fastThreshold=7)
        norm = cv2.NORM_HAMMING
        min_matches = 24

    previous_kp, previous_desc = detector.detectAndCompute(previous_gray, None)
    current_kp, current_desc = detector.detectAndCompute(current_gray, None)
    if previous_desc is None or current_desc is None:
        return None

    matcher = cv2.BFMatcher(norm)
    raw_matches = matcher.knnMatch(current_desc, previous_desc, k=2)
    good: list = []
    for pair in raw_matches:
        if len(pair) != 2:
            continue
        best, second = pair
        if best.distance < 0.75 * second.distance:
            good.append(best)

    if len(good) < min_matches:
        return None

    current_pts = np.float32([current_kp[m.queryIdx].pt for m in good])
    previous_pts = np.float32([previous_kp[m.trainIdx].pt for m in good])

    affine, inliers = cv2.estimateAffinePartial2D(
        current_pts,
        previous_pts,
        method=cv2.RANSAC,
        ransacReprojThreshold=4.0,
        maxIters=3000,
        confidence=0.995,
    )
    if affine is None or inliers is None or int(inliers.sum()) < 12:
        return None

    # Use translation only (both axes).  Discarding rotation and scale prevents
    # the panorama from curving (banana shape from yaw) or shrinking (scale
    # compounding to near-zero over 200 frames).
    transform = np.eye(3, dtype=np.float64)
    transform[0, 2] = affine[0, 2]
    transform[1, 2] = affine[1, 2]
    if not _is_reasonable_pair_transform(previous, current, transform):
        return None
    return transform


def _blend_warped_images_wide(cv2, images, transforms, canvas_transform, canvas_size):
    """Composite frames using 'first frame wins' with a horizontal seam blend.

    Each pixel is taken from the first frame that covers it. At each seam a
    BLEND_WIDTH-px horizontal cross-fade (keyed on canvas x-coordinate, not
    on boundary proximity) smooths the transition without creating the diagonal
    fan artefacts that occur when the blend zone is based on distance to the
    new-content boundary.
    """
    import numpy as np

    BLEND_WIDTH = 96
    width, height = canvas_size
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    filled = np.zeros((height, width), dtype=np.uint8)
    x_coords = np.arange(width)  # shape (width,) for broadcasting

    for image, transform in zip(images, transforms):
        full_transform = canvas_transform @ transform
        warped = cv2.warpPerspective(image, full_transform, (width, height))
        frame_mask = cv2.warpPerspective(
            np.ones(image.shape[:2], dtype=np.uint8) * 255,
            full_transform,
            (width, height),
        )
        if not frame_mask.any():
            continue

        new_area = (frame_mask > 0) & (filled == 0)
        overlap = (frame_mask > 0) & (filled > 0)

        # Fill brand-new pixels directly
        canvas[new_area] = warped[new_area]
        filled[new_area] = 255

        if not overlap.any() or not new_area.any():
            continue

        # Blend in overlap pixels within BLEND_WIDTH columns left of the seam.
        # Using canvas x-coordinate (not boundary distance) avoids diagonal artefacts
        # from tiny frame rotations.
        x_seam = int(np.where(new_area)[1].min())
        seam_band = (x_coords >= x_seam - BLEND_WIDTH) & (x_coords < x_seam)
        blend_region = overlap & seam_band[None, :]
        if not blend_region.any():
            continue

        ys, xs = np.where(blend_region)
        alpha = np.clip((xs - (x_seam - BLEND_WIDTH)) / float(BLEND_WIDTH), 0.0, 1.0).astype(np.float32)
        canvas[ys, xs] = (
            canvas[ys, xs].astype(np.float32) * (1.0 - alpha[:, None])
            + warped[ys, xs].astype(np.float32) * alpha[:, None]
        ).astype(np.uint8)

    return canvas


def _try_stitch(cv2, image_paths: list[Path], max_images: int):
    attempts: list[tuple[int, int]] = []
    for count in (20, 24, 16, 12, 8, 5, max_images):
        count = min(count, len(image_paths), max_images)
        if count >= 2 and (count, cv2.Stitcher_PANORAMA) not in attempts:
            attempts.append((count, cv2.Stitcher_PANORAMA))
        if count >= 2 and (count, cv2.Stitcher_SCANS) not in attempts:
            attempts.append((count, cv2.Stitcher_SCANS))

    for count, mode in attempts:
        chosen = _spread_selection(image_paths, count)
        images = [cv2.imread(str(path)) for path in chosen]
        images = [image for image in images if image is not None]
        if len(images) < 2:
            continue
        stitcher = cv2.Stitcher_create(mode)
        status, stitched = stitcher.stitch(images)
        if status == cv2.Stitcher_OK and stitched is not None:
            return stitched
    return None


def _read_for_strip(cv2, path: Path, work_width: int):
    image = cv2.imread(str(path))
    if image is None:
        return None
    height, width = image.shape[:2]
    if width <= work_width:
        return image
    scale = work_width / width
    size = (work_width, max(1, int(height * scale)))
    return cv2.resize(image, size)


def _estimate_pair_transform(cv2, previous, current):
    import numpy as np

    previous_gray = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=5000, fastThreshold=7)
    previous_keypoints, previous_descriptors = orb.detectAndCompute(previous_gray, None)
    current_keypoints, current_descriptors = orb.detectAndCompute(current_gray, None)
    if previous_descriptors is None or current_descriptors is None:
        return None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = matcher.knnMatch(current_descriptors, previous_descriptors, k=2)
    good_matches = []
    for pair in matches:
        if len(pair) != 2:
            continue
        best, second = pair
        if best.distance < 0.72 * second.distance:
            good_matches.append(best)

    if len(good_matches) < 24:
        return None

    current_points = np.float32([current_keypoints[match.queryIdx].pt for match in good_matches])
    previous_points = np.float32([previous_keypoints[match.trainIdx].pt for match in good_matches])
    affine, inliers = cv2.estimateAffinePartial2D(
        current_points,
        previous_points,
        method=cv2.RANSAC,
        ransacReprojThreshold=4.0,
        maxIters=3000,
        confidence=0.995,
    )
    if affine is None or inliers is None or int(inliers.sum()) < 18:
        return None
    transform = np.eye(3, dtype=np.float64)
    transform[:2] = affine
    if not _is_reasonable_pair_transform(previous, current, transform):
        return None
    return transform


def _is_reasonable_pair_transform(previous, current, transform) -> bool:
    import numpy as np

    previous_height, previous_width = previous.shape[:2]
    current_height, current_width = current.shape[:2]
    corners = np.float64([[[0, 0], [current_width, 0], [current_width, current_height], [0, current_height]]])
    warped = _perspective_transform(corners, transform)[0]
    if not np.isfinite(warped).all():
        return False

    min_x, min_y = warped.min(axis=0)
    max_x, max_y = warped.max(axis=0)
    warped_width = max_x - min_x
    warped_height = max_y - min_y
    if warped_width < previous_width * 0.35 or warped_width > previous_width * 2.2:
        return False
    if warped_height < previous_height * 0.35 or warped_height > previous_height * 2.2:
        return False

    overlap_x = max(0.0, min(max_x, previous_width) - max(min_x, 0.0))
    overlap_y = max(0.0, min(max_y, previous_height) - max(min_y, 0.0))
    overlap_ratio = (overlap_x * overlap_y) / max(1.0, previous_width * previous_height)
    return overlap_ratio >= 0.15


def _canvas_transform(images, transforms):
    import numpy as np

    corners = []
    for image, transform in zip(images, transforms):
        height, width = image.shape[:2]
        image_corners = np.float64(
            [[[0, 0], [width, 0], [width, height], [0, height]]]
        )
        corners.append(_perspective_transform(image_corners, transform)[0])

    all_corners = np.vstack(corners)
    min_x, min_y = np.floor(all_corners.min(axis=0)).astype(int)
    max_x, max_y = np.ceil(all_corners.max(axis=0)).astype(int)
    offset = np.array([[1, 0, -min_x], [0, 1, -min_y], [0, 0, 1]], dtype=np.float64)
    width = max(1, int(max_x - min_x))
    height = max(1, int(max_y - min_y))
    return offset, (width, height)


def _perspective_transform(points, transform):
    import numpy as np

    homogeneous = np.concatenate(
        [points, np.ones((*points.shape[:2], 1), dtype=points.dtype)],
        axis=2,
    )
    warped = homogeneous @ transform.T
    warped_xy = warped[:, :, :2] / np.maximum(warped[:, :, 2:], 1e-8)
    return warped_xy


def _blend_warped_images(cv2, images, transforms, canvas_transform, canvas_size):
    import numpy as np

    width, height = canvas_size
    accum = np.zeros((height, width, 3), dtype=np.float32)
    weights = np.zeros((height, width), dtype=np.float32)
    for image, transform in zip(images, transforms):
        full_transform = canvas_transform @ transform
        warped = cv2.warpPerspective(image, full_transform, (width, height))
        mask = cv2.warpPerspective(
            np.ones(image.shape[:2], dtype=np.uint8) * 255,
            full_transform,
            (width, height),
        )
        if not mask.any():
            continue
        feather = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        feather = np.clip(feather / 32.0, 0.0, 1.0).astype(np.float32)
        accum += warped.astype(np.float32) * feather[:, :, None]
        weights += feather

    weights = np.maximum(weights, 1e-6)
    return np.clip(accum / weights[:, :, None], 0, 255).astype(np.uint8)


def _crop_non_empty(cv2, image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
    bbox = cv2.boundingRect(mask)
    x, y, width, height = bbox
    if width <= 0 or height <= 0:
        return image
    return image[y : y + height, x : x + width]


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
