# FTP-AI — Installation Guide

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Project Overview](#2-project-overview)
3. [Prerequisites](#3-prerequisites)
4. [Step 1 — Clone the Repository](#4-step-1--clone-the-repository)
5. [Step 2 — PostgreSQL Database Setup](#5-step-2--postgresql-database-setup)
6. [Step 3 — Backend Setup](#6-step-3--backend-setup)
7. [Step 4 — Running the Application](#7-step-4--running-the-application)
8. [Optional: AI Pipeline Setup](#8-optional-ai-pipeline-setup)
9. [Optional: XR / 3D Processing Setup](#9-optional-xr--3d-processing-setup)
10. [Optional: SAM3 Segmentation Model](#10-optional-sam3-segmentation-model)
11. [Folder Structure Reference](#11-folder-structure-reference)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10 64-bit | Windows 11 64-bit |
| RAM | 8 GB | 16 GB |
| Disk | 10 GB free | 30 GB free |
| Python | 3.10 | 3.10 – 3.12 |
| GPU | — | NVIDIA GPU with CUDA 11.8+ (for SAM2/SAM3/COLMAP) |
| PostgreSQL | 14 | 15 or 16 |

> The base system (backend + frontend + 3D viewer) runs without a GPU. A GPU is only needed for the optional deep-learning segmentation and 3D reconstruction tools.

---

## 2. Project Overview

FTP-AI is a drone-inspection dashboard for bridge construction monitoring. The 3D BIM viewer and coverage inspector load automatically when the backend starts.

```
Browser  →  http://127.0.0.1:8000
                │
           FastAPI Backend
                │
                ├── PostgreSQL  (video metadata, detections)
                ├── Frontend/   (Dashboard, 3D viewer, inspector)
                └── XR/         (coverage_result.ply, coverage_data.json)
```

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | HTML / CSS / JS / Three.js | Dashboard, 3D BIM viewer |
| Backend | Python / FastAPI / Uvicorn | REST API, serves the frontend |
| Database | PostgreSQL | Videos, runs, detections, reports |
| XR / 3D | Python / ifcopenshell / Open3D | IFC → point cloud, coverage analysis |
| AI Pipeline | Python / OpenCV | Keyframe extraction, damage detection |

---

## 3. Prerequisites

### 3.1 Python 3.10

Download from [python.org](https://www.python.org/downloads/) and install with **"Add Python to PATH"** checked.

```powershell
python --version   # Python 3.10.x
```

### 3.2 Git

Download from [git-scm.com](https://git-scm.com/download/win).

```powershell
git --version
```

### 3.3 PostgreSQL 14 or newer

Download from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/).

During installation:
- Set a **superuser password** (you will need it in Step 2).
- Leave the default port **5432**.

```powershell
psql --version
```

If `psql` is not found, add `C:\Program Files\PostgreSQL\<version>\bin` to your system `PATH`.

---

## 4. Step 1 — Clone the Repository

```powershell
git clone https://github.com/RaijmakersKilian/FTP-AI.git
cd FTP-AI
```

---

## 5. Step 2 — PostgreSQL Database Setup

Open **pgAdmin 4** or a `psql` terminal as the `postgres` superuser and run:

```sql
CREATE USER ftpai_user WITH PASSWORD 'change_this_password';
CREATE DATABASE ftpai_db OWNER ftpai_user;
GRANT ALL PRIVILEGES ON DATABASE ftpai_db TO ftpai_user;
```

Then connect to the new database and create the schema:

```sql
\c ftpai_db

CREATE TABLE element_types (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    weight      FLOAT DEFAULT 1.0,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE videos (
    id           SERIAL PRIMARY KEY,
    filename     VARCHAR(255) NOT NULL,
    filepath     TEXT NOT NULL,
    uploaded_at  TIMESTAMP DEFAULT NOW(),
    file_size    BIGINT,
    status       VARCHAR(50) DEFAULT 'uploaded'
);

CREATE TABLE processing_runs (
    id               SERIAL PRIMARY KEY,
    video_id         INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    status           VARCHAR(50) DEFAULT 'pending',
    started_at       TIMESTAMP,
    completed_at     TIMESTAMP,
    config           JSONB,
    error_message    TEXT
);

CREATE TABLE detected_elements (
    id                 SERIAL PRIMARY KEY,
    processing_run_id  INTEGER REFERENCES processing_runs(id) ON DELETE CASCADE,
    element_type_id    INTEGER REFERENCES element_types(id),
    frame_number       INTEGER,
    confidence         FLOAT,
    bounding_box       JSONB,
    metadata           JSONB,
    detected_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE progress_reports (
    id                 SERIAL PRIMARY KEY,
    processing_run_id  INTEGER REFERENCES processing_runs(id) ON DELETE CASCADE,
    overall_score      FLOAT,
    section_scores     JSONB,
    element_scores     JSONB,
    generated_at       TIMESTAMP DEFAULT NOW()
);
```

---

## 6. Step 3 — Backend Setup

### 6.1 Install dependencies

```powershell
cd backend
pip install -r requirements.txt
```

> If you prefer an isolated environment:
> ```powershell
> python -m venv .venv
> .\.venv\Scripts\Activate.ps1
> pip install -r requirements.txt
> ```
> If PowerShell blocks scripts: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### 6.2 Configure environment variables

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in your database credentials:

```env
DATABASE_URL=postgresql+psycopg://ftpai_user:change_this_password@localhost:5432/ftpai_db
UPLOAD_DIR=storage/videos
REPORT_OUTPUT_DIR=storage/reports_pdf
```

### 6.3 Create storage folders

```powershell
New-Item -ItemType Directory -Force storage\videos
New-Item -ItemType Directory -Force storage\reports_pdf
```

---

## 7. Step 4 — Running the Application

Start the backend from the `backend/` folder:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Then open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

The dashboard loads automatically with:
- The **3D BIM point cloud** coloured by coverage (green / orange / red)
- The **Construction Inspector** showing coverage per bridge segment

> **Important:** always open the dashboard via `http://127.0.0.1:8000`, not via VS Code Live Server or by opening the HTML file directly. The 3D viewer and inspector fetch data from the backend API and will show 404 errors otherwise.

### What happens on startup

When the backend starts, it automatically checks whether the coverage result files (`coverage_result.ply` and `coverage_data.json`) exist in the `Frontend/` folder. If they are missing or outdated compared to the source point clouds, the coverage analysis runs in the background:

```
[startup] Coverage analysis started in background...
[startup] Coverage analysis complete — results loaded.
```

If the files are already up to date, the analysis is skipped:

```
[startup] Coverage results are up to date, analysis skipped.
```

---

## 8. Optional: AI Pipeline Setup

The AI pipeline processes drone videos into keyframes and detections.

### 8.1 Install the package

```powershell
cd AI
pip install -e ".[dev,ifc]"
```

### 8.2 Configure environment variables

```powershell
Copy-Item configs\.env.example .env
notepad .env
```

Minimum required:

```env
PYTHONPATH=src
```

### 8.3 Run the pipeline

```powershell
ftp-ai run-video `
  --video "path\to\drone_video.mp4" `
  --output "outputs\test_run" `
  --sample-every 10 `
  --segmenter classical
```

---

## 9. Optional: XR / 3D Processing Setup

These scripts convert an IFC BIM file to a point cloud and compute coverage against a drone reconstruction. **This step is only needed when you have new drone footage to analyse.**

### 9.1 Install dependencies

```powershell
cd XR\IFC-TO-Cloud
pip install ifcopenshell trimesh numpy open3d scipy
```

> If `pip install open3d` fails on Python 3.10, download the wheel from [github.com/isl-org/Open3D/releases](https://github.com/isl-org/Open3D/releases) and install it manually:
> ```powershell
> pip install open3d-<version>-cp310-cp310-win_amd64.whl
> ```

### 9.2 Add required files

Place the following files in `XR\IFC-TO-Cloud\`:

| File | Description | Size |
|------|-------------|------|
| `Full_Build_Bridge.ifc` | BIM model | ~135 MB |
| `mast3r_filtered.ply` | Filtered drone reconstruction | ~67 MB |

> These large files are excluded from git. Obtain them from the project's shared drive.

### 9.3 Convert IFC to point cloud (first time only)

```powershell
cd XR\IFC-TO-Cloud
python ifctocloud.py --ifc Full_Build_Bridge.ifc
```

This produces `ifc_cloud.ply`.

### 9.4 Run coverage analysis

```powershell
python coverage_analysis.py `
  --ifc ifc_cloud.ply `
  --mast3r mast3r_filtered.ply `
  --export-ply ..\..\Frontend\coverage_result.ply `
  --export-json ..\..\Frontend\coverage_data.json
```

The exported files are automatically picked up by the dashboard on the next backend start (or immediately via the browser refresh).

---

## 10. Optional: SAM3 Segmentation Model

SAM3 provides higher-quality damage segmentation using a transformer model.

**Requirements:** Python 3.12, NVIDIA GPU with ≥ 8 GB VRAM, CUDA 11.8+.

1. Accept the model license at [huggingface.co/facebook/sam3](https://huggingface.co/facebook/sam3).
2. Generate a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
3. Install PyTorch with CUDA:
   ```powershell
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```
4. Install SAM3:
   ```powershell
   pip install git+https://github.com/facebookresearch/segment-anything-3.git
   ```
5. Update `AI/.env`:
   ```env
   HF_TOKEN=hf_your_token_here
   SAM2_CHECKPOINT=models/sam2.1_hiera_tiny.pt
   SAM2_MODEL_CFG=configs/sam2.1/sam2.1_hiera_t.yaml
   ```
6. Run:
   ```powershell
   ftp-ai run-video --video <path> --output <path> --segmenter sam3
   ```

---

## 11. Folder Structure Reference

```
FTP-AI/
├── AI/                        # AI pipeline Python package
│   ├── src/ftp_ai/            # Source code
│   ├── configs/               # Config examples
│   └── requirements.txt
│
├── backend/                   # FastAPI backend
│   ├── app/
│   │   ├── main.py            # Entry point (runs coverage analysis on startup)
│   │   └── routers/           # /videos, /processing-runs, /api/coverage, etc.
│   ├── storage/
│   │   ├── videos/            # Uploaded drone videos
│   │   └── reports_pdf/       # Generated reports
│   ├── requirements.txt
│   └── .env.example
│
├── Frontend/                  # Web dashboard (served by the backend)
│   ├── Dashboard.html         # Main page
│   ├── Dashboard.css
│   ├── viewer.js              # Three.js 3D point cloud viewer
│   ├── inspector.js           # Construction Inspector panel
│   ├── thumbnails.js          # Video timeline UI
│   ├── coverage_result.ply    # Generated by XR pipeline (auto-loaded)
│   └── coverage_data.json     # Generated by XR pipeline (auto-loaded)
│
└── XR/IFC-TO-Cloud/           # 3D processing scripts
    ├── ifctocloud.py           # IFC → point cloud
    ├── coverage_analysis.py   # Coverage per bridge segment
    ├── coverage_per_type.py   # Coverage per element type
    ├── ifc_cloud.ply          # IFC point cloud (not in git)
    └── mast3r_filtered.ply    # Drone reconstruction (not in git)
```

---

## 12. Troubleshooting

**`psql: command not found`**
```powershell
$env:PATH += ";C:\Program Files\PostgreSQL\16\bin"
```

**PostgreSQL service not running**
```powershell
Start-Service -Name postgresql-x64-16
```

**`ModuleNotFoundError` after pip install**
```powershell
where python   # should point to the correct Python / venv
```

**Backend returns 500 on startup**
1. Check that `DATABASE_URL` in `backend\.env` is correct.
2. Confirm PostgreSQL is running.
3. Re-run the SQL schema from Step 2.

**3D viewer shows grey model instead of point cloud**
- Open the browser at `http://127.0.0.1:8000`, not via Live Server or a file path.
- Check the browser console (F12) — the PLY endpoint should return 200.
- Confirm `Frontend\coverage_result.ply` exists. If not, run the coverage analysis (Step 9.4).

**Construction Inspector is empty**
- Confirm `Frontend\coverage_data.json` exists.
- Open `http://127.0.0.1:8000/api/coverage/data` in your browser — it should return JSON.

**PowerShell script execution blocked**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**`pip install open3d` fails**
Download the pre-built wheel from [github.com/isl-org/Open3D/releases](https://github.com/isl-org/Open3D/releases) and install with `pip install <file>.whl`.

---

*FTP-AI · GOT Bridge Monitoring Platform · June 2026*
