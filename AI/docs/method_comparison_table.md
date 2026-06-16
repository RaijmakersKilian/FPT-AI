# Method Comparison Table And Upgraded 3D Progress Comparison

Date: 2026-06-11

This document delivers two things:

1. The method comparison table (Task 5 from the handoff document).
2. The upgraded current-vs-final 3D comparison (Task 3 direction), including
   per-section progress results against the completed bridge point cloud.

## Method Comparison Table

| Method | Input | Output | Worked? | Problems | Recommendation |
|---|---|---|---|---|---|
| OpenCV classical segmentation | Drone frames | Noisy masks | Partially | No construction understanding, noisy masks | Keep only as fallback/demo baseline |
| SAM3 progress prompts | Drone frames + text prompts | Named class masks (deck, formwork, crane, ...) | Yes, as demo | Only finds prompted concepts, false positives, no bridge-section knowledge | Use for visual demo evidence, not progress measurement |
| SAM3 object prompts | Drone frames + many object prompts | Many labeled masks | Partially | Output too crowded, misses/mislabels objects | Use to inspect model recognition, not for reporting |
| SAM2 automatic masks | Drone frames | Dense unlabeled masks | Yes, for discovery | Masks unlabeled, needs a classifier on top | Best dense segmentation research path; needs classification step |
| Custom two-view SIFT | 2 drone frames | Sparse point cloud | Yes, as proof | Sparse, arbitrary scale, not aligned | Diagnostic only |
| COLMAP photogrammetry | Selected video frames | Sparse/dense cloud + mesh | Yes, on good segments | Many segments fail, moving traffic hurts, scene mesh not clean bridge | Use on high-overlap planned captures; best geometry when it works |
| Manual 10-frame COLMAP | 10 hand-picked frames | Sparse cloud (10,911 pts) | Yes | Still includes road/trees/water features | Good cheap diagnostic before heavy runs |
| MASt3R-SLAM / vSLAM | Drone video | Dense point cloud (3.08M pts) | Yes, strongest 3D output | Noisy, includes surroundings, arbitrary scale | Best current-cloud source from unplanned video |
| DUSt3R / MASt3R pairs | Frame pairs | Neural point clouds | Yes, as experiment | Superseded by MASt3R-SLAM | Treat MASt3R-SLAM as the stronger result |
| Nerfstudio / Splatfacto Gaussian Splatting | COLMAP poses + frames | Gaussian splat PLY (7,927 gaussians) | Pipeline only | Only 8 registered poses, bad visual quality, MeshLab cannot render splats | Proof of pipeline; needs planned capture to be useful |
| Current-vs-final 3D comparison (v1) | Current cloud + final GLB | Distance metrics + colored cloud | Yes, in principle | PCA-only alignment, only current-to-model direction, one global number | Superseded by v2 below |
| Current-vs-final 3D comparison (v2, this doc) | Current cloud + final model/cloud | ICP-refined alignment, two-direction distances, per-section progress | Yes | Still normalized scale, unsupervised alignment can settle wrong | Main research direction; add control points for production |
| Control-point / anchor alignment | Current cloud + 1 picked anchor per cloud | Mirror-resolved, stable per-section comparison | Yes | Needs one human click per scan | Use to stabilize the 3D comparison; trivial with GPS/Unity pose |
| Vision-only comparison (SAM3 + model render) | One drone frame + GLB model | Bridge isolated, background removed, side-by-side vs model | Yes on good frames | Viewpoint-dependent, mask holes, no pose yet so not pixel-overlap scored | Teacher-recommended 2D track; becomes automatic 1:1 with Unity drone pose |

## What Changed In The Comparison (v2)

The previous comparison in `AI/src/ftp_ai/model_comparison.py` had three gaps:

1. Alignment stopped at PCA normalization plus axis sign flips.
2. It only measured current-to-model distance, which mostly measures scan
   noise, not progress.
3. It reported one global number instead of per-section progress.

The upgraded pipeline:

```text
1. PCA-normalize both clouds, pick best axis sign flips (coarse alignment).
2. Trimmed scale-aware ICP refinement: only the closest 70% of point
   correspondences drive each update, so trees/traffic/background points
   do not dominate the fit.
3. Current-to-model distances: how noisy is the scan, what is likely
   non-bridge (traffic, trees, buildings).
4. Model-to-current distances: which planned geometry already has as-built
   evidence. This is the actual progress signal.
5. Slice the final model along its longest axis into N sections (default 10)
   and report built percentage per section.
```

New outputs per run:

```text
comparison_summary.json        (now includes progress_estimate + per_section)
difference_pointcloud.ply      (current cloud colored by distance to model)
model_coverage_pointcloud.ply  (final model colored green=built, red=missing)
comparison_preview.jpg         (two panels: distance view + progress view)
```

How to run:

```text
python -m ftp_ai.cli compare-3d-model \
  --current <current_pointcloud.ply> \
  --final-model <final_model.glb or completed_bridge.ply> \
  --output <output_dir> \
  --sections 10 --icp-iterations 40 --built-threshold 0.04
```

Use the `AI/.venv-sam3` environment (it has trimesh + scipy installed).

## Reference Data

Two completed-bridge references were tested:

```text
Frontend/KCPT_Ki_centered.glb                  (final design model, mesh)
AI/data/BridgePointcloud/coverage_result.ply   (completed bridge point cloud,
                                                500,000 points, Open3D export)
```

The completed bridge point cloud is the better reference: it is dense, bridge
shaped, and gives much more interpretable per-section results.

## Results (2026-06-11)

All distances are in normalized scene units, not meters.

### ICP improves alignment

MASt3R-SLAM cloud vs final GLB, before vs after adding ICP:

```text
                       v1 (PCA only)   v2 (PCA + trimmed ICP)
median distance        0.02386         0.01384
P90 distance           0.08911         0.08129
close coverage         68.6%           76.59%
```

### Per-section progress vs the completed bridge point cloud

MASt3R-SLAM cloud (`mast3r_slam_bridge1_fast/pointcloud.ply`):

```text
overall model built: 82.28%  (strict 62.85%, loose 91.99%)
likely non-bridge current points: 7.51%
S1:60.4  S2:92.5  S3:97.1  S4:95.4  S5:91.1
S6:82.2  S7:100   S8:100   S9:85.0  S10:0.0
output: AI/outputs/comparison_mast3r_bridge1_vs_bridgepointcloud/
```

COLMAP dense cloud (`colmap_mesh_bridgevid2_s22_full/dense_point_cloud.ply`):

```text
overall model built: 56.2%  (strict 49.78%, loose 60.33%)
likely non-bridge current points: 14.43%
S1:0.0   S2:0.0   S3:72.1  S4:100   S5:99.9
S6:99.2  S7:100   S8:77.2  S9:0.0   S10:0.0
output: AI/outputs/comparison_colmap_bridgevid2_vs_bridgepointcloud/
```

GLB-reference runs also exist for completeness:

```text
AI/outputs/comparison_mast3r_bridge1_vs_final_v2/
AI/outputs/comparison_colmap_bridgevid2_vs_final_v2/
```

## Interpretation

The COLMAP result is the clearest demonstration that per-section reporting
works:

```text
The COLMAP reconstruction only covers the middle video segment. The
comparison correctly reports the covered sections (S3-S8) as 72-100% built
and the uncovered bridge ends (S1, S2, S9, S10) as 0%.
```

This means the pipeline can already distinguish "scanned and present" from
"not scanned / not present" per bridge section, which is the core mechanism a
production progress tracker needs.

The MASt3R result covers more of the bridge (it comes from a longer flyover)
and reads 82% overall with one missing end section.

Important caveats:

```text
1. "Built %" here really means "the scan found geometry near the planned
   geometry". With an already-completed reference cloud and full-coverage
   video, high numbers mean coverage, not construction progress over time.
   Real progress tracking needs scans at different construction stages.
2. The ICP scale factor drifted to 0.54-0.72 on the bridge-point-cloud runs
   because the current clouds contain large surroundings while the reference
   is bridge-only. Control points or GPS would pin the scale in production.
3. Alignment is unsupervised. It looked correct in the previews, but it can
   settle on a wrong fit on other data. Always check comparison_preview.jpg.
4. Section boundaries are equal slices along the bridge axis, not real
   construction phases. With a sectioned BIM model, the same code can report
   per real component.
```

## Client/Teacher Summary

```text
We upgraded the 3D comparison from a single global distance number to an
ICP-refined, two-direction comparison that reports built percentage per
bridge section. Tested against the completed bridge point cloud, the system
correctly identifies which bridge sections are covered by each
reconstruction (e.g. COLMAP covers the middle segment only: sections 3-8
read 72-100%, the ends read 0%). This demonstrates the full feasibility
chain: drone video -> current point cloud -> alignment with a completed
reference -> per-section progress report. The remaining gap to production is
calibrated alignment (control points/GPS) and scans from multiple
construction stages.
```
