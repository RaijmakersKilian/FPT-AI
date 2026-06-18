# Bridge Progress Monitor — Client Summary (AI Module)

Prepared for: FPT AI · GOT Bridge progress monitoring · 2026-06-16

## What it does

Give it a drone video of the bridge. It rebuilds the current bridge in 3D,
aligns that reconstruction onto the final design model, and reports how much of
the planned bridge is already built — overall and section by section. Run it on
videos from different dates and it shows the progress curve over time.

## What you receive

```text
1. Software   - a one-command pipeline (video -> progress report) + all source.
2. Data       - per-date 3D reconstructions, "built %" per section, and a
                progress-over-time curve, plus browser-ready clouds for the web app.
3. Findings   - a feasibility report: what works, what doesn't, and exactly what
                data capture is needed to make it production-grade.
4. Install    - a step-by-step installation manual (INSTALLATION.md).
```

## Results so far

- Processed **9 dated flights (Nov 2023 – Oct 2024)** plus the original footage.
- Each flight: a 3D point cloud, an overall built %, and a 10-section breakdown.
- A progress-over-time curve across all dates (`progress_over_time.png`).
- A vision track that isolates the active construction between the roads.

## Honest verdict

- **As a turnkey, survey-grade product from the current footage — not yet.**
  Casual top-view video without camera pose/calibration cannot give reliable,
  calibrated per-component numbers today.
- **As a proven method — yes.** The full loop works end to end and is documented.

**The limiting factor is the data capture, not the AI.** Every approach we tested
hit the same wall: no known drone position, no GPS/IMU, no calibration, no
repeatable flight path. The AI consistently did its job; the input data is what
holds back accuracy.

## What would make it production-grade

```text
1. Planned, repeatable drone flights (fixed path, altitude, angle, multi-pass).
2. Drone position per frame (Unity-planned path and/or GPS/IMU).
3. Camera calibration (known intrinsics) for real-world scale.
4. The final BIM/IFC model split into named components/phases.
5. A bridge-specific trained detector (vs. today's open-vocabulary prompts).
```

With those, the same pipeline produces reliable per-section progress.

## How to install and run

See **INSTALLATION.md** (two environments: a Windows GPU env for segmentation and
comparison, and a WSL/Linux env for the 3D reconstruction). After setup, one
command processes a video:

```powershell
AI\.venv-sam3\Scripts\python.exe AI\scripts\run_bridge_ai_pipeline.py `
  --video <video.mp4> --final-model <final_model.ply> --name <run_name>
```

## Where the details live

```text
INSTALLATION.md                         full setup manual
bridge_progress_monitor_report.md       complete method + results + limits + roadmap
progress_over_time.png / .md            the progress curve across dates
handoff_plys/                           per-date 3D clouds + comparison JSON for the web app
```
