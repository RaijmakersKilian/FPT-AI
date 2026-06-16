# Bridge Progress Monitor — AI Product & Research Report

Date: 2026-06-15
Branch: `ai-vslam-gaussian-splat-test`
Status: v0 / feasibility product — the full loop runs end to end on real client footage.

This is the single consolidating document for the AI side of the project. It
describes the product we have, the results, everything we tried (including what
did not work), the honest limitations, and the path from this v0 to a production
v1. The detailed per-experiment notes referenced throughout still live in their
own files in `AI/docs/`.

---

## 1. What it is (one paragraph)

**Bridge Progress Monitor turns a drone flyover into a construction-progress
report.** You give it a drone video of the bridge. It removes moving traffic,
rebuilds the current bridge in 3D, aligns that reconstruction onto the final
design model, and reports how much of the planned bridge is already built —
overall and section by section. Fly it again on another date and it plots the
progress curve over time. It also produces a 2D vision overlay that highlights
the active construction zone in the footage.

It is a **v0 feasibility product**: the entire pipeline works automatically on
real footage. What separates it from a production system is the quality and
repeatability of the input data, not the algorithms — that is the central
research finding, and it defines the v1 roadmap (Section 9).

---

## 2. The product: input, output, pipeline

**Input**
- A drone flyover video (`.mp4`).
- Once: the final bridge model — we use a GLB and a denser completed-bridge point
  cloud (`AI/data/BridgePointcloud/coverage_result.ply`, 500k points) as the
  comparison reference.

**Output (per flight)** — written to `AI/outputs/runs/<name>/`
- `REPORT.md` + `manifest.json` — the numbers.
- A cleaned 3D point cloud of the current bridge.
- An overall **built %** and a **per-section built %** (default 10 sections).
- A **likely-non-bridge %** (scan noise / trees / traffic estimate).
- (Full mode only) a construction-zone vision overlay video.

**Output (across flights)**
- `AI/outputs/runs/progress_over_time.md` + `.png` — the progress curve.
- `AI/outputs/runs/INDEX.md` — one row per flight, linking each report.

**Pipeline stages** (one named system)

| Stage | Does | Component |
|---|---|---|
| 1. Ingest | Read the drone video | `AI/scripts/run_bridge_ai_pipeline.py` |
| 2. Clean (2D) | SAM3 masks moving traffic/people out of the frames | `AI/scripts/mask_dynamic_objects.py` |
| 3. Reconstruct | MASt3R-SLAM builds a 3D point cloud + camera path | WSL `run_mast3r_*` |
| 4. Clean (3D) | Remove hallucinated/black points + statistical-outlier noise | `remove_black_points.py`, `clean_pointcloud.py` |
| 5. Align & measure | PCA + trimmed ICP fit to the final model; per-section built % | `AI/src/ftp_ai/model_comparison.py` |
| 6. Report | Per-flight report; batch → progress curve | `run_all_videos.py` |
| (B) Vision overlay | SAM3 isolates the construction zone across the whole flyover | `construction_overlay_video.py` |

**One front door**

```powershell
# one flight
$env:PYTHONPATH="AI/src"
AI\.venv-sam3\Scripts\python.exe AI\scripts\run_bridge_ai_pipeline.py --video <video> --final-model <model>

# all flights in a folder -> INDEX.md + progress_over_time
AI\.venv-sam3\Scripts\python.exe AI\scripts\run_all_videos.py --video-dir AI\data\raw --final-model <model>
```

---

## 3. What we have now (concrete deliverables)

```text
- An automatic video -> progress-report pipeline (one command).            [DONE]
- A batch runner that produces a progress-over-time curve across dates.     [DONE]
- 11 processed flights with per-section built % (see Section 4).            [DONE]
- A 3D current-vs-final comparison with ICP alignment + per-section split.  [DONE]
- A 2D construction-zone vision overlay track.                              [DONE, BridgeVid1]
- A documented output contract for the frontend team.                       [DONE]  (ai_output_contract.md)
- A full research ledger of methods tried (Section 6).                      [DONE]
```

