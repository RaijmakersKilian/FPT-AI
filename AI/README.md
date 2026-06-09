# FTP AI

AI prototype for the FPT construction progress project. The scope is the GOT Bridge
from the XL8 IFC file.

The pipeline follows the project brief:

1. Extract representative keyframes from drone video.
2. Stitch selected frames into a bridge panorama.
3. Segment visible bridge regions.
4. Classify segments into progress-related classes.
5. Estimate section and overall progress.
6. Export annotated images and a structured JSON report.

This repository starts with a runnable baseline. It does not require SAM3, SAM2, or YOLO
weights to prove the workflow: `classical` segmentation and rule-based
classification are included as fallbacks. SAM3/SAM2/YOLO can be plugged in later through
the interfaces in `src/ftp_ai/segmentation.py` and `src/ftp_ai/classification.py`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

If editable install is not needed:

```powershell
pip install -r requirements.txt
```

## Run On A Video

```powershell
python -m ftp_ai.cli run-video `
  --video data/raw/DJI_0105.MP4 `
  --output outputs/dji_0105 `
  --sample-every 10
```

The output folder will contain:

- `keyframes/`: selected frames after blur and motion filtering
- `panorama.jpg`: stitched or concatenated panorama
- `annotated.jpg`: panorama with segment masks and labels
- `report.json`: progress summary for backend/database integration

## Run On Existing Images

Use this when frames have already been extracted manually:

```powershell
python -m ftp_ai.cli run-images `
  --images data/frames `
  --output outputs/manual_frames
```

## Run On One Image

This is the best mode for testing model quality because it avoids segmenting a
large contact sheet with black gaps.

```powershell
python -m ftp_ai.cli run-image `
  --image outputs/dvc_27122023/keyframes/frame_00000000.jpg `
  --output outputs/sam_test
```

## Optional SAM3 Setup

SAM3 is optional because it is a heavy GPU dependency. Meta's official SAM3 setup
requires Python 3.12+, PyTorch 2.7+, a CUDA 12.6+ compatible GPU, and accepted
Hugging Face access to the SAM3 checkpoints.

Install it in a separate environment or after the baseline works:

```powershell
pip install torch==2.10.0 torchvision --index-url https://download.pytorch.org/whl/cu128
git clone https://github.com/facebookresearch/sam3.git ..\sam3
pip install -e ..\sam3
huggingface-cli login
```

Alternatively, put your token in `data/.env`:

```text
HF_TOKEN=hf_your_token_here
```

Then test SAM3 on a single real frame:

```powershell
python -m ftp_ai.cli run-image `
  --image outputs/dvc_27122023/keyframes/frame_00000000.jpg `
  --output outputs/sam3_frame_00000000 `
  --segmenter sam3
```

The current SAM3 prompts are in `src/ftp_ai/segmentation.py`:

- `completed concrete bridge deck`
- `construction formwork`
- `exposed steel rebar`
- `bridge support column`
- `construction equipment`

## Construction ROI Mode

SAM3 is currently strongest at finding the work zone with the broad prompt
`construction site`. Use ROI mode to crop the drone frame to that area before
running the rest of the pipeline:

```powershell
python -m ftp_ai.cli run-image `
  --image outputs/dvc_27122023/keyframes/frame_00000000.jpg `
  --output outputs/roi_test `
  --roi sam3-construction
```

The output folder includes:

- `analysis_image.jpg`: image after basic preprocessing
- `roi_mask.jpg`: SAM3 mask for the construction site
- `roi_image.jpg`: cropped region used for progress estimation
- `annotated.jpg`: segmentation result on the cropped ROI

## Batch ROI Analysis

Use this to produce several demo examples from the extracted keyframes. The
command selects a spread of frames across the folder, runs ROI analysis on each,
and writes a `summary.json`.

```powershell
python -m ftp_ai.cli run-roi-batch `
  --images outputs/dvc_27122023/keyframes `
  --output outputs/roi_batch_demo `
  --limit 8
```

Each selected frame gets its own output folder containing `roi_image.jpg`,
`annotated.jpg`, and `report.json`.

## Full-Video Panorama Segmentation

For bridge-only drone flights, create one large panorama from selected frames and
run progress segmentation on the panorama. SAM3 needs a resized analysis image on
8 GB GPUs, so cap the analysis dimension:

