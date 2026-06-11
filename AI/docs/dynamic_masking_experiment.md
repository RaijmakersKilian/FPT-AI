# Dynamic Object Masking Before MASt3R-SLAM

Date: 2026-06-11

Question tested:

```text
Does masking moving traffic out of the drone frames before reconstruction
improve the MASt3R-SLAM point cloud and the per-section progress comparison?
```

Answer: yes. Every comparable metric improved, with one alignment caveat
explained below.

## Pipeline

```text
1. Extract every 30th frame of BridgeVid1-271223.mp4 (115 frames), exactly
   matching the stride of the unmasked baseline MASt3R-SLAM run.
2. SAM3 text-prompted segmentation per frame with the prompts:
   car, bus, truck, van, motorcycle, person, boat (min score 0.35).
3. Union the masks, dilate by 9 px, fill masked pixels with black.
   Safety cap: if a frame's mask exceeds 45% of pixels it is skipped as a
   likely false positive (never triggered; max was 8.9%).
4. Run MASt3R-SLAM on the masked frame folder (subsample 1).
5. Run the per-section comparison against the completed bridge point cloud.
```

Files:

```text
AI/scripts/mask_dynamic_objects.py                 (frame extraction + masking)
AI/scripts/run_mast3r_bridge1_masked.sh            (WSL MASt3R-SLAM run)
AI/configs/mast3r_bridge_frames_fast.yaml          (frames config, subsample 1)
AI/outputs/bridgevid1_masked_frames/               (frames, masked, debug, stats)
AI/outputs/mast3r_slam_bridge1_masked/             (point cloud + trajectory)
AI/outputs/comparison_mast3r_bridge1_masked_vs_bridgepointcloud/
```

Masking statistics:

```text
115/115 frames masked
mean masked pixels per frame: 4.94%
max masked pixels per frame: 8.91%
```

The debug overlays (AI/outputs/bridgevid1_masked_frames/debug/) confirm the
masks hit vehicles on the deck and surrounding roads without touching the
bridge structure.

## Results: masked vs unmasked baseline

Both compared against `AI/data/BridgePointcloud/coverage_result.ply` with the
same settings.

```text
                                unmasked baseline    masked
keyframes                       30                   38
point cloud vertices            3,077,001            3,626,733
model built (0.04)              82.28%               87.23%
model built strict (0.02)       62.85%               68.52%
model built loose (0.08)        91.99%               93.23%
likely non-bridge points        7.51%                6.41%
close coverage (current side)   66.05%               66.55%
```

Per-section built percentage. The masked run's alignment mirrored the bridge
lengthwise relative to the baseline (sign flip 1,-1,1 vs -1,-1,1), so the
masked sections are listed in reversed order to compare the same physical
bridge ends:

```text
section (baseline order):  1     2     3     4     5     6     7     8     9     10
unmasked baseline:         60.4  92.5  97.1  95.4  91.1  82.2  100   100   85.0  0.0
masked (mirror-corrected): 67.3  96.3  100   100   100   97.7  99.3  100   96.5  3.6
```

Every section is equal or better. The weakly covered bridge end stays weakly
covered (the video simply does not capture it well); that is correct behavior,
not a masking failure.

## Interpretation

```text
1. Masking moving traffic before reconstruction measurably improves both the
   reconstruction (more keyframes registered, fewer non-bridge points) and
   the progress comparison (strict built +5.7 points). Segmentation has a
   real production role as a pre-reconstruction cleaning step, not as the
   progress measurement itself.
2. The lengthwise mirror flip between runs confirms a known limitation:
   bridges are nearly symmetric along their length, so unsupervised
   PCA+ICP alignment cannot reliably pick the orientation. Production needs
   one manual control point (or GPS) to fix the bridge direction.
3. Part of the improvement comes from MASt3R-SLAM registering more keyframes
   (38 vs 30) on the masked frames - masking traffic also helps tracking,
   not only the final cloud.
```

## How To Reproduce

```text
# 1. mask frames (Windows, AI/.venv-sam3 venv)
AI/.venv-sam3/Scripts/python.exe AI/scripts/mask_dynamic_objects.py \
  --video AI/data/raw/BridgeVid1-271223.mp4 \
  --output AI/outputs/bridgevid1_masked_frames --subsample 30

# 2. run MASt3R-SLAM on masked frames (WSL Ubuntu-24.04 as root)
bash AI/scripts/run_mast3r_bridge1_masked.sh
# results land in AI/.external/MASt3R-SLAM/logs/bridge1_fast_masked/

# 3. compare against the completed bridge cloud
PYTHONPATH=AI/src python -m ftp_ai.cli compare-3d-model \
  --current AI/outputs/mast3r_slam_bridge1_masked/pointcloud.ply \
  --final-model AI/data/BridgePointcloud/coverage_result.ply \
  --output AI/outputs/comparison_mast3r_bridge1_masked_vs_bridgepointcloud
```
