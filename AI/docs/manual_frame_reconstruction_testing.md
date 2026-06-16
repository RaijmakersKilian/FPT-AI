# Manual 10-Frame Reconstruction Testing

Date: 2026-06-10

Branch: `ai-vslam-gaussian-splat-test`

## Goal

Test the teacher suggestion:

```text
Maybe take 10 non-consecutive frames, inspect them, make a point cloud, and try
manual/exhaustive matching.
```

This experiment checks whether deliberately selected frames work better than
fully automatic video extraction.

## Input

Video:

```text
AI/data/raw/Bridgevid2-271223.mp4
```

Selected segment:

```text
start: 22 seconds
frame interval: 0.75 seconds
frames: 10
matcher: exhaustive
dense reconstruction: skipped
```

Output:

```text
AI/outputs/manual10_colmap_bridgevid2_s22/
```

Selected frames:

```text
frame_00001320.jpg
frame_00001365.jpg
frame_00001410.jpg
frame_00001455.jpg
frame_00001500.jpg
frame_00001545.jpg
frame_00001590.jpg
frame_00001635.jpg
frame_00001680.jpg
frame_00001725.jpg
```

Visual contact sheet:

```text
AI/outputs/manual10_colmap_bridgevid2_s22/selected_frames_contact_sheet.jpg
```

## COLMAP Result

Command shape:

```powershell
$env:PYTHONPATH='AI/src'
AI\.venv-sam3\Scripts\python.exe -m ftp_ai.cli build-colmap-mesh `
  --video AI\data\raw\Bridgevid2-271223.mp4 `
  --output AI\outputs\manual10_colmap_bridgevid2_s22 `
  --colmap-path AI\.external\colmap\nocuda\bin\colmap.exe `
  --start-seconds 22 `
  --frame-interval 0.75 `
  --max-frames 10 `
  --blur-threshold 20 `
  --max-image-size 1600 `
  --matcher exhaustive `
  --skip-dense
```

Metrics:

```text
status: sparse_success
input frames: 10
registered images: 10
sparse points: 10911
```

Important outputs:

```text
AI/outputs/manual10_colmap_bridgevid2_s22/sparse_point_cloud.ply
AI/outputs/manual10_colmap_bridgevid2_s22/summary.json
AI/outputs/manual10_colmap_bridgevid2_s22/sparse/0/
```

## Two-View Manual Match Check

To get a visible match preview, a two-view SIFT reconstruction was also run on
the first and last selected frames:

```text
frame_a: 1320
frame_b: 1725
```

Output:

```text
AI/outputs/manual10_twoview_bridgevid2_1320_1725/
```

Metrics:

```text
matcher: SIFT
raw matches: 340
essential inliers: 248
pose inliers: 245
points written: 216
mean reprojection error: 42.755 px
median reprojection error: 39.901 px
```

The two-view point cloud is weak because the first and last frames have a large
viewpoint change. The match preview is still useful to explain what the model is
matching.

Match preview:

```text
AI/outputs/manual10_twoview_bridgevid2_1320_1725/matches_preview.jpg
```

## Interpretation

This experiment is useful because the 10 manually chosen/spaced frames performed
better than some previous automatic frame selections:

- all 10 frames were registered by COLMAP
- COLMAP produced 10911 sparse points
- exhaustive matching helped because the frame set is small

However, the result is still not a clean bridge model:

- many features are from roads, buildings, trees, water, and traffic
- the reconstruction is still sparse
- scale is arbitrary without calibration/GPS/control points
- the selected frames are good for research, but not enough for production
  progress tracking

## Conclusion

Manual frame selection helps. This supports the research conclusion that data
selection and capture planning matter more than simply changing the AI model.

For future data collection, the team should not rely on random drone video.
Instead, the drone should capture planned overlapping images along a fixed path.

Recommended next step:

```text
Use manually selected frame sets as a quick diagnostic before running heavier
COLMAP, MASt3R-SLAM, or Gaussian Splatting jobs.
```

For a real implementation, manually selected frames should be replaced by:

- a fixed drone flight path
- controlled overlap
- bridge-only viewpoints
- camera calibration or control points
- repeated captures from the same locations
