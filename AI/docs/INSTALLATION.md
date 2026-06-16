# Installation Manual — Bridge Progress Monitor (AI Module)

Date: 2026-06-16

This manual sets up the AI module so you can run the pipeline:
**drone video → 3D reconstruction → comparison with the final model → progress report.**

It is honest about being research-grade software: there are **two** environments,
because the 3D reconstruction (MASt3R-SLAM) only builds on Linux/CUDA while the
rest (SAM3 segmentation, point-cloud work, comparison) runs on Windows.

```text
ENV A  Windows  AI/.venv-sam3            SAM3 masking + vision + cleaning + comparison + handoff
ENV B  WSL/Linux  /opt/mast3r-slam-env   MASt3R-SLAM 3D reconstruction (CUDA build)
```

The pipeline orchestrator (`AI/scripts/run_bridge_ai_pipeline.py`) runs on Windows
and calls into WSL automatically for the reconstruction step, so once both
environments exist you only ever run one command.

---

## 0. Hardware & OS prerequisites

```text
- Windows 11 with an NVIDIA GPU (CUDA-capable). Tested on a laptop RTX GPU.
- ~30 GB free disk: ~3 GB model checkpoints + multi-GB frame/point-cloud outputs.
- NVIDIA driver new enough for CUDA 12.x.
- A Hugging Face account (SAM3 checkpoints are gated).
- Internet access for the model downloads.
```

---

## 1. ENV A — Windows (SAM3 + 3D tooling)

Tested versions: **Python 3.12.6**, **torch 2.10.0+cu128**, **open3d 0.19**.

```powershell
# from the repo root
cd AI
py -3.12 -m venv .venv-sam3
.\.venv-sam3\Scripts\Activate.ps1
python -m pip install --upgrade pip

# core deps
pip install -r requirements.txt
pip install open3d            # used by the cleaning / comparison / handoff scripts

# GPU PyTorch (CUDA 12.8 build)
pip install torch==2.10.0 torchvision --index-url https://download.pytorch.org/whl/cu128
```

### SAM3 (Meta, gated checkpoints)

```powershell
# clone SAM3 next to the project's external deps and install editable
git clone https://github.com/facebookresearch/sam3.git .external\sam3
pip install -e .external\sam3

# authenticate to Hugging Face so SAM3 can pull its checkpoints
huggingface-cli login          # paste a token with SAM3 access accepted
```

Verify ENV A:

```powershell
.\.venv-sam3\Scripts\python.exe -c "import torch, sam3, open3d, cv2, trimesh, scipy; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
# expect: torch 2.10.0+cu128 cuda True
```

---

## 2. ENV B — WSL Ubuntu (MASt3R-SLAM reconstruction)

Tested versions: **Ubuntu-24.04**, **Python 3.12.3**, **torch 2.5.1+cu121**,
**CUDA toolkit 12.6** (the SLAM CUDA extensions need a real toolkit to compile).

### 2.1 Install WSL + Ubuntu

```powershell
wsl --install -d Ubuntu-24.04        # reboot if prompted, then set a user
```

### 2.2 CUDA toolkit inside WSL

Install the NVIDIA **CUDA Toolkit 12.6** for WSL-Ubuntu (follow NVIDIA's official
WSL CUDA guide). It lands at `/usr/local/cuda-12.6`. The MASt3R-SLAM build needs it:

```bash
export CUDA_HOME=/usr/local/cuda-12.6
export PATH=$CUDA_HOME/bin:$PATH
nvcc --version          # must work before building MASt3R-SLAM
```

> The single most common install failure is `CUDA_HOME environment variable is not
> set` during the MASt3R-SLAM build. Export it as above before `pip install`.

### 2.3 Python env + PyTorch

```bash
sudo python3 -m venv /opt/mast3r-slam-env
/opt/mast3r-slam-env/bin/pip install --upgrade pip
/opt/mast3r-slam-env/bin/pip install torch==2.5.1 torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 2.4 Build MASt3R-SLAM

The repo is vendored at `AI/.external/MASt3R-SLAM`. Build it with ENV B's python
(follow the upstream README at https://github.com/rmurai0610/MASt3R-SLAM for the
exact submodule/extension steps; on Windows use its `windows` branch via WSL):

```bash
cd "/mnt/c/Users/<you>/.../FTP-AI/AI/.external/MASt3R-SLAM"
CUDA_HOME=/usr/local/cuda-12.6 /opt/mast3r-slam-env/bin/pip install -e .
# (this compiles the CUDA backend -> mast3r_slam_backends*.so)
```

### 2.5 Download the checkpoints

Place these in `AI/.external/MASt3R-SLAM/checkpoints/` (from the MASt3R / naver
model release linked in the upstream README):

```text
MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth                  (~2.75 GB)
MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric_retrieval_codebook.pkl (~268 MB)
MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric_retrieval_trainingfree.pth (~8 MB)
```

Verify ENV B:

```powershell
# from Windows PowerShell
wsl -d Ubuntu-24.04 -u root /opt/mast3r-slam-env/bin/python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
# expect: torch 2.5.1+cu121 cuda True
```

---

## 3. Run it

One command does the whole pipeline (run from Windows in ENV A):

```powershell
$env:PYTHONPATH="AI/src"
AI\.venv-sam3\Scripts\python.exe AI\scripts\run_bridge_ai_pipeline.py `
  --video AI\data\raw\<your_video>.mp4 `
  --final-model AI\data\BridgePointcloud\coverage_result.ply `
  --name <run_name>
```

Output lands in `AI/outputs/runs/<run_name>/` (`REPORT.md`, `manifest.json`,
the cleaned 3D cloud, and the per-section comparison). Batch a whole folder with
`AI/scripts/run_all_videos.py`. See `AI/docs/pipeline_usage.md` for all options.

---

## 4. Known pitfalls (read this)

```text
- Shell scripts must be LF, not CRLF. A git checkout on Windows can re-apply
  CRLF and break the .sh files with "set: pipefail: invalid option name".
  Fixed by the repo .gitattributes (*.sh text eol=lf); if it recurs run
  `sed -i 's/\r$//' AI/scripts/*.sh` inside WSL.
- Paths contain spaces ("Howest 2025-2026 ..."). Always quote paths. For heavy
  Nerfstudio/COLMAP work the upstream tools dislike spaces - use a no-space work
  dir like /opt/ftp_ai_ns_bridge1 (see nerfstudio_splatfacto_testing.md).
- Call WSL from PowerShell, not Git Bash: Git Bash mangles /mnt/c/... paths.
- CUDA_HOME must be set when building MASt3R-SLAM (Section 2.2).
- Long batch runs: stop the machine from sleeping or the WSL job dies mid-run.
- SAM3 inference resolution is fixed at 1008 (its RoPE table); do not change it.
```

---

## 5. What each environment is responsible for

```text
ENV A (Windows .venv-sam3):
  mask_dynamic_objects.py / mask_keep_construction.py  SAM3 masking
  segment_bridge_frame.py / construction_overlay_video.py  vision track
  remove_black_points.py / clean_pointcloud.py         point-cloud cleaning
  src/ftp_ai/model_comparison.py                       align + per-section compare
  collect_handoff.py / progress_over_time.py           deliverables

ENV B (WSL /opt/mast3r-slam-env):
  AI/.external/MASt3R-SLAM (main.py via run_mast3r_bridge1_*.sh)  3D reconstruction
```

For the full method background and limits, see
`AI/docs/bridge_progress_monitor_report.md`.