```powershell
python -m ftp_ai.cli run-video `
  --video data/raw/BridgeVid1-271223.mp4 `
  --output outputs/bridgevid1_panorama_progress `
  --sample-every 120 `
  --segmenter sam3-progress `
  --analysis-max-dimension 1800
```

Key outputs:

- `panorama.jpg`: stitched bridge panorama
- `analysis_image_resized.jpg`: panorama resized for SAM3
- `annotated.jpg`: progress segmentation on the panorama
- `report.json`: section-level prototype progress report

If the normal `run-video` command produces a grid/contact-sheet image, build a
strict smooth panorama from the extracted keyframes:

```powershell
python -m ftp_ai.cli build-panorama `
  --images outputs/bridgevid1_panorama_progress/keyframes `
  --output outputs/bridgevid1_smooth_panorama/panorama.jpg
```

There is also an experimental neighboring-frame strip mode:

```powershell
python -m ftp_ai.cli build-panorama `
  --images outputs/bridgevid1_panorama_progress/keyframes `
  --output outputs/bridgevid1_strip_panorama/panorama.jpg `
  --method strip
```

Important: this is still not a true orthomosaic. Apple-style panoramas work best
when the camera rotates from one position. A drone fly-over translates through a
3D scene, so trees, buildings, roads, and the bridge move differently. For a
real map-like "one total picture", use photogrammetry/orthomosaic software such
as OpenDroneMap, COLMAP, or a MASt3R/Dust3R-based reconstruction workflow.

## SAM3 Progress Segmentation

For the bridge footage, SAM3 responds better to construction-state prompts than
to detailed BIM terms like `rebar` or `bridge deck`. Use the progress preset on a
cropped ROI image:

```powershell
python -m ftp_ai.cli run-image `
  --image outputs/bridgevid1_roi_batch/002_frame_00000660/roi_image.jpg `
  --output outputs/sam3_progress_demo `
  --segmenter sam3-progress
```

The preset maps these prompts to progress labels:

- `bridge deck`, `concrete bridge deck`, `finished bridge deck` -> `completed_deck`
- `bridge construction`, `unfinished construction`, `construction formwork`, `bridge girders` -> `formwork`
- `construction equipment`, `crane` -> `equipment`

The preset applies stricter filtering than raw SAM3: tiny masks are removed,
overlapping masks are deduplicated, and annotations only draw the most useful
progress labels so the demo image stays readable.

## SAM3 Object Segmentation

Use this mode when you want visual object discovery instead of progress scoring.
It asks SAM3 for many object concepts such as bridge deck, slab, girder, crane,
truck, person, road, tree, building, and water, then draws the detected instances
with unique colors.

```powershell
python -m ftp_ai.cli run-image `
  --image outputs/keep/bridgevid1_sam3_progress_vivid/analysis_image.jpg `
  --output outputs/bridgevid1_sam3_objects_demo `
  --segmenter sam3-objects `
  --analysis-max-dimension 1400
```

The `overall_completion` value in this mode is not meaningful, because the
segments are generic objects rather than progress classes.

Dense object modes draw thinner boxes, smaller labels, and lighter masks than
progress mode so the image stays easier to inspect.

## SAM2 Segment Everything

SAM2 has an automatic mask generator that can segment many unlabeled regions
without text prompts. This is a better experiment for "segment everything" than
SAM3 text prompts, but it needs the optional SAM2 package and checkpoint.

Expected `.env` values:

```text
SAM2_CHECKPOINT=models/sam2.1_hiera_large.pt
SAM2_MODEL_CFG=configs/sam2.1/sam2.1_hiera_l.yaml
```

Run it with:

```powershell
python -m ftp_ai.cli run-image `
  --image outputs/keep/bridgevid1_sam3_progress_vivid/analysis_image.jpg `
  --output outputs/bridgevid1_sam2_auto_demo `
  --segmenter sam2-auto `
  --analysis-max-dimension 1400
```

SAM2 automatic masks are unlabeled, so the output labels are shown as `object`.
Use this to inspect whether dense segmentation is useful. Do not use its
`overall_completion` value as real progress.

## Sparse 3D Proof Of Concept

Use this to generate a small two-view point cloud from bridge drone footage. It
is useful for the interim presentation because it proves the footage can support
3D reconstruction, but it is not a complete metric bridge model.

```powershell
python -m ftp_ai.cli build-sparse-3d `
  --video data/raw/Bridgevid2-271223.mp4 `
  --output outputs/interim_3d_bridgevid2_pair_600_720 `
  --frame-a 600 `
  --frame-b 720 `
  --max-dimension 1280 `
  --max-points 6000
