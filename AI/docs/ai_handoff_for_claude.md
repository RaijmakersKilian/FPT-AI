# AI Handoff For Claude Code

Date: 2026-06-11

Current branch: `ai-vslam-gaussian-splat-test`

Purpose of this document: give another coding assistant enough context to
continue the AI research work without needing the full chat history.

## CURRENT STATUS (updated 2026-06-15) - READ THIS FIRST

Final week. Presentation is Friday 2026-06-19. Two AI tracks are built and
there is now a single one-command pipeline tying them together.

```text
TRACK A - 3D point cloud (DONE, proven):
  video -> SAM3 traffic masking -> MASt3R-SLAM -> black-point filter ->
  geometric clean -> compare to final model (per-section progress) ->
  optional anchor/control-point alignment to stabilize orientation.

TRACK B - vision-only (teacher's 2026-06-15 recommendation, DONE as demo):
  FOCUS = the active CONSTRUCTION between the finished roads (yellow
  falsework/gantry, new pier, cranes), NOT the whole bridge. SAM3 isolates
  the construction zone per frame and removes the rest; run across the whole
  flyover into construction_overlay.mp4, shown next to the finished 3D model.
  A pixel-level 1:1 overlay onto the model needs the drone pose (Unity); until
  then the quantitative progress number comes from Track A. Prompt choice
  matters: broad terms over-fire onto the whole deck, use "yellow steel
  gantry"/"scaffolding"/"bridge pylon tower"/"construction crane".

PRODUCT - one command runs the whole AI part:
  AI/scripts/run_bridge_ai_pipeline.py  (see AI/docs/pipeline_usage.md)
  video in -> AI/outputs/runs/<name>/REPORT.md out.
```

Key newest docs (read in this order):

```text
AI/docs/meetingwithteacher.md          - teacher meeting transcript (the brief)
AI/docs/vision_comparison_testing.md   - Track B method + presentation talking points
AI/docs/pipeline_usage.md              - the one-command product usage
AI/docs/dynamic_masking_experiment.md  - Track A masking/cleaning/denser-frames chain
AI/docs/method_comparison_table.md     - full method table + 3D comparison results
AI/docs/bridge_isolation_testing.md    - PARKED (3D bridge crop; not clean enough)
```

Newest scripts (all run with the Windows env AI/.venv-sam3):

```text
AI/scripts/run_bridge_ai_pipeline.py   - the product orchestrator (one command)
AI/scripts/run_all_videos.py           - batch the pipeline over a video folder
AI/scripts/mask_dynamic_objects.py     - SAM3 traffic masking on extracted frames
AI/scripts/remove_black_points.py      - drop blacked-out hallucinated points
AI/scripts/clean_pointcloud.py         - SOR + density smear/noise removal
AI/scripts/pick_control_points.py      - Open3D landmark/anchor picker (PLY-friendly)
AI/scripts/check_mirror_fit.py         - shows the two lengthwise mirror fits
AI/scripts/segment_bridge_frame.py     - Track B: isolate the construction zone (--focus)
AI/scripts/construction_overlay_video.py - Track B: whole-video construction overlay MP4
AI/scripts/render_bridge_model.py      - software (no-GL) render of the GLB model
AI/scripts/build_vision_comparison.py  - Track B 4-panel presentation figure
```

Environments: Windows AI/.venv-sam3 has SAM3 + trimesh + scipy + open3d +
opencv (use this for everything except SLAM). MASt3R-SLAM runs in WSL
Ubuntu-24.04 at /opt/mast3r-slam-env. Trello creds are in the user env
(TRELLO_API_KEY / TRELLO_TOKEN); board FPT-AI id 6a0ad1b50725565ed877de90.

Best current artifacts:

```text
AI/outputs/mast3r_slam_bridge1_masked_s15/pointcloud_clean.ply   (best cloud, 3.2M pts)
AI/outputs/vision_compare/frame_00120/comparison_figure.jpg      (Track B figure)
AI/outputs/vision_compare/frame_00090/comparison_figure.jpg      (Track B figure)
```