---

## 4. Coverage — which videos, processed to what depth

We have **12 source videos** (10 dated + BridgeVid1 + Bridgevid2, the last two
both 27/12/2023). Honest processing state:

Updated 2026-06-16 after the masked re-run. The 04/03 == 20/03 duplicate was
dropped (its video moved to `AI/data/raw/_excluded_duplicate/`).

| Video / date | 3D progress track | Traffic masking | Vision overlay | Notes |
|---|---|---|---|---|
| BridgeVid1 (27/12/2023) | yes | yes | yes | the only run with the vision overlay |
| Bridgevid2 (27/12/2023) | yes (fast) | no | no | same date as BridgeVid1; not a new curve point |
| 18/11/2023 | yes | **yes** | no | masked re-run |
| 12/01/2024 | yes | **yes** | no | masked re-run |
| 13/02/2024 | yes | **yes** | no | masked re-run |
| 04/03/2024 | yes | **yes** | no | masked re-run |
| 19/03/2024 | yes | **yes** | no | masked re-run |
| 16/06/2024 | yes | **yes** | no | masked re-run |
| 06/07/2024 | yes | **yes** | no | masked re-run |
| 20/08/2024 | yes | **yes** | no | masked re-run |
| 23/10/2024 | yes | **yes** | no | masked re-run |

**Summary:** every distinct video now has the 3D progress track. The 9 dated
videos were re-run with **SAM3 traffic masking** (masked re-run, 2026-06-16);
they still skip the vision overlay (masking-only mode was chosen to get the
cleaner clouds without the ~2x SAM3 cost). The **vision overlay** exists for
BridgeVid1 only. Bridgevid2 (same date as BridgeVid1) was processed fast-mode
for completeness. Effective distinct dates for the curve: **9 + BridgeVid1**.

Remaining if a fully-uniform dataset is wanted: add the vision overlay to the
dated runs (Section 10).

---

## 5. Results

### Progress over time (built % = fraction of final-model points with as-built evidence)

These numbers are from the **masked** re-run (2026-06-16): every dated video went
through SAM3 traffic masking -> SLAM -> clean -> compare. The 04/03 duplicate is
dropped, so the curve is 9 distinct dates + BridgeVid1.

| Date | Built % | Strict built % | Non-bridge % |
|---|---|---|---|
| 2023-11-18 | 85.32 | 64.79 | 3.24 |
| 2023-12-27 (BridgeVid1) | 82.40 | 68.76 | 2.43 |
| 2024-01-12 | 88.53 | 73.50 | 4.27 |
| 2024-02-13 | 73.88 | 63.35 | 4.58 |
| 2024-03-04 | 75.19 | 64.32 | 13.04 |
| 2024-03-19 | 62.93 | 51.67 | 8.39 |
| 2024-06-16 | 75.71 | 63.41 | 0.21 |
| 2024-07-06 | 75.75 | 65.23 | 5.04 |
| 2024-08-20 | 94.10 | 80.92 | 3.59 |
| 2024-10-23 | 72.51 | 62.56 | 6.97 |

### Per-section example (2024-08-20, the strongest flight)

10 sections along the bridge axis read 75-100% built, demonstrating the system
distinguishes well-covered spans from weakly-covered ones.

### Did SAM3 traffic masking improve the dated results? (honest finding)

Barely. Comparing the earlier fast-mode runs to the masked re-run, built %
shifted by only **-3.9 to +2.4 points**, mixed in direction (some up, some
down) — within the noise of the scale-normalized alignment. Reason: these are
high-altitude aerial flyovers where traffic is a small fraction of the frame
(SAM3 masked only **1.6-5.6%** of pixels), so removing it changes little. The
bigger masking gain seen earlier on the low, oblique BridgeVid1 footage
(`dynamic_masking_experiment.md`) did **not** generalise to the aerial dated
videos. Value delivered by the re-run: a single, consistently-processed,
defensible dataset across all dates — not a quality leap. Masking earns its keep
on low/oblique footage with heavy in-frame traffic, not on high aerial passes.

