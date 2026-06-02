# Interim AI Brief - June 3, 2026

## Current AI Goal

Detect visible construction progress on the GOT bridge from drone footage and
prepare a path toward comparing the real construction state with the final 3D
bridge model.

## What We Built So Far

- Drone video input pipeline: extract usable frames from bridge footage.
- Image preprocessing: border cropping and optional resizing for GPU limits.
- Segmentation modes:
  - `classical`: OpenCV fallback, no AI model required.
  - `sam3-progress`: SAM3 text-prompt segmentation for bridge progress states.
  - `sam3-objects`: SAM3 text-prompt segmentation for many named object types.
  - `sam2-auto`: SAM2 automatic "segment everything" masks.
- ROI mode: SAM3 detects the construction site first, then the pipeline segments
  only that cropped work zone.
- Output artifacts: annotated images, JSON progress reports, object masks, and
  now a sparse 3D point cloud proof of concept.

## Segmentation Experiments

### Classical OpenCV Segmentation

Result: Useful only as a fallback.

Pros:
- Runs without GPU or model weights.
- Good for proving the pipeline shape.

Cons:
- Does not understand construction objects.
- Masks are noisy and based on edges/color, not semantic meaning.
- Not good enough for progress estimation.

Conclusion: keep as a fallback only.

### SAM3 Progress Prompts

Result: Best current option for a progress demo.

Prompts tested:
- `bridge deck`, `concrete bridge deck`, `finished bridge deck`
- `bridge construction`, `unfinished construction`, `construction formwork`,
  `bridge girders`
- `construction equipment`, `crane`

Pros:
- Gives named progress classes, so it can feed progress reporting.
- Works well when the image is cropped to the construction ROI.
- Easy to tune by changing text prompts.

Cons:
- It only segments what we ask for.
- Broad prompts such as `road surface` caused false positives on normal roads.
- It does not automatically discover every object.

Conclusion: use this for interim progress visualization, especially on cropped
bridge/work-zone images.

### SAM3 Object Prompts

Result: More complete, but visually crowded and still prompt-limited.

Prompts tested include:
- bridge deck, concrete slab, bridge girder, bridge column
- formwork, scaffolding, rebar, construction material
- crane, excavator, truck, bus, car, motorbike, person
- road, tree, building, water

Pros:
- Can attach object-like names to masks.
- Useful to inspect what SAM3 can recognize in construction scenes.

Cons:
- Only finds object concepts listed in prompts.
- Many overlapping boxes/masks make the image harder to read.
- Some objects are mislabeled or missed.

Conclusion: useful for visual exploration, but not the best final strategy for
"segment everything".

### SAM2 Automatic Segmentation

Result: Best current experiment for "segment everything".

Pros:
- No text prompts needed.
- Separates many visual regions/objects automatically.
- Cleaner for dense object discovery than SAM3 object prompts.

Cons:
- Masks are unlabeled: output says `object`, not `deck` or `formwork`.
- Does not directly produce progress classes.
- Needs a second classification step to become useful for progress.

Conclusion: SAM2 automatic masks are the best candidate for dense segmentation.
For final progress tracking, combine SAM2 masks with a trained classifier or a
YOLO segmentation model.

## Current Recommendation

Use two different modes depending on the task:

- For interim demo progress: `sam3-progress` + ROI crop.
- For "segment everything" research: `sam2-auto`.

Best future architecture:

1. Detect/crop the bridge construction ROI.
2. Generate dense masks with SAM2 automatic segmentation.
3. Classify masks into project-specific classes:
   - completed deck
   - unfinished deck/formwork
   - columns/supports
   - rebar
   - equipment
   - temporary structures
4. Estimate progress per bridge section.
5. Compare this with the planned/final IFC/3D model.

## 3D Work Tested Before Interim

We tested three first steps toward 3D reconstruction:

- our own two-view sparse point cloud prototype
- COLMAP photogrammetry
- MASt3R-SLAM feasibility

### Custom Two-View Prototype

Generated demo:
- `outputs/interim_3d_bridgevid2_pair_600_720/sparse_point_cloud.ply`
- `outputs/interim_3d_bridgevid2_pair_600_720/pointcloud_preview.jpg`
- `outputs/interim_3d_bridgevid2_pair_600_720/matches_preview.jpg`
- `outputs/interim_3d_bridgevid2_pair_600_720/metrics.json`

Metrics:
- Video: `Bridgevid2-271223.mp4`
- Frames: 600 and 720
- Matcher: SIFT
- Raw matches: 1787
- Geometric inliers: 1587
- Pose inliers: 1482
- 3D points written: 1306
- Mean reprojection error: 9.089 px
- Median reprojection error: 8.058 px