Direction confirmed 2026-06-15 (user): the teacher's asks are done (Track A +
Track B). The remaining AI job is to run MASt3R-SLAM + the full pipeline on ALL
the client's videos (more arriving from Google Drive, ordered by date). The
FRONTEND + SUPABASE is Andreas/Giada's responsibility - the AI side only
produces files in a predictable structure (see AI/docs/ai_output_contract.md).

What is left / good next tasks for Codex:

```text
1. When the user adds the Google Drive videos, batch them:
   AI/scripts/run_all_videos.py --video-dir <folder> --final-model <model>
   -> one AI/outputs/runs/<name>/ per video + INDEX.md.
2. We currently only have one date (27/12/2023, 3 videos). "Progress over time"
   needs the new dated videos; the pipeline already supports one run per date.
3. Hand outputs to the frontend team per AI/docs/ai_output_contract.md (the 5
   key artifacts: clean cloud, coverage cloud, comparison json, overlay mp4,
   manifest). Optional quick win: add a --web-export decimated PLY (~300k pts)
   for smooth browser display if the frontend asks.
4. The future drone flight-plan doc (Task 4 below) - high-value, pure writing.
5. Optional: a project-specific trained detector would make Track B reliable
   (open-vocabulary SAM3 is a demo, not certified; see vision doc).
```

DO NOT reopen the 3D bridge-isolation crop (AI/docs/bridge_isolation_testing.md);
it was parked on purpose - unsupervised alignment is not precise enough, and it
becomes trivial only with calibrated (GPS/Unity) alignment.

## Project Explained Clearly

This project is about construction progress tracking for a bridge.

The client has drone footage of a bridge construction site and a final bridge
design/model. The goal is to research whether AI can help compare the current
real-world construction state against the planned/final bridge state.

Plain-language version:

```text
We want to know how much of the bridge that should exist in the final model
already exists in the real world.
```

The ideal final system would work like this:

```text
1. The client flies a drone over the bridge construction site.
2. The system converts the drone/LiDAR/photogrammetry data into a current 3D
   point cloud.
3. The final BIM/IFC/3D bridge model is also converted into a reference point
   cloud.
4. The two point clouds are aligned.
5. The system checks which bridge sections overlap, which sections are missing,
   and which points are noise or temporary construction objects.
6. The result becomes a progress report per bridge section/component.
```

Important distinction:

```text
The project is not just "detect objects in drone images".
The real problem is comparing current as-built geometry with planned final
geometry.
```

Why 2D segmentation is not enough:

- it can show visible masks in images
- it does not know exact 3D bridge section positions
- it cannot reliably measure geometric completion by itself
- it struggles to distinguish permanent bridge structure from temporary
  equipment/formwork/traffic

Why 3D point clouds are the stronger direction:

- a point cloud can represent the current physical bridge shape
- the final model can also be sampled into a point cloud
- overlap/distance comparison can be measured numerically
- progress can be reported per section if the final model is split or annotated

The current practical goal is not to deliver a production system, but to produce
a clear feasibility study:

```text
Which AI/3D approaches work on the available data, what are their limitations,
and what would a real implementation team need to collect better data and build
the system properly?
```

## Project Direction

The project has shifted from "build a final working AI product now" toward a
research/feasibility project.

The useful deliverable is to test many possible AI and 3D approaches on the
client drone data and explain:

- what works
- what does not work
- why some approaches fail
- what data a real implementation team would need
- what workflow would be recommended for a production version

The core research question is:

```text
Can drone footage of a bridge construction site be used to estimate visible
construction progress by comparing the current state with a final 3D bridge
model or digital twin?
```

The main insight so far:

```text
The hardest part is not only choosing an AI model. The hardest part is getting
repeatable, high-quality drone data that can be reconstructed and aligned with
the final model.
```

