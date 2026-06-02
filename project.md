# AI Module — Construction Progress Monitoring
## GOT Bridge — FPT AI Project

---

## Project Overview

This project is an automated construction progress monitoring system built for FPT AI.
The system processes UAV (drone) video footage of the GOT bridge construction site in Ho Chi Minh City, Vietnam,
and compares what is visually detected against the official 3D BIM model (IFC file XL8) to estimate how much of the bridge has been completed.

**Industrial partner:** FPT AI  
**Academic institution:** Howest University of Applied Sciences  
**Team size:** 5 students  
**Methodology:** Agile Scrum  

---

## Scope

- **In scope:** GOT bridge only (IFC file XL8) — one bridge, visual progress tracking only
- **Out of scope:** tunnels, underground sections, budget/purchase data, other IFC files (XL5–XL7, XL9–XL17)
- **Data:** Multiple dated UAV videos of the GOT bridge (October–December 2025)
- **Output:** Website where user uploads drone video + IFC model → system returns progress report

---

## Full System Pipeline

```
UAV Video (MP4)
      ↓
Stage 1 — Keyframe Extraction
      ↓
Stage 2 — AI Detection & Segmentation  ← THIS MODULE
      ↓
Stage 3 — 3D Reconstruction (MASt3R-SLAM + DUSt3R)
      ↓
Stage 4 — IFC Alignment (XL8 BIM model)
      ↓
Stage 5 — Progress Estimation
      ↓
Stage 6 — Database Storage (MySQL)
      ↓
Stage 7 — Frontend + PDF Report
```

---

## AI Module Responsibilities (Stage 1 + Stage 2)

### Stage 1 — Keyframe Extraction

**File:** `src/ai/keyframe_extraction.py`

Extract representative frames from the drone video. A 30-minute video = ~54,000 frames.
Target output: 200–400 high-quality frames.

**Logic:**
1. Sample every Nth frame (sample_rate=10 default)
2. Blur filter — discard frames below sharpness threshold (Laplacian variance < 100)
3. Motion filter — discard near-duplicate frames (optical flow magnitude < 0.02)
4. Save keyframes as JPG to output directory with frame index in filename

**Input:** path to MP4 video file  
**Output:** list of saved keyframe image paths

```python
def extract_keyframes(video_path: str, output_dir: str, sample_rate: int = 10) -> list[str]:
    """Returns list of saved keyframe paths"""
```

---

### Stage 2a — Panoramic Stitching

**File:** `src/ai/panorama.py`

Stitch selected keyframes into one continuous top-down panoramic view of the full bridge length.

**Tool:** OpenCV Stitcher (cv2.Stitcher_PANORAMA)  
**Fallback:** If OpenCV stitcher fails, use MASt3R for frame alignment  
**Input:** list of keyframe image paths  
**Output:** single panoramic image (JPG)

```python
def create_bridge_panorama(frame_paths: list[str], output_path: str) -> str:
    """Returns path to stitched panorama image"""
```

---

### Stage 2b — SAM2 Automatic Segmentation

**File:** `src/ai/segmentation.py`

Run SAM2's automatic mask generator on the panoramic image.
No prompts, no training data needed for this step — fully automatic.

**Model:** SAM2 (sam2_hiera_large.pt)  
**Key parameters:**
- points_per_side = 32
- pred_iou_thresh = 0.85
- stability_score_thresh = 0.9
- min_mask_region_area = 1000

**Input:** panoramic image path  
**Output:** list of SAM2 mask dicts (segmentation, area, bbox, stability_score)

```python
def segment_bridge(image_path: str) -> list[dict]:
    """Returns list of SAM2 mask dictionaries"""
```

---

### Stage 2c — Segment Classification

**File:** `src/ai/classification.py`

Classify each SAM2 segment into one of the target construction classes.
Uses a fine-tuned YOLO26 classifier on cropped segment regions.

**Target classes (derived from XL8 IFC elements):**

| Class | Visual indicator | Construction status |
|---|---|---|
| `deck_complete` | Smooth grey/white concrete surface | Built |
| `deck_incomplete` | Rough surface, materials present | In progress |
| `formwork` | Brown wooden/metal temporary structure | In progress |
| `rebar_exposed` | Dark steel mesh visible | Not started |
| `support_column` | Vertical concrete pillar | Built |
| `equipment` | Cranes, trucks, machinery | Ignored in progress calc |

**Input:** original image + list of SAM2 masks  
**Output:** list of labeled detections

```python
def classify_segments(image: np.ndarray, masks: list[dict]) -> list[dict]:
    """
    Returns list of dicts:
    {
        "class": "deck_complete",
        "confidence": 0.91,
        "mask": np.ndarray,     # boolean pixel mask
        "bbox": [x1, y1, x2, y2],
        "area": int,
        "position_3d": None     # filled in by Stage 3
    }
    """
```

---

### Stage 2 Output Contract

This is what the AI module hands to the 3D reconstruction team.
Every frame produces a JSON-serializable detection result:

```json
{
  "frame_id": 42,
  "frame_path": "frames/AP_13_10_2025/frame_001200.jpg",
  "panorama_path": "outputs/panorama_AP_13_10_2025.jpg",
  "detections": [
    {
      "class": "deck_complete",
      "confidence": 0.91,
      "bbox": [120, 340, 580, 620],
      "mask_polygon": [[120, 340], [580, 340], [580, 620], [120, 620]],
      "area_pixels": 156000,
      "position_3d": null
    },
    {
      "class": "formwork",
      "confidence": 0.87,
      "bbox": [600, 340, 900, 580],
      "mask_polygon": [[600, 340], [900, 340], [900, 580], [600, 580]],
      "area_pixels": 72000,
      "position_3d": null
    }
  ]
}
```

