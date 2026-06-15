# Bridge AI Pipeline - One-Command Usage

Date: 2026-06-15

This is the product-style entry point. Instead of running each AI step by hand,
one command takes a drone video and produces a full progress report.

## The one command

```bash
AI/.venv-sam3/Scripts/python.exe AI/scripts/run_bridge_ai_pipeline.py \
  --video AI/data/raw/BridgeVid1-271223.mp4 \
  --final-model AI/data/BridgePointcloud/coverage_result.ply \
  --name bridgevid1_demo
```

That is the whole AI part. Everything lands in one folder:
`AI/outputs/runs/bridgevid1_demo/`.

## What it does (6 stages)

```text
1. Extract frames + mask moving traffic (SAM3)         -> 01_frames/
2. MASt3R-SLAM reconstruction (runs in WSL)            -> 02_slam/pointcloud.ply
3. Clean cloud (remove blackout + smear/noise)         -> 03_clean/pointcloud_clean.ply
4. Compare to final bridge model (per-section %)       -> 04_comparison/
5. Vision check (segment bridge, remove background)    -> 05_vision/
6. Write the report                                    -> REPORT.md
```

Open `REPORT.md` for the summary: overall built %, per-section table, vision
figures, and caveats. `manifest.json` holds the machine-readable version.

## Requirements

```text
- Windows env AI/.venv-sam3 (has SAM3, trimesh, scipy, open3d, opencv)
- WSL Ubuntu-24.04 with the MASt3R-SLAM env at /opt/mast3r-slam-env
  (only needed for stage 2; see AI/docs/ai_handoff_for_claude.md)
- A final bridge model/cloud for stage 4 (.ply or .glb)
```

## Useful flags

```text
--subsample 15        every Nth video frame (lower = denser = slower, fewer holes)
--name <run>          run folder name (default: video stem + timestamp)
--final-model <path>  .ply or .glb; a .glb also enables the model render panel
--vision-frames 6     how many frames to run the vision check on
--anchor-current / --anchor-reference   anchor JSONs to lock bridge orientation
                                        (see pick_control_points.py)

Resume / partial runs (reuse a previous run folder by --name):
--skip-mask    --skip-slam    --skip-clean    --skip-compare    --skip-vision
```

Examples:

```bash
# reuse an existing reconstruction, only redo comparison + vision
... --name bridgevid1_demo --skip-mask --skip-slam --skip-clean

# calibrated orientation using one picked anchor per cloud
... --anchor-current AI/outputs/control_points/scan_anchor.json \
    --anchor-reference AI/outputs/control_points/reference_anchor.json
```

## Notes / honesty

```text
- Stage 2 (SLAM) is the slow part and the only one needing WSL. If WSL or the
  SLAM env is missing, the stage records "failed" in the manifest and the
  pipeline continues; stages 4-5 then run only if a cloud already exists.
- The built % is scale-normalized, not survey-grade. Anchor/GPS/Unity pose
  makes it calibrated.
- This is a research pipeline that demonstrates the full chain on real client
  video. Production quality depends on planned, repeatable, high-overlap
  flights (see the flight-plan recommendation in the handoff doc).
```