## Current Main Strategy As Of 2026-06-11

The current best project direction is point-cloud comparison, not pure 2D
segmentation.

Target workflow:

```text
current drone/LiDAR/photogrammetry data -> current point cloud
final BIM/IFC/3D bridge model -> final reference point cloud
align current point cloud to final point cloud
compare overlap / missing geometry / distance differences per bridge section
```

This is the most realistic research direction because bridge progress is a 3D
problem:

- is this bridge part present?
- is this deck section built?
- is this support/column visible?
- how much of the final geometry overlaps with the current reconstruction?
- which final model regions are still missing in the current scan?

Segmentation should now be treated as supporting evidence, not the main progress
measurement method.

Recommended production-style architecture:

1. Generate the best possible current point cloud.
   - best if available: real LiDAR scan
   - second best: planned photogrammetry image capture
   - useful research baseline: MASt3R-SLAM from drone video
   - useful when data has good overlap: COLMAP
2. Convert the final BIM/IFC/GLB/OBJ bridge model into a dense point cloud.
3. Align current and final point clouds.
   - start with manual control points
   - then run ICP/registration
4. Compare geometry.
   - final-to-current distance: which planned parts are missing?
   - current-to-final distance: what is noise, traffic, trees, or temporary work?
5. Report progress by bridge section/component, not as one global percentage.

Important phrasing for client/teacher:

```text
The most accurate path is to compare a current point cloud against a point cloud
sampled from the final BIM model. The quality of the result depends mostly on
the quality and repeatability of the current scan.
```

## LiDAR Clarification

Normal drone footage cannot be converted into a real LiDAR scan.

Reason:

```text
LiDAR measures real distances with laser pulses. Normal RGB video only contains
pixels, so depth must be estimated rather than measured.
```

What is possible from video:

- COLMAP / photogrammetry point cloud
- MASt3R-SLAM point cloud
- DUSt3R / MASt3R neural point cloud
- depth-estimation-based pseudo point cloud

These are LiDAR-like point clouds, but they are not as accurate as real LiDAR.

If the client has LiDAR data, ask for it. Useful formats:

```text
.las
.laz
.e57
.ply
.pcd
```

Best LiDAR workflow:

```text
real LiDAR scan -> current point cloud
final BIM model -> final point cloud
manual/control-point alignment -> ICP refinement -> overlap/progress analysis
```

MASt3R-SLAM does not directly fuse LiDAR in the current local setup. The local
repo supports RGB video/image folders and RealSense/TUM-RGBD-style examples, but
not a direct "feed LiDAR into MASt3R-SLAM" workflow. LiDAR should be used as a
separate stronger geometry source or alignment reference.

How to explain MASt3R-SLAM vs COLMAP:

```text
MASt3R-SLAM worked better on imperfect video because it is neural and more
flexible. It can estimate dense structure from difficult footage. COLMAP is more
strict and depends on reliable feature matching, so it needs better planned
photogrammetry data. More MASt3R points does not automatically mean more
accuracy; it can also include trees, roads, buildings, traffic, and noisy depth.
```

## Client Meeting Questions

Ask the client for:

1. Final bridge model:
   - BIM
   - IFC
   - GLB/GLTF
   - OBJ
   - DWG
   - Revit export
2. Any current or historical LiDAR scans.
3. Drone metadata:
   - GPS
   - IMU
   - camera intrinsics/calibration
   - flight path logs
4. Whether future drone flights can follow a fixed repeatable path.
5. Whether the drone can capture planned high-overlap photos instead of only
   video.
6. Bridge sections/phases they care about:
   - deck sections
   - columns/supports
   - formwork
   - road surface
   - ramps
   - temporary structures
7. Examples of what the client considers:
   - completed
   - in progress
   - not started
8. Whether they can provide a section plan or construction schedule linked to
   the final model.

