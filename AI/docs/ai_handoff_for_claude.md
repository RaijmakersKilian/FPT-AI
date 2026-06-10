# AI Handoff For Claude Code

Date: 2026-06-10

Current branch: `ai-vslam-gaussian-splat-test`

Purpose of this document: give another coding assistant enough context to
continue the AI research work without needing the full chat history.

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

Known output folders:

```text
AI/outputs/comparison_colmap_bridgevid2_vs_final/
AI/outputs/comparison_mast3r_bridge1_vs_final/
```

Known result from the MASt3R-SLAM comparison:

```text
median distance: 0.02386
P90 distance: 0.08911
close coverage: 68.6%
```

Important caveat:

```text
The alignment is experimental. Do not present this as final accurate progress
measurement. Present it as proof that comparing a current reconstruction with a
final bridge model is possible in principle.
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

### Task 2: Manual Frame Experiment

Extract around 10 non-consecutive but overlapping good frames and inspect them
manually.

Goal:

```text
Check whether carefully selected frames give better point clouds than automatic
frame extraction.
```

This matches the teacher note: "maybe take 10 frames not consecutive and see if
they make a point cloud, then manually match."

### Task 3: Better Current-Vs-Final Alignment

Improve comparison with the final model by adding manual control points.

Recommended process:

1. Open current point cloud and final bridge model.
2. Pick matching bridge landmarks manually.
3. Estimate transform.
4. Compare only bridge deck/columns, not the whole scene.

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
625e91b Retry Nerfstudio Splatfacto export
```

Generated outputs are generally not committed. Keep code/docs/config commits
small and do not add huge model/video/output files unless explicitly requested.

## Key Files To Read First

Start with:

```text
AI/docs/ai_handoff_for_claude.md
AI/docs/interim_ai_brief.md
AI/docs/vslam_gaussian_splat_testing.md
AI/docs/nerfstudio_splatfacto_testing.md
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
