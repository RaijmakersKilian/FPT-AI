"""Top-down contact sheet of every dated reconstruction, to compare SLAM drift.

Loads each AI/outputs/runs/<date>/03_clean/pointcloud_clean.ply, PCA-orients it
so the bridge's long axis is horizontal, renders a top-down footprint, and tiles
them into one labeled grid. Straight footprints = low drift (good hero shot);
banana-curved footprints = high drift.

    AI/.venv-sam3/Scripts/python.exe AI/scripts/render_topdown_grid.py \
        --runs AI/outputs/runs --output AI/outputs/runs/topdown_grid.png
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import cv2
import numpy as np
import trimesh


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=Path("AI/outputs/runs"))
    parser.add_argument("--output", type=Path, default=Path("AI/outputs/runs/topdown_grid.png"))
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--panel", type=int, default=460)
    parser.add_argument("--sample", type=int, default=200_000)
    args = parser.parse_args()

    clouds = sorted(args.runs.glob("*/03_clean/pointcloud_clean.ply"), key=lambda p: _date_key(p.parent.parent.name))
    if not clouds:
        raise SystemExit("no cleaned clouds found")

    panels = []
    for ply in clouds:
        run = ply.parent.parent
        label = run.name
        built = _built_pct(run / "manifest.json")
        panels.append(_render_panel(ply, label, built, args.panel, args.sample))
        print(f"rendered {label}")

    grid = _tile(panels, args.cols, args.panel)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), grid)
    print(f"saved {args.output}")


def _render_panel(ply: Path, label: str, built, panel: int, sample: int) -> np.ndarray:
    cloud = trimesh.load(str(ply), process=False)
    pts = np.asarray(cloud.vertices, dtype=np.float64)
    cols = np.asarray(cloud.visual.vertex_colors)[:, :3]
    finite = np.isfinite(pts).all(axis=1)
    pts, cols = pts[finite], cols[finite]
    if len(pts) > sample:
        idx = np.random.default_rng(0).choice(len(pts), sample, replace=False)
        pts, cols = pts[idx], cols[idx]

    # PCA orient: largest horizontal variance -> x, up -> y in the top-down view.
    pts = pts - np.median(pts, axis=0)
    vals, vecs = np.linalg.eigh(np.cov(pts.T))
    order = np.argsort(vals)[::-1]
    oriented = pts @ vecs[:, order]
    x, y = oriented[:, 0], oriented[:, 1]  # length, width (top-down footprint)

    img = np.full((panel, panel, 3), 18, np.uint8)
    mnx, mxx = np.percentile(x, [1, 99])
    mny, mxy = np.percentile(y, [1, 99])
    span = max(mxx - mnx, mxy - mny, 1e-9)
    px = np.clip(((x - mnx) / span * (panel - 40) + 20).astype(int), 0, panel - 1)
    py = np.clip(((y - mny) / span * (panel - 40) + 20).astype(int), 0, panel - 1)
    for xi, yi, c in zip(px, py, cols[:, ::-1]):
        img[yi, xi] = c

    cv2.rectangle(img, (0, 0), (panel - 1, 28), (35, 35, 35), -1)
    text = f"{label}" + (f"  -  built {built}%" if built is not None else "")
    cv2.putText(img, text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)
    return img


def _tile(panels: list[np.ndarray], cols: int, panel: int) -> np.ndarray:
    rows = (len(panels) + cols - 1) // cols
    grid = np.full((rows * panel, cols * panel, 3), 12, np.uint8)
    for i, p in enumerate(panels):
        r, c = divmod(i, cols)
        grid[r * panel:(r + 1) * panel, c * panel:(c + 1) * panel] = p
    return grid


def _built_pct(manifest: Path):
    try:
        j = json.loads(manifest.read_text(encoding="utf-8"))
        if j.get("compare", {}).get("status") == "ok":
            return j["compare"]["model_built_pct"]
    except Exception:
        pass
    return None


def _date_key(name: str) -> str:
    m = re.search(r"(\d{2})(\d{2})(\d{4})", name)
    if m:
        d, mo, y = m.groups()
        return f"{y}{mo}{d}"
    return "99999999_" + name


if __name__ == "__main__":
    main()