Good client-facing summary:

```text
Our tests show that AI reconstruction is possible, but the reliable solution is
not just choosing a model. We need a repeatable data capture process and a final
reference model. The strongest direction is point-cloud comparison: create a
current point cloud from drone/LiDAR data, sample the final BIM model into a
reference point cloud, align both, and measure overlap per bridge section.
```

## Current High-Level Recommendation

For a real team, the recommended setup would be:

1. Use a final bridge model, BIM model, IFC model, or digital twin as reference.
2. Define a fixed drone flight path first, ideally in Unity or another planning
   tool.
3. Fly the same route every time:
   - same altitude
   - same camera angle
   - same speed
   - same direction
   - same takeoff/reference points
   - similar lighting/time of day if possible
4. Capture many overlapping images, not just casual video.
5. Reconstruct the current bridge state with photogrammetry, SLAM, or
   MASt3R-style reconstruction.
6. Align current reconstruction to the final model using control points.
7. Use segmentation/object detection only as support for identifying bridge
   parts, equipment, and work zones.
8. Report progress per predefined bridge section, not as one global percentage.

## Important Data Notes

Raw videos are in:

```text
AI/data/raw/
```

Important video used often:

```text
AI/data/raw/BridgeVid1-271223.mp4
```

Another useful video:

```text
AI/data/raw/Bridgevid2-271223.mp4
```

Bridge length mentioned in notes:

```text
494 m
```

The available drone videos are useful for research, but not ideal for production
3D reconstruction:

- many moving cars, buses, and motorbikes
- trees and water around the bridge
- repeated road/deck textures
- changing perspective
- not always bridge-only
- unknown camera calibration/GPS/IMU metadata
- not a fixed repeatable drone path

## Segmentation Work Done

Segmentation was tested as the first AI progress-detection direction.

### Classical OpenCV

Status: works as fallback only.

Pros:

- no model weights required
- runs locally
- proves pipeline shape

Cons:

- no construction understanding
- noisy masks
- not useful for progress estimation

Conclusion: keep only as fallback/demo baseline.

### SAM3 Progress Prompts

Status: best semantic progress demo so far, but not automatic enough.

Tested prompt style:

```text
completed deck
formwork
bridge deck
construction equipment
crane
bridge construction
unfinished construction
```

Pros:

- gives named classes
- useful for visual progress screenshots
- better when cropped to construction ROI

Cons:

- only finds concepts we prompt for
- can create false positives
- does not know exact bridge components/phases

Conclusion: good for demo, not enough for a production progress system.

### SAM3 Object Prompts

Status: more complete, but visually crowded and prompt-limited.

Tested many object prompts such as:

```text
bridge deck
concrete slab
bridge girder
bridge column
formwork
scaffolding
rebar
construction material
crane
excavator
truck
bus
car
motorbike
person
road
tree
building
water
```

Conclusion: useful to inspect what the model recognizes, but the output becomes
too busy and still misses/mislabels things.

### SAM2 Automatic Segment Everything

Status: best candidate for dense "segment everything" research.

Pros:

- no text prompts
- creates many masks
- better for object/region discovery

Cons:

- masks are unlabeled
- it does not know which mask is deck/formwork/rebar
- needs a second classifier or manual labeling step

Conclusion:

```text
SAM2 automatic masks are useful, but final progress tracking needs mask
classification or a trained project-specific segmentation model.
```

## 3D Work Done

The 3D part is the most important research direction now, because progress
tracking probably needs comparison with the final 3D model/digital twin.

### Custom Two-View Prototype

Tested SIFT matching between two drone frames and generated a sparse point
cloud.

What it proved:

- drone frames contain matchable features
- sparse 3D reconstruction is possible

Why it is not enough:

- only sparse points
- not a finished bridge model
- arbitrary scale
- not aligned to final model

### COLMAP Photogrammetry

COLMAP was tested on extracted bridge frames.

