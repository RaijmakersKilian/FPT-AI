# Running SAM on the 3D: 2D mask lifting onto the MASt3R-SLAM cloud

Date: 2026-06-15

Branch: `ai-vslam-gaussian-splat-test`

## The idea

"What if we run SAM on the 3D from MASt3R-SLAM?" SAM is a 2D image model, so it
cannot segment a point cloud directly. Instead we **lift** SAM's 2D masks into
3D: project the fused SLAM cloud back into each keyframe, segment the keyframe
with SAM3 ("bridge" prompts), and vote each 3D point bridge / not-bridge by the
masks it lands in. The output is a semantically isolated bridge-only cloud.

This is the *semantic* version of bridge isolation. It is deliberately different
from the geometric crop parked in `bridge_isolation_testing.md` (that one failed
because unsupervised alignment was imprecise). Here the bridge is identified by
what it *looks like* in the images, not by where it sits in space.

## Why it was feasible without re-running SLAM

The existing run already saved everything needed:

```text
- fused cloud       AI/outputs/mast3r_slam_bridge1_fast/pointcloud.ply (3,077,001 pts)
- trajectory        AI/outputs/mast3r_slam_bridge1_fast/trajectory.txt
                    (TUM: ts tx ty tz qx qy qz qw, T_WC = camera->world, OpenCV frame)
- keyframe images   AI/.external/MASt3R-SLAM/logs/bridge1_fast/keyframes/BridgeVid1-271223/<ts>.png
```

The keyframe PNGs are named by the **same timestamp** as the trajectory rows, so
each image pairs exactly with its pose. No frame-mapping guesswork.

## The one snag: no stored focal

MASt3R-SLAM ran with `use_calib: False`, so it never stored a pinhole focal -
the points come straight from MASt3R's pointmap regression. We recover an
approximate focal by rendering the cloud into each keyframe (painter's z-buffer)
and minimising colour error against the real keyframe image.

Result: a clean, unambiguous minimum, which also proves the projection
convention (pose handedness, OpenCV camera frame, centred principal point) is
correct - a wrong convention gives no basin.

```text
focal  mean colour error (/255)
150    53.9
300    41.1
344    27.4   <- minimum (~73 deg horizontal FOV on the 512x288 keyframes)
400    44.3
600    66.2
900    71.4
```

Sanity images: `AI/outputs/sam_lift_bridge1/debug/focal_check_*.png`
(left = real keyframe, right = cloud reprojected at focal 344).

## Method (script)

```text
AI/scripts/sam_lift_to_pointcloud.py
```

1. Load cloud (3.08M pts) + the 30 keyframe (image, pose) pairs.
2. Fit focal (above), or pass `--focal`.
3. For each keyframe:
   - SAM3 segment with bridge prompts ("bridge", "bridge deck", "concrete bridge
     structure", "elevated road", "bridge pier column") -> union mask.
   - Project every 3D point into the keyframe; build a painter's depth buffer and
     keep only points that pass a visibility z-test (`--occlusion-tol 0.06`) so
     background points behind the deck do not steal bridge votes.
   - Vote: each visible point gets +1 view, and +1 bridge vote if it lands in the
     mask.
4. Keep a point if it was seen in `>= --min-views` (2) keyframes and `>=
   --vote-threshold` (0.5) of those views called it bridge.

Run (Windows `AI/.venv-sam3`):

```powershell
$env:PYTHONPATH="AI/src"
AI\.venv-sam3\Scripts\python.exe AI\scripts\sam_lift_to_pointcloud.py `
  --cloud AI\outputs\mast3r_slam_bridge1_fast\pointcloud.ply `
  --keyframes-dir AI\.external\MASt3R-SLAM\logs\bridge1_fast\keyframes\BridgeVid1-271223 `
  --trajectory AI\outputs\mast3r_slam_bridge1_fast\trajectory.txt `
  --output AI\outputs\sam_lift_bridge1 --focal 344
```

## Result

```text
points total            3,077,001
points seen (>=2 views)  2,580,790
points kept as bridge      267,840   (8.7% of the cloud)
mean SAM bridge mask        8.2% of each keyframe
```

Outputs:

```text
AI/outputs/sam_lift_bridge1/pointcloud_sam_bridge.ply   (bridge-only, 267,840 pts)
AI/outputs/sam_lift_bridge1/pointcloud_removed.ply      (everything dropped)
AI/outputs/sam_lift_bridge1/topdown_before_after.png    (the key figure)
AI/outputs/sam_lift_bridge1/debug/mask_*.png            (SAM mask overlays)
AI/outputs/sam_lift_bridge1/sam_lift_summary.json
```

The before/after top-down is the headline: in the full SLAM cloud the bridge is a
coherent linear strip buried inside a feathery splay of trees, buildings and
ground; after lifting, that strip survives and the surroundings are stripped out.
The isolated structure stays connected end to end (deck + the connecting road),
which is the right shape.

## Honest limitations

```text
- Demo-grade, not survey-grade. The focal is recovered, not measured; MASt3R
  pointmaps are only approximately pinhole, so reprojection has some error.
- Conservative: 8.7% kept is slightly under-inclusive at deck edges (occlusion
  z-test + 0.5 vote threshold). Loosening --vote-threshold / --occlusion-tol
  keeps more but lets in more noise.
- SAM3 open-vocabulary prompts are a demo, not a certified detector; a project-
  trained bridge segmenter would make this reliable.
- The connecting-road / junction caveats from slam_drift_finding.md still apply.
```

## Why this matters / next step

This gives segmentation a concrete production role on the 3D side: **semantic
pre-cleaning of the reconstruction**, isolating the bridge where geometric
cropping could not. The obvious follow-up is to feed `pointcloud_sam_bridge.ply`
into `model_comparison.py` and check whether removing the non-bridge splay
improves alignment and lowers the "non-bridge %" against the final model. It also
generalises: the same script runs on any dated run that kept its keyframes
(`AI/.external/MASt3R-SLAM/logs/pipeline_<date>/keyframes/...`).

See also: [[ftp-ai-environment-quirks]].
```text
related docs: dynamic_masking_experiment.md (2D masking BEFORE SLAM),
              bridge_isolation_testing.md (the parked geometric crop),
              slam_drift_finding.md (junction / return-pass caveats)
```
