"""Render clean top-down PNGs of the method point clouds for the presentation.

Each cloud is projected onto its two widest axes (PCA) and scatter-plotted with
its real RGB colours on a dark background, no axes -- consistent slide visuals.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("AI/outputs/slide_renders")
OUT.mkdir(parents=True, exist_ok=True)

# (label, ply path, point size, target sample)
JOBS = [
    ("MASt3R-SLAM (full flight)", "AI/outputs/mast3r_slam_bridge1_fast/pointcloud.ply", 0.30, 350000),
    ("MASt3R / DUSt3R (plain, few-view)", "AI/outputs/dust3r_bridge1/pointcloud.ply", 0.8, 350000),
    ("COLMAP (dense)", "AI/outputs/colmap_mesh_bridgevid2_s22_full/dense_point_cloud.ply", 0.5, 350000),
    ("Gaussian Splatting (seed)", "AI/outputs/gaussian_splat_bridge1_seed/gaussian_splat_seed.ply", 1.0, 250000),
]


def render(label, path, psize, sample):
    p = Path(path)
    if not p.exists():
        print(f"skip (missing): {path}")
        return
    pcd = o3d.io.read_point_cloud(str(p))
    pts = np.asarray(pcd.points)
    if len(pts) == 0:
        print(f"skip (empty): {path}")
        return
    cols = np.asarray(pcd.colors)
    if cols.size == 0:
        cols = np.tile(np.array([[0.55, 0.7, 1.0]]), (len(pts), 1))

    rng = np.random.default_rng(0)
    if len(pts) > sample:
        idx = rng.choice(len(pts), sample, replace=False)
        pts = pts[idx]

    # project onto the 2 widest axes (top-down of an elongated structure)
    c = pts - pts.mean(0)
    _, _, vt = np.linalg.svd(c[rng.choice(len(c), min(len(c), 120000), replace=False)], full_matrices=False)
    proj = c @ vt[:2].T

    # colour by position along the bridge (widest axis) -> always high-contrast
    val = proj[:, 0]
    lo, hi = np.percentile(val, [2, 98])
    val = np.clip((val - lo) / (hi - lo + 1e-9), 0, 1)

    w, h = 1600, 1000
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    bg = "#0c1124"
    ax.set_facecolor(bg)
    fig.patch.set_facecolor(bg)
    ax.scatter(proj[:, 0], proj[:, 1], s=psize * 2.2, c=val, cmap="turbo", linewidths=0, marker=".")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.text(0.02, 0.96, f"{label}   ({len(pts):,} pts shown)", transform=ax.transAxes,
            color="#ffffff", fontsize=15, fontweight="bold", va="top",
            family="DejaVu Sans")
    out = OUT / (label.split("(")[0].strip().replace(" ", "_").replace("/", "-") + ".png")
    fig.savefig(out, dpi=100)
    plt.close(fig)
    print(f"wrote {out}  ({len(pts):,} pts)")


for job in JOBS:
    render(*job)
print(f"\ndone -> {OUT}")