### Alignment quality

```text
ICP refinement improved MASt3R-vs-final median distance 0.02386 -> 0.01384 and
close coverage 68.6% -> 76.59%. Against the denser completed-bridge point cloud,
82.28% of model points had as-built evidence (MASt3R) vs 56.2% (COLMAP), with
uncovered bridge ends correctly reading 0%.
```

**Critical reading of the curve (must say this out loud):** these videos are all
of a **largely-complete bridge**, so the built % primarily measures *how much of
the bridge each flight reconstructed*, i.e. **coverage**, not month-to-month
construction. The curve is not monotonic because dips track weaker
reconstructions (more traffic, faster motion, a reversed return pass), not
demolition. The number is honest proof that *per-section current-vs-final
comparison works*; it is **not** a survey-grade progress measurement yet.

---

## 6. Research ledger — everything we tried

### What worked (kept)

| Method | Role | Result |
|---|---|---|
| MASt3R-SLAM (vSLAM) | main 3D reconstruction | dense cloud (up to 3.2M pts); best on imperfect drone video |
| SAM3 traffic masking *before* SLAM | production pre-cleaning | +keyframes, fewer non-bridge points, better comparison |
| Current-vs-final comparison + ICP + per-section | the progress measurement | distinguishes built vs missing sections — strongest evidence |
| COLMAP photogrammetry | reconstruction on good-overlap segments | produced an actual mesh (32 frames, 25k sparse pts) |
| SAM3 progress prompts | simple visual demo | named progress classes on cropped ROI |
| SAM2 automatic masks | "segment everything" research | dense unlabeled regions for discovery |
| Construction-zone vision overlay (Track B) | per-frame demo next to the model | isolates active construction (gantry/pier/cranes) |

### What did not work / was parked

| Method | Why it failed / was parked |
|---|---|
| Classical OpenCV segmentation | no construction understanding; noisy — fallback only |
| SAM3 object prompts (many classes) | crowded, prompt-limited, mislabels |
| Geometric 3D bridge crop | unsupervised alignment too imprecise — **parked** (`bridge_isolation_testing.md`) |
| SAM mask-lifting onto the 3D cloud (2026-06-15) | works, but SAM latches onto the **road surface**, so isolation is demo-grade (`sam_pointcloud_lifting_testing.md`) |
| Video → Gaussian Splat (Nerfstudio/Splatfacto) | pipeline proven, but COLMAP registered only ~8 poses → poor quality |
| Panorama stitching | drone fly-over has parallax — does not behave like a phone panorama |
| Two-view SIFT prototype | sparse points only, arbitrary scale |
| Treating casual video as planned photogrammetry | unreliable registration; the core data-quality lesson |

Full method-by-method detail: `AI/docs/method_comparison_table.md`,
`AI/docs/vision_comparison_testing.md`, `AI/docs/nerfstudio_splatfacto_testing.md`,
`AI/docs/dynamic_masking_experiment.md`, `AI/docs/slam_drift_finding.md`,
`AI/docs/sam_pointcloud_lifting_testing.md`.

---

## 7. The headline research finding

```text
The hardest part is not picking an AI model. Every model we tried can produce a
useful prototype. The limiting factor is repeatable, high-quality drone data
that can be reconstructed and aligned to the final model. Reconstruction and
segmentation only become reliable when the capture is planned: a fixed flight
path, consistent heading, calibration, and ideally GPS/IMU or control points.
```

Two concrete sub-findings from this work:
- **Masking moving traffic before reconstruction measurably improves the cloud**
  — this is segmentation's real production role on the 3D side (pre-cleaning).