---

## Model Comparison Study

Before finalising the pipeline, run a structured comparison.
All models tested on the same GOT bridge frames.

**Evaluation metrics:** mAP@50, mAP@50-95, Mask IoU, inference time (ms), FPS

## Fine-tuning Strategy

### YOLO26 Classifier
- Fine-tune on cropped SAM2 segments labeled by class
- Training data: manually labeled GOT bridge frames (target 200–300 frames via Roboflow)
- Supplement: AIDCON dataset, Roboflow Universe construction datasets
- Export format: YOLO format (.yaml dataset config)
- Training script: `src/ai/training/train_classifier.py`

### SAM2 Mask Decoder (optional)
- Only fine-tune the mask decoder — keep image encoder frozen
- Fine-tune on bridge-specific imagery (concrete, steel, formwork textures)
- Training script: `src/ai/training/finetune_sam2.py`

---

## Data

### Drone Videos
Located in: `data/videos/`

| Filename | Date | Notes |
|---|---|---|
| AP_13-10-2025.mp4 | Oct 13 2025 | Earliest — baseline state |
| AP_27-10-2025.mp4 | Oct 27 2025 | 2 weeks progress |
| AP_24-11-2025.mp4 | Nov 24 2025 | 1 month progress |
| AP_29-12-2025.mp4 | Dec 29 2025 | Latest available |

### IFC Model
- **In scope:** `data/ifc/XL8.ifc` — GOT Bridge
- All other IFC files (XL5–XL17) are out of scope for this phase

### Labeled Dataset
- Tool: Roboflow
- Export format: YOLOv8 format
- Location after export: `data/labeled/`
- Classes: deck_complete, deck_incomplete, formwork, rebar_exposed, support_column, equipment

---

## Project Structure

```
/
├── data/
│   ├── videos/              # raw MP4 drone videos
│   ├── ifc/                 # IFC model files (XL8 in scope)
│   └── labeled/             # Roboflow labeled dataset
├── src/
│   ├── ai/
│   │   ├── keyframe_extraction.py
│   │   ├── panorama.py
│   │   ├── segmentation.py
│   │   ├── classification.py
│   │   ├── training/
│   │   │   ├── train_classifier.py
│   │   │   └── finetune_sam2.py
│   │   └── comparison/
│   │       └── run_comparison.py
│   ├── reconstruction/      # MASt3R-SLAM + DUSt3R (teammate)
│   ├── alignment/           # IFC matching (teammate)
│   ├── progress/            # progress estimation (teammate)
│   ├── database/            # MySQL models (teammate)
│   └── frontend/            # web interface (teammate)
├── outputs/
│   ├── frames/              # extracted keyframes per video
│   ├── panoramas/           # stitched bridge panoramas
│   ├── detections/          # JSON detection results per frame
│   └── comparison/          # model comparison results CSV
├── notebooks/               # experimentation notebooks
├── requirements.txt
├── AI.md                    # this file
└── README.md
```

---

## Tech Stack — AI Module

| Tool | Purpose | Version |
|---|---|---|
| Python | Language | 3.10+ |
| PyTorch | Deep learning | latest |
| Ultralytics | YOLO26 training and inference | latest |
| SAM2 (Meta) | Automatic segmentation | latest |
| OpenCV | Video processing, stitching | latest |
| NumPy | Array operations | latest |
| Supervision | Detection visualization | latest |
| ifcopenshell | IFC model parsing | latest |
| Roboflow | Dataset labeling and management | online |

Install:
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
pip install ultralytics opencv-python numpy supervision ifcopenshell
git clone https://github.com/facebookresearch/sam2.git && cd sam2 && pip install -e .
```

---

## Database Schema (MySQL) — AI Relevant Tables

The AI module writes to these tables after processing:

**`video`** — one row per drone video uploaded  
**`processing_run`** — one row per pipeline execution  
**`detected_element`** — one row per detected segment per frame  
**`progress_report`** — one row per element type per run  

See full schema in `src/database/schema.sql`

---

## Progress Definition

Progress is expressed at three levels:

**Level 1 — Section-based (length)**
Bridge divided into equal sections. Each section classified as complete / in progress / not started.

**Level 2 — Element-based (presence)**
Each structural element type checked for presence or absence.

**Level 3 — Overall score**
Weighted combination → single percentage.

Example output:
```
Section 1 (0m–45m):    Complete        ✅
Section 2 (45m–90m):   In progress     🔄  60%
Section 3 (90m–135m):  Not started     ❌

Overall: 53% complete
Basis: deck surface coverage + column presence detection
```

---

## Key Decisions Already Made

- SAM2 automatic (no prompts) is the primary segmentation approach
- YOLO26 is the classifier on top of SAM2 segments
- Panoramic stitching before segmentation — not per-frame
- Keypoints (YOLO26-pose) is an alternative being compared
- No budget or purchase data — visual only
- One bridge only (XL8 GOT) for this phase
- Multiple dated videos enable 4D progress tracking over time
- MySQL for database
- Web frontend for upload + results

---

## What Claude Code Should Help Build

When working on this project, focus on these tasks in order:

1. `keyframe_extraction.py` — extract smart keyframes from MP4
2. `panorama.py` — stitch frames into bridge panorama
3. `segmentation.py` — run SAM2 automatic on panorama
4. `classification.py` — classify SAM2 segments with YOLO26
5. `run_comparison.py` — benchmark all models on same frames
6. `train_classifier.py` — fine-tune YOLO26 on labeled bridge data
7. Integration — connect all stages into one pipeline function

Always write modular, well-typed Python. Each function should have a clear input/output contract matching the definitions in this file. All intermediate results should be saved to disk so stages can be run independently.