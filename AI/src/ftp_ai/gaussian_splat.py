from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import numpy as np


SH_C0 = 0.28209479177387814


def pointcloud_to_gaussian_splat(
    input_ply: Path,
    output_dir: Path,
    max_points: int = 250_000,
    splat_scale: float = 0.01,
    opacity: float = 0.65,
    seed: int = 19,
) -> dict[str, object]:
    """Convert a colored point cloud into a 3D Gaussian Splat seed PLY.

    This is not optimized 3D Gaussian Splatting training. It writes a common
    3DGS-style PLY containing one isotropic gaussian per sampled point, useful
    for quickly testing whether splatting could be a good representation.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    points, colors = _read_xyz_rgb_ply(input_ply)
    points, colors = _sample(points, colors, max_points=max_points, seed=seed)

    center = np.median(points, axis=0)
    centered = points - center
    radius = float(np.percentile(np.linalg.norm(centered, axis=1), 95))
    radius = max(radius, 1e-9)
    normalized = centered / radius

    splat_path = output_dir / "gaussian_splat_seed.ply"
    preview_path = output_dir / "gaussian_splat_preview.jpg"
    summary_path = output_dir / "gaussian_splat_summary.json"

    _write_3dgs_ply(splat_path, normalized, colors, splat_scale=splat_scale, opacity=opacity)
    _write_preview(preview_path, normalized, colors)

    source_count = _read_ply_vertex_count(input_ply)
    summary: dict[str, object] = {
        "status": "experimental_seed",
        "method": "point cloud to isotropic 3D Gaussian Splat seed",
        "input_ply": str(input_ply),
        "source_points": int(source_count if source_count is not None else len(points)),
        "splat_points": int(len(normalized)),
        "normalization": {
            "center": [round(float(value), 6) for value in center],
            "scale_p95_radius": round(radius, 6),
        },
        "splat_scale_log": round(float(math.log(max(splat_scale, 1e-8))), 6),
        "opacity_logit": round(float(_logit(opacity)), 6),
        "outputs": {
            "gaussian_splat_seed": str(splat_path),
            "preview": str(preview_path),
            "summary": str(summary_path),
        },
        "limitations": [
            "This is a Gaussian Splat seed, not a trained/optimized 3DGS scene.",
            "It uses one isotropic gaussian per point and identity rotations.",
            "Visual quality depends on the source point cloud quality.",
            "A real 3DGS test should train from COLMAP camera poses and source images.",
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _read_xyz_rgb_ply(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open("rb") as handle:
        header_lines: list[str] = []
        while True:
            line = handle.readline()
            if not line:
                raise ValueError(f"Invalid PLY without end_header: {path}")
            decoded = line.decode("ascii", errors="replace").strip()
            header_lines.append(decoded)
            if decoded == "end_header":
                break
        data_start = handle.tell()

    fmt = _header_value(header_lines, "format")
    vertex_count = int(_header_value(header_lines, "element vertex"))
    properties = _vertex_properties(header_lines)
    if fmt == "ascii":
        return _read_ascii_vertices(path, data_start, vertex_count, properties)
    if fmt == "binary_little_endian":
        return _read_binary_vertices(path, data_start, vertex_count, properties, endian="<")
    raise ValueError(f"Unsupported PLY format for {path}: {fmt}")


def _header_value(header_lines: list[str], prefix: str) -> str:
    for line in header_lines:
        if line.startswith(prefix + " "):
            return line[len(prefix) + 1 :].split()[0]
    raise ValueError(f"PLY header missing {prefix}")


def _vertex_properties(header_lines: list[str]) -> list[tuple[str, str]]:
    properties: list[tuple[str, str]] = []
    in_vertex = False
    for line in header_lines:
        if line.startswith("element vertex "):
            in_vertex = True
            continue
        if in_vertex and line.startswith("element "):
            break
        if in_vertex and line.startswith("property "):
            _, dtype, name = line.split()[:3]
            properties.append((dtype, name))
    return properties


def _read_ascii_vertices(
    path: Path,
    data_start: int,
    vertex_count: int,
    properties: list[tuple[str, str]],
) -> tuple[np.ndarray, np.ndarray]:
    name_to_index = {name: index for index, (_, name) in enumerate(properties)}
    required = ["x", "y", "z"]
    if not all(name in name_to_index for name in required):
        raise ValueError(f"PLY missing x/y/z properties: {path}")

    points = np.zeros((vertex_count, 3), dtype=np.float32)
    colors = np.full((vertex_count, 3), 180, dtype=np.uint8)
    with path.open("rb") as handle:
        handle.seek(data_start)
        for index in range(vertex_count):
            values = handle.readline().decode("ascii", errors="replace").split()
            points[index] = [
                float(values[name_to_index["x"]]),
                float(values[name_to_index["y"]]),
                float(values[name_to_index["z"]]),
            ]
            if all(name in name_to_index for name in ("red", "green", "blue")):
                colors[index] = [
                    int(float(values[name_to_index["red"]])),
                    int(float(values[name_to_index["green"]])),
                    int(float(values[name_to_index["blue"]])),
                ]
    return points, colors


def _read_binary_vertices(
    path: Path,
    data_start: int,
    vertex_count: int,
    properties: list[tuple[str, str]],
    endian: str,
) -> tuple[np.ndarray, np.ndarray]:
    type_map = {
        "char": "b",
        "int8": "b",
        "uchar": "B",
        "uint8": "B",
        "short": "h",
        "int16": "h",
        "ushort": "H",
        "uint16": "H",
        "int": "i",
        "int32": "i",
        "uint": "I",
        "uint32": "I",
        "float": "f",
        "float32": "f",
        "double": "d",
        "float64": "d",
    }
    fmt = endian + "".join(type_map[dtype] for dtype, _ in properties)
    record = struct.Struct(fmt)
    name_to_index = {name: index for index, (_, name) in enumerate(properties)}
    required = ["x", "y", "z"]
    if not all(name in name_to_index for name in required):
        raise ValueError(f"PLY missing x/y/z properties: {path}")

    points = np.zeros((vertex_count, 3), dtype=np.float32)
    colors = np.full((vertex_count, 3), 180, dtype=np.uint8)
    with path.open("rb") as handle:
        handle.seek(data_start)
        for index in range(vertex_count):
            values = record.unpack(handle.read(record.size))
            points[index] = [
                float(values[name_to_index["x"]]),
                float(values[name_to_index["y"]]),
                float(values[name_to_index["z"]]),
            ]
            if all(name in name_to_index for name in ("red", "green", "blue")):
                colors[index] = [
                    int(values[name_to_index["red"]]),
                    int(values[name_to_index["green"]]),
                    int(values[name_to_index["blue"]]),
                ]
    return points, colors


def _sample(points: np.ndarray, colors: np.ndarray, max_points: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    finite = np.isfinite(points).all(axis=1)
    points = points[finite]
    colors = colors[finite]
    if len(points) <= max_points:
        return points, colors
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(points), size=max_points, replace=False)
    return points[indices], colors[indices]


def _write_3dgs_ply(
    path: Path,
    points: np.ndarray,
    colors: np.ndarray,
    splat_scale: float,
    opacity: float,
) -> None:
    rgb = colors.astype(np.float32) / 255.0
    f_dc = (rgb - 0.5) / SH_C0
    opacity_value = _logit(opacity)
    scale_value = math.log(max(splat_scale, 1e-8))

    properties = [
        "x",
        "y",
        "z",
        "nx",
        "ny",
        "nz",
        "f_dc_0",
        "f_dc_1",
        "f_dc_2",
        "opacity",
        "scale_0",
        "scale_1",
        "scale_2",
        "rot_0",
        "rot_1",
        "rot_2",
        "rot_3",
    ]
    with path.open("wb") as handle:
        header = ["ply", "format binary_little_endian 1.0", f"element vertex {len(points)}"]
        header.extend(f"property float {name}" for name in properties)
        header.append("end_header\n")
        handle.write(("\n".join(header)).encode("ascii"))
        record = struct.Struct("<17f")
        for point, color_dc in zip(points, f_dc):
            handle.write(
                record.pack(
                    float(point[0]),
                    float(point[1]),
                    float(point[2]),
                    0.0,
                    0.0,
                    0.0,
                    float(color_dc[0]),
                    float(color_dc[1]),
                    float(color_dc[2]),
                    float(opacity_value),
                    float(scale_value),
                    float(scale_value),
                    float(scale_value),
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                )
            )


def _write_preview(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    try:
        import cv2  # type: ignore
    except ImportError:
        return

    canvas = np.zeros((1000, 1400, 3), dtype=np.uint8)
    xy = points[:, :2]
    mn = np.percentile(xy, 1, axis=0)
    mx = np.percentile(xy, 99, axis=0)
    span = np.maximum(mx - mn, 1e-9)
    norm = (xy - mn) / span
    px = np.clip((norm[:, 0] * 1320 + 40).astype(int), 0, 1399)
    py = np.clip(((1.0 - norm[:, 1]) * 920 + 60).astype(int), 0, 999)

    colors_bgr = colors[:, ::-1]
    stride = max(1, len(points) // 250_000)
    for x, y, color in zip(px[::stride], py[::stride], colors_bgr[::stride]):
        canvas[int(y), int(x)] = color

    cv2.putText(
        canvas,
        "Gaussian Splat seed preview (top-down point projection)",
        (30, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (235, 235, 235),
        2,
        cv2.LINE_AA,
    )
    cv2.imwrite(str(path), canvas)


def _logit(value: float) -> float:
    clipped = min(1.0 - 1e-6, max(1e-6, value))
    return math.log(clipped / (1.0 - clipped))


def _read_ply_vertex_count(path: Path) -> int | None:
    try:
        with path.open("rb") as handle:
            for raw_line in handle:
                line = raw_line.decode("ascii", errors="ignore").strip()
                if line.startswith("element vertex "):
                    return int(line.split()[-1])
                if line == "end_header":
                    return None
    except OSError:
        return None
    return None