What this proves:
- Drone frames contain enough matching features for 3D reconstruction.
- A sparse point cloud can be generated from the footage.
- The result is not yet a finished 3D bridge model.

### COLMAP Photogrammetry And Mesh Test

COLMAP was tested on bridge-only frames extracted from `Bridgevid2-271223.mp4`.
The conda COLMAP package installed but failed to start on Windows because of a
runtime DLL issue. The official Windows no-CUDA binary did run for sparse
reconstruction, but dense stereo requires the CUDA COLMAP binary. After
downloading the official CUDA-enabled Windows binary, dense reconstruction and
meshing worked.

Generated demo:
- `outputs/colmap_mesh_bridgevid2_s22_full/sparse_point_cloud.ply`
- `outputs/colmap_mesh_bridgevid2_s22_full/dense_point_cloud.ply`
- `outputs/colmap_mesh_bridgevid2_s22_full/mesh.ply`
- `outputs/colmap_mesh_bridgevid2_s22_full/summary.json`

Metrics:
- Video segment: starts around 22 seconds in `Bridgevid2-271223.mp4`
- Frame interval: 0.25 seconds
- Input frames: 32
- Registered images: 32
- Sparse 3D points: 25739
- Dense vertices: 178539
- Mesh vertices: 12672
- Mesh faces: 23118

Conclusion:
- COLMAP can create an actual 3D mesh from the drone footage when the segment has
  enough overlap and the CUDA binary is used.
- Not every video segment works. Earlier segments registered only 2 images and
  produced empty meshes.
- The mesh is not yet a clean BIM/IFC object. It is a reconstructed scene mesh
  with arbitrary scale, possible traffic/background noise, and no semantic
  bridge element labels.
- Next improvement: use longer bridge-only sequences, camera calibration/GPS/IMU
  if available, and post-process the mesh/point cloud to isolate the bridge.

### MASt3R-SLAM Feasibility Test

The official MASt3R-SLAM repository was cloned under
`AI/.external/mast3r-slam`.

What the official project expects:
- Python 3.11 environment
- CUDA-enabled PyTorch
- CUDA toolkit/compiler (`nvcc`)
- native C++/CUDA extension build
- MASt3R checkpoints
- preferably Ubuntu, or WSL using the repository's `windows` branch

Local result:
- The laptop GPU is available to PyTorch in our SAM environment.
- The machine does not currently expose `nvcc`, `cl`, or `CUDA_PATH`.
- The MASt3R-SLAM package build fails before runtime with:
  `CUDA_HOME environment variable is not set`.
- WSL is installed as a Windows feature, but no Linux distribution is installed.

Conclusion:
- MASt3R-SLAM is technically relevant for our 3D direction.
- We could not run it natively before the interim because the CUDA development
  toolkit/build environment is missing.
- Next step is to run MASt3R-SLAM in Ubuntu/WSL2 or on a cloud/Linux GPU
  machine, then feed it the bridge-only MP4 or extracted image folder.

Current 3D limitations:
- Sparse point cloud only, no complete mesh.
- Scale is arbitrary without camera calibration/GPS/IMU.
- Moving vehicles and background buildings can create noisy points.
- Simple panoramas do not work well because drone fly-over footage has parallax.

## 3D Plan For Coming Weeks

1. Extract many overlapping bridge-only frames.
2. Run a real photogrammetry/SLAM pipeline:
   - COLMAP
   - OpenDroneMap
   - Meshroom
   - MASt3R/Dust3R if feasible on our hardware
3. Produce one of:
   - sparse point cloud
   - dense point cloud
   - mesh
   - orthomosaic/top-down map
4. Align the reconstruction with the final bridge model/IFC:
   - manually selected control points first
   - later automatic registration if possible
5. Compare detected as-built structure against planned sections.

## Demo Flow For Presentation

1. Show original drone frame.
2. Show SAM3 progress segmentation on bridge ROI.
3. Show SAM2 automatic segmentation as "segment everything" experiment.
4. Show sparse 3D match preview.
5. Show sparse point cloud preview.
6. Explain next step: photogrammetry/SLAM and classification for real progress
   comparison with the final 3D model.

## Honest Status

The AI part has working prototypes for segmentation and an initial 3D direction.
The biggest technical insight is that segmentation alone is not enough. For real
progress tracking, we need:

- reliable bridge/work-zone localization
- dense masks or trained construction-class segmentation
- classification into progress states
- 3D/orthomosaic alignment with the final model

## Sources Checked

- COLMAP official project: `https://github.com/colmap/colmap`
- MASt3R-SLAM official project: `https://github.com/rmurai0610/MASt3R-SLAM`