Best known output:

```text
AI/outputs/colmap_mesh_bridgevid2_s22_full/
```

Important files:

```text
AI/outputs/colmap_mesh_bridgevid2_s22_full/sparse_point_cloud.ply
AI/outputs/colmap_mesh_bridgevid2_s22_full/dense_point_cloud.ply
AI/outputs/colmap_mesh_bridgevid2_s22_full/mesh.ply
AI/outputs/colmap_mesh_bridgevid2_s22_full/summary.json
```

Best known metrics from the interim notes:

```text
input frames: 32
registered images: 32
sparse 3D points: 25739
dense vertices: 178539
mesh vertices: 12672
mesh faces: 23118
```

Conclusion:

- COLMAP can produce a mesh when the video segment has enough overlap.
- Many segments fail or reconstruct weakly.
- The result is a scene mesh, not a clean BIM bridge object.
- Moving traffic/background noise hurts quality.

### Manual 10-Frame COLMAP Test

Teacher suggestion tested on 2026-06-10:

```text
Take around 10 non-consecutive frames, inspect them, and make a point cloud /
manual matching test.
```

Dedicated note:

```text
AI/docs/manual_frame_reconstruction_testing.md
```

Output:

```text
AI/outputs/manual10_colmap_bridgevid2_s22/
AI/outputs/manual10_twoview_bridgevid2_1320_1725/
```

Result:

```text
10 selected frames
10 registered COLMAP images
10911 sparse points
```

Conclusion:

```text
Manual/spaced frame selection helps. It is a good diagnostic step before
running heavier COLMAP, MASt3R-SLAM, or Gaussian Splatting jobs. The output is
still not a clean bridge model because many features come from road, buildings,
trees, water, and traffic.
```

### MASt3R-SLAM / vSLAM

MASt3R-SLAM is the main vSLAM experiment.

Run script:

```text
AI/scripts/run_mast3r_bridge1_fast.sh
```

Config:

```text
AI/configs/mast3r_bridge_video_fast.yaml
```

Output:

```text
AI/outputs/mast3r_slam_bridge1_fast/pointcloud.ply
AI/outputs/mast3r_slam_bridge1_fast/trajectory.txt
```

Known result:

```text
point cloud vertices: 3,077,001
trajectory entries: 30
```

Conclusion:

- This is currently one of the strongest 3D outputs.
- It is still a noisy point cloud, not a clean final model.
- It includes surroundings, trees, roads, traffic, water, and buildings.
- It is useful research evidence for vSLAM feasibility.

Important clarification:

```text
vSLAM is not one separate model. vSLAM is the task/method category: estimating
camera motion while reconstructing the scene. MASt3R-SLAM is one specific vSLAM
system we tested.
```

Update 2026-06-11: masking moving traffic out of the frames with SAM3 before
running MASt3R-SLAM measurably improves the reconstruction and the progress
comparison (38 vs 30 keyframes, strict built +5.7 points, fewer non-bridge
points). See `AI/docs/dynamic_masking_experiment.md`. This gives segmentation
its production role: pre-reconstruction cleaning, not progress measurement.

```text
AI/scripts/mask_dynamic_objects.py
AI/scripts/run_mast3r_bridge1_masked.sh
AI/outputs/mast3r_slam_bridge1_masked/
AI/outputs/comparison_mast3r_bridge1_masked_vs_bridgepointcloud/
```

### DUSt3R / MASt3R Point Clouds

Earlier DUSt3R/MASt3R-style outputs exist:

```text
AI/outputs/dust3r_bridge1/
AI/outputs/dust3r_bridge1_2m/
```

These are useful as additional 3D reconstruction experiments, but the current
handoff should treat MASt3R-SLAM as the stronger SLAM/vSLAM result.

### Nerfstudio / Splatfacto Gaussian Splatting

This was tested because the teacher asked about Gaussian Splatting.

Important document:

```text
AI/docs/nerfstudio_splatfacto_testing.md
```

Reusable script:

```text
AI/scripts/run_nerfstudio_bridge1_splat.sh
```

Important environment:

```text
WSL Ubuntu-24.04 as root
venv: /opt/nerfstudio-env
CUDA_HOME: /usr/local/cuda-12.6
torch: 2.5.1+cu121
nerfstudio: 1.1.5
gsplat: 1.4.0
```

Important no-spaces working folder:

```text
/opt/ftp_ai_ns_bridge1
```

The Windows project path contains spaces and caused issues with Nerfstudio and
COLMAP. Use `/opt/ftp_ai_ns_bridge1` for stable processing.

What worked:

- `gsplat` CUDA backend was precompiled successfully.
- Splatfacto trained for a short 50-iteration proof run.
- A real checkpoint was produced.
- The checkpoint was exported to a Gaussian Splat PLY.

Checkpoint:

```text
/opt/ftp_ai_ns_bridge1/nerfstudio_training/bridgevid1_splatfacto_compile_disabled/splatfacto/2026-06-10_105022/nerfstudio_models/step-000000049.ckpt
```

Exported file:

```text
AI/outputs/nerfstudio_bridgevid1_trained_splat/bridgevid1_trained_splat.ply
```

Known export info:

```text
file size: about 468 KB
gaussian vertices: 7927
```

Conclusion:

- The Splatfacto pipeline is technically working.
- The visual result is bad because COLMAP only registered `8` usable camera
  poses for the current dataset.
- MeshLab is also not a true Gaussian Splat viewer, so it displays the file more
  like a point cloud and ignores the real splat rendering behavior.
- This is proof of pipeline, not proof of useful reconstruction quality.

## Current Comparison Work

There is an experimental current-vs-final model comparison direction.

Upgraded on 2026-06-11 (see `AI/docs/method_comparison_table.md` for full
details and results). The comparison in `AI/src/ftp_ai/model_comparison.py`
now does:

```text
1. PCA + sign-flip coarse alignment (as before)
2. Trimmed scale-aware ICP refinement (robust to trees/traffic noise)
3. Current-to-model distances (scan noise / likely non-bridge points)
4. Model-to-current distances (the actual progress signal: which planned
   geometry has as-built evidence)
5. Per-section built percentage along the bridge axis (default 10 sections)
```

A completed bridge reference point cloud is available and is the better
reference (denser and bridge-only compared to the GLB):

```text
AI/data/BridgePointcloud/coverage_result.ply   (500,000 points, Open3D export)
```

Output folders:

```text
AI/outputs/comparison_colmap_bridgevid2_vs_final/              (v1, PCA only)
AI/outputs/comparison_mast3r_bridge1_vs_final/                 (v1, PCA only)
AI/outputs/comparison_mast3r_bridge1_vs_final_v2/              (ICP, GLB ref)
AI/outputs/comparison_colmap_bridgevid2_vs_final_v2/           (ICP, GLB ref)
AI/outputs/comparison_mast3r_bridge1_vs_bridgepointcloud/      (ICP, cloud ref)
AI/outputs/comparison_colmap_bridgevid2_vs_bridgepointcloud/   (ICP, cloud ref)
```

Key results (2026-06-11):

```text
ICP improved MASt3R-vs-GLB median distance from 0.02386 to 0.01384 and close
coverage from 68.6% to 76.59%.

Against the completed bridge point cloud:
- MASt3R cloud: 82.28% of model points have as-built evidence; sections range
  60-100% with one uncovered end section at 0%.
- COLMAP cloud: 56.2% overall; covered middle sections read 72-100% built and
  the uncovered bridge ends correctly read 0%.
```

The COLMAP per-section result is the strongest feasibility evidence so far:
the pipeline correctly distinguishes scanned/present sections from
missing/unscanned sections.

Important caveat:

```text
The alignment is experimental and scale-normalized. "Built %" means "the scan
found geometry near the planned geometry"; with a completed bridge and full
coverage video this measures coverage, not construction progress over time.
Do not present this as final accurate progress measurement. Present it as
proof that per-section comparison of a current reconstruction with a final
bridge reference works in principle.
```

## What The Results Mean

Segmentation alone is not enough.

It can show visible areas like deck/formwork/equipment, but it cannot reliably
calculate bridge progress without knowing:

- which bridge section the pixels belong to
- what the final state should look like
- whether something is temporary formwork or permanent structure
- whether an object is part of the bridge or just traffic/equipment

3D reconstruction alone is also not enough.

It can create point clouds/meshes, but not a clean progress report unless it is:

- aligned with the final model
- filtered to the bridge only
- split into known bridge sections/components
- validated with project-specific construction knowledge

Best production direction:

```text
Fixed drone path + high-overlap image capture + reconstruction + alignment to
final model + section/component-based comparison + segmentation/classification
as supporting evidence.
```

## What To Tell Teachers

Short version:

```text
We tested segmentation, COLMAP photogrammetry, MASt3R-SLAM/vSLAM, Gaussian
Splatting, and first current-vs-final 3D comparison. The main result is that
the AI models can produce useful prototypes, but the data collection process is
the limiting factor. A real implementation needs repeatable drone flights,
many overlapping images, calibration/control points, and a final digital twin
for comparison.
```

Hard things:

- drone footage has parallax, so simple panoramas do not work like phone
  panoramas
- moving vehicles and trees create noisy reconstruction
- bridge surfaces are repetitive and hard to match
- scale is arbitrary without calibration/GPS/control points
- segmentation masks are not the same as construction progress
- final model alignment is required before progress can be measured
- MeshLab does not properly render Gaussian Splatting files

What worked best so far:

- SAM3 progress prompts for simple visual demo
- SAM2 auto masks for "segment everything" research
- COLMAP when the video segment has good overlap
- MASt3R-SLAM for dense vSLAM-style point cloud

What did not work well:

- random video-to-Gaussian-Splat quality
- panorama stitching from flyover footage
- "segment literally everything and know what it is" without a classifier
- using current videos as if they were planned photogrammetry captures

## Suggested Next Tasks

### Task 1: Improve Data Selection

Pick a clean short bridge-only segment from `BridgeVid1-271223.mp4` or
`Bridgevid2-271223.mp4`.

Criteria:

- slow camera motion
- high overlap
- bridge visible most of the time
- not too much traffic/tree occlusion
- avoid sudden turns

Then rerun:

- COLMAP
- MASt3R-SLAM
- Nerfstudio/Splatfacto if enough poses register

### Task 2: Repeat Manual Frame Experiments On Better Segments

The first manual 10-frame experiment has already been done:

```text
AI/docs/manual_frame_reconstruction_testing.md
AI/outputs/manual10_colmap_bridgevid2_s22/
```

Result:

```text
10 selected frames
10 registered COLMAP images
10911 sparse points
```

Next: repeat this on other promising bridge-only segments and compare which
segment gives the cleanest point cloud.

### Task 3: Point Cloud Comparison Against Final BIM Model

This is now the main AI/3D direction.

Progress 2026-06-11: largely done at research level. ICP refinement,
model-to-current progress measurement, and per-section reporting are
implemented in `AI/src/ftp_ai/model_comparison.py` and tested against both
the GLB model and `AI/data/BridgePointcloud/coverage_result.ply`. See
`AI/docs/method_comparison_table.md`. Remaining for production: control-point
based calibrated alignment and real construction-stage scans.

Recommended process:

1. Convert final BIM/IFC/GLB/OBJ bridge model into a dense point cloud.
2. Choose the best current point cloud:
   - LiDAR if the client has it
   - MASt3R-SLAM point cloud
   - COLMAP point cloud from good selected frames
