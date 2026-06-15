# AI Output Contract (for the Frontend / Supabase Team)

Date: 2026-06-15

This document tells the frontend team (Andreas/Giada) exactly what the AI
pipeline produces per video, so the outputs can be uploaded to Supabase storage
and displayed in the dashboard. The AI side does not touch Supabase or the
frontend; it produces files in a predictable structure.

## How a video is processed

```text
AI/.venv-sam3/Scripts/python.exe AI/scripts/run_bridge_ai_pipeline.py \
  --video <one video> --final-model AI/data/BridgePointcloud/coverage_result.ply \
  --name <run name, e.g. the date>

# or batch the whole Google Drive folder at once:
AI/.venv-sam3/Scripts/python.exe AI/scripts/run_all_videos.py \
  --video-dir <folder of videos> --final-model AI/data/BridgePointcloud/coverage_result.ply
```

Output goes to `AI/outputs/runs/<name>/`. Batch runs also write
`AI/outputs/runs/INDEX.md` listing every run.

## Per-run folder structure

```text
AI/outputs/runs/<name>/
  REPORT.md                         human summary (built %, per-section, links)
  manifest.json                     MACHINE-READABLE summary  <-- frontend reads this
  02_slam/pointcloud.ply            raw MASt3R-SLAM reconstruction (+ trajectory.txt)
  03_clean/pointcloud_clean.ply     cleaned current reconstruction  <-- 3D viewer
  04_comparison/
    comparison_summary.json         per-section built %, distances, alignment
    model_coverage_pointcloud.ply   final model colored GREEN=built / RED=missing  <-- progress 3D
    difference_pointcloud.ply       current cloud colored by distance to model
    comparison_preview.jpg          2-panel progress preview image
  05_vision/
    construction_overlay.mp4        whole-video construction detection  <-- video panel
    model_render.jpg                render of the finished model (no background)
    frame_XXXXX/comparison_figure.jpg   per-frame 4-panel vision figure
```

## What to upload to Supabase (the 5 artifacts that matter)

Suggested bucket layout: `bridge/<date_or_name>/...`

```text
1. 03_clean/pointcloud_clean.ply        -> the current as-built 3D point cloud
2. 04_comparison/model_coverage_pointcloud.ply -> bridge colored by built/missing
3. 04_comparison/comparison_summary.json -> the numbers for the dashboard
4. 05_vision/construction_overlay.mp4    -> the construction-detection video
5. manifest.json                         -> headline summary per run
```

The finished design model `Frontend/KCPT_Ki_centered.glb` is already in the
frontend repo and is the same for every date.

## Formats and how to display each

```text
*.ply  ASCII point clouds with per-point RGB.
       Display with three.js PLYLoader + THREE.Points (you already load the
       GLB with a GLTFLoader; PLY is the same pattern).
       NOTE: pointcloud_clean.ply is ~3M points. For smooth browser display,
       decimate to ~300-500k on upload (or ask the AI side to add a
       --web-export decimated copy - quick to add if you want it).

*.mp4  Standard H.264-friendly mp4 (cv2 mp4v). Plain <video> element.

*.json manifest.json / comparison_summary.json - read directly for dashboard
       numbers (see schema below).
```

## manifest.json schema (the fields the dashboard needs)

```json
{
  "name": "<run name>",
  "video": "<source video path>",
  "slam":    { "status": "ok", "points": 3600000 },
  "clean":   { "status": "ok", "points_out": 3200000, "removed_pct": 14.7 },
  "compare": {
    "status": "ok",
    "model_built_pct": 82.4,
    "model_built_pct_strict": 68.8,
    "likely_non_bridge_pct": 2.4,
    "per_section": [ { "section": 1, "built_pct": 0.0 }, ... ]
  },
  "vision":  {
    "status": "ok",
    "frames_checked": 6,
    "overlay_video": "<path to construction_overlay.mp4>",
    "best": [ { "frame": "frame_00120.png", "bridge_pct": 12.95, "dir": "..." } ]
  }
}
```

For a "progress over time" view, read `compare.model_built_pct` and
`compare.per_section` from each date's manifest and plot them in date order.

## Important honesty notes (so the frontend doesn't over-promise)

```text
- All videos we currently have are one date (27/12/2023). "Progress over time"
  needs more dated videos from the client; the pipeline already supports it
  (one run per date), the data is the only blocker.
- Built % is a scale-normalized estimate, not survey-grade. It is calibrated
  once a control-point anchor or GPS/Unity drone pose is provided.
- The construction-detection video flags the active construction zone; it is
  SAM3 open-vocabulary, so it is a strong demo but not a certified detector.
```