```

The output folder contains:

- `sparse_point_cloud.ply`: colored sparse point cloud
- `pointcloud_preview.jpg`: 2D preview of the point cloud
- `matches_preview.jpg`: matched features between the two frames
- `metrics.json`: match counts, inliers, reprojection error, and limitations

For a real bridge model, the next step is a full photogrammetry or SLAM pipeline
such as COLMAP, OpenDroneMap, Meshroom, or MASt3R/Dust3R.

## COLMAP Mesh Reconstruction

Use this to turn a bridge-only drone video segment into a dense point cloud and
mesh. This requires the CUDA-enabled COLMAP binary; the no-CUDA binary can run
sparse reconstruction but cannot run dense stereo.

Successful interim command:

```powershell
python -m ftp_ai.cli build-colmap-mesh `
  --video data/raw/Bridgevid2-271223.mp4 `
  --output outputs/colmap_mesh_bridgevid2_s22_full `
  --colmap-path .external/colmap/cuda/bin/colmap.exe `
  --frame-interval 0.25 `
  --start-seconds 22 `
  --max-frames 32 `
  --blur-threshold 35 `
  --max-image-size 900 `
  --matcher exhaustive
```

Result from this run:

- input frames: 32
- registered images: 32
- sparse points: 25739
- dense vertices: 178539
- mesh vertices: 12672
- mesh faces: 23118

Key outputs:

- `sparse_point_cloud.ply`: sparse SfM point cloud
- `dense_point_cloud.ply`: dense fused point cloud
- `mesh.ply`: reconstructed 3D mesh
- `summary.json`: reconstruction metrics and output paths
- `logs/`: COLMAP logs per step

Open `mesh.ply` in Blender, MeshLab, CloudCompare, or Windows 3D Viewer. The
mesh is not yet a clean BIM model: scale is arbitrary without camera calibration
or GPS/IMU, and moving traffic/background geometry can still be reconstructed.

## Experimental 3D Model Comparison

Use this to compare a current/as-built reconstruction against the completed
bridge model. The current implementation performs a rough PCA normalization and
nearest-neighbor distance comparison, so it is a feasibility test rather than a
survey-accurate BIM comparison.

```powershell
python -m ftp_ai.cli compare-3d-model `
  --current outputs/mast3r_slam_bridge1_fast/pointcloud.ply `
  --final-model ../Frontend/KCPT_Ki_centered.glb `
  --output outputs/comparison_mast3r_bridge1_vs_final `
  --max-current-points 150000 `
  --max-model-points 150000
```

Outputs:

- `comparison_summary.json`: distance statistics and coverage percentages
- `comparison_preview.jpg`: top-down visual comparison
- `difference_pointcloud.ply`: current reconstruction colored by distance
- `normalized_final_model_points.ply`: sampled final model points in normalized space

Color meaning:

- green: current reconstruction is close to the completed model
- yellow/orange: some difference
- red: far from the model, noisy, background, or not aligned

Current test results:

- MASt3R-SLAM bridge point cloud vs final model:
  - median distance: `0.02386`
  - P90 distance: `0.08911`
  - close coverage: `68.6%`
- COLMAP dense point cloud vs final model:
  - median distance: `0.0503`
  - P90 distance: `0.31626`
  - close coverage: `42.49%`

Interpretation: this supports the teacher's idea that we can compare the current
state with the finished model, but final progress tracking needs better
alignment: camera calibration, control points, GPS/RTK, or manually selected
corresponding points between the reconstruction and BIM/GLB model.

## Current Classes

The baseline progress classes are:

- `completed_deck`
- `formwork`
- `exposed_rebar`
- `support_column`
- `equipment`
- `unknown`

Progress is visual only, as requested in the project brief. Budget and disbursed
cost are intentionally not part of this AI module.

## Recommended Next Steps

1. Place GOT bridge videos under `data/raw/`.
2. Run the baseline on one short video clip and inspect `annotated.jpg`.
3. Label 200-300 GOT bridge frames in Roboflow.
4. Train a classifier/segmenter and replace the fallback classifier.
5. Align section output with XL8 IFC element IDs once the IFC file is available.