3. Pick matching bridge landmarks manually.
4. Estimate transform.
5. Run ICP refinement.
6. Compare only bridge deck/columns/known sections, not the whole scene.
7. Report missing/overlapping geometry per bridge section.

### Task 4: Define A Future Drone Flight Plan

Write down how the drone should fly if the project were done seriously.

Important:

- same path each inspection
- same camera angle
- high overlap
- enough side views and top-down views
- start/end at known points
- use markers/control points if possible

This is likely one of the most valuable research outputs.

### Task 5: Better Presentation Artifacts

Done 2026-06-11: see `AI/docs/method_comparison_table.md`.

Create a clear table:

```text
Method | Input | Output | Worked? | Problems | Recommendation
```

Suggested rows:

- OpenCV segmentation
- SAM3 progress prompts
- SAM2 automatic masks
- COLMAP
- MASt3R-SLAM / vSLAM
- DUSt3R / MASt3R
- Nerfstudio / Splatfacto Gaussian Splatting
- current-vs-final comparison

## Important Git Notes

Current branch:

```text
ai-vslam-gaussian-splat-test
```

Recent important commit:

```text
7702353 Document manual frame reconstruction test
828563e Add AI research handoff document
625e91b Retry Nerfstudio Splatfacto export
```

Generated outputs are generally not committed. Keep code/docs/config commits
small and do not add huge model/video/output files unless explicitly requested.

## Trello Tracking Rule

Keep Trello updated while working.

Board:

```text
FPT-AI
```

Current pattern:

- add/update cards in the correct daily list, for example `Wednesday 10/06`
- include story points in the card title, for example `(1)`, `(2)`, `(3)`
- use the `AI` label for AI work
- add `Testing`, `Documentation`, or `Scrum` labels when relevant
- describe:
  - what was tried
  - input data used
  - output folder/files
  - result
  - conclusion / next step

Trello access already works locally:

```text
Claude Code MCP server: trello
Command: npx -y atlassian-trello-mcp
Codex can also use the Trello REST API with TRELLO_API_KEY and TRELLO_TOKEN.
```

Important:

```text
After every meaningful experiment, setup task, documentation update, or research
decision, create or update a Trello card so daily progress tracking stays
accurate.
```

## Key Files To Read First

Start with:

```text
AI/docs/ai_handoff_for_claude.md
AI/docs/interim_ai_brief.md
AI/docs/vslam_gaussian_splat_testing.md
AI/docs/nerfstudio_splatfacto_testing.md
AI/docs/manual_frame_reconstruction_testing.md
AI/docs/method_comparison_table.md
AI/docs/dynamic_masking_experiment.md
```

Then inspect:

```text
AI/scripts/run_mast3r_bridge1_fast.sh
AI/scripts/run_nerfstudio_bridge1_splat.sh
AI/configs/mast3r_bridge_video_fast.yaml
```

Useful output folders:

```text
AI/outputs/mast3r_slam_bridge1_fast/
AI/outputs/colmap_mesh_bridgevid2_s22_full/
AI/outputs/nerfstudio_bridgevid1_trained_splat/
AI/outputs/comparison_mast3r_bridge1_vs_final/
AI/outputs/manual10_colmap_bridgevid2_s22/
AI/outputs/manual10_twoview_bridgevid2_1320_1725/
AI/outputs/bridgevid1_sam2_overlay_video/
AI/outputs/bridgevid1_full_sam2_auto/
```

## Final Handoff Summary

This is currently a research project about feasibility. The work so far shows
that multiple AI approaches can run, but the best final system depends mostly on
controlled data gathering and alignment with a final model.

Do not spend too much time trying to make poor existing drone video look perfect.
The stronger research conclusion is:

```text
For accurate bridge progress tracking, the team must design the capture process
first. AI reconstruction and segmentation only become reliable when the drone
data is planned, repeatable, and aligned with the final digital twin.
```