- **Out-and-back flights with a reversed return pass break loop closure**, which
  bends the reconstruction at junctions; consistent-heading flights would fix it
  (`slam_drift_finding.md`).

---

## 8. Limitations (honest)

```text
- Scale is normalized, not metric. Without GPS/IMU or camera calibration we
  cannot report distances in real units.
- "Built %" on a completed bridge measures coverage, not progress over time.
- Junction / reversed-return-pass geometry fuses poorly.
- Open-vocabulary SAM3 is a demo, not a certified construction detector.
- The final model is one undivided shape; "sections" are geometric slices, not
  real named bridge components/phases.
- One date is a duplicate and one video is unprocessed (Section 4).
```

---

## 9. From v0 to v1 — production roadmap

What a real implementation team would change, in priority order:

1. **Plan the capture.** Fixed, repeatable flight path: same route, altitude,
   angle, speed, heading, start/end points; high overlap; consistent lighting.
2. **Add metadata.** GPS/IMU + camera intrinsics → metric scale and
   coordinate-based alignment instead of fragile visual fitting.
3. **Add control points / markers** on site for survey-grade registration.
4. **Section the final model.** Split the BIM/IFC into named components/phases so
   per-section progress maps to real deliverables and a schedule.
5. **Train a project-specific bridge/element segmenter** to replace open-vocab
   SAM3 for reliable isolation and classification.
6. **Use LiDAR if available** as a stronger geometry source / alignment reference.
7. Then "built %" becomes true progress: compare as-built geometry against the
   planned component set and the construction schedule.

---

## 10. What we would still do this week (optional)

```text
- Process Bridgevid2 (the one unprocessed video).
- Drop the 04/03 == 20/03 duplicate so the curve has 9 honest dates.
- Optionally re-run the dated videos in full mode (masking + vision) for a
  consistent, complete dataset rather than fast-mode 3D only.
- Package per-flight REPORT.md into a client-facing report + a dashboard page
  built on the progress curve (the "feels like a product" layer).
```

---

## 11. What we need from the client

```text
1. Final bridge model: BIM / IFC / GLB / OBJ / Revit export (have: a GLB + a
   completed-bridge point cloud).
2. Any LiDAR scans (.las/.laz/.e57/.ply/.pcd).
3. Drone metadata: GPS, IMU, camera intrinsics/calibration, flight logs.
4. Ability to fly a fixed, repeatable path in future inspections.
5. Planned high-overlap photo capture, not only casual video.
6. Bridge sections/phases they care about (deck, columns, formwork, ramps, ...).
7. Their definition of completed / in-progress / not-started.
8. A section plan or construction schedule linked to the final model.
```

---

## 12. Artifact map

```text
Product / orchestration
  AI/scripts/run_bridge_ai_pipeline.py     one video -> runs/<name>/REPORT.md
  AI/scripts/run_all_videos.py             batch -> INDEX.md + progress_over_time
  AI/docs/pipeline_usage.md                usage
  AI/docs/ai_output_contract.md            frontend handoff contract

Results
  AI/outputs/runs/<date>/                  per-flight: 02_slam 03_clean 04_comparison REPORT manifest
  AI/outputs/runs/bridgevid1_full/         the one full run (adds 01_frames 05_vision)
  AI/outputs/runs/progress_over_time.md/.png
  AI/outputs/runs/INDEX.md

Reference model
  AI/data/BridgePointcloud/coverage_result.ply   completed-bridge point cloud (500k)

Key research docs
  AI/docs/method_comparison_table.md
  AI/docs/dynamic_masking_experiment.md
  AI/docs/slam_drift_finding.md
  AI/docs/vision_comparison_testing.md
  AI/docs/sam_pointcloud_lifting_testing.md
  AI/docs/interim_ai_brief.md
  AI/docs/ai_handoff_for_claude.md
```
