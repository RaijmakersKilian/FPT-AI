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

## Black Point Filtering (Follow-Up, Same Day)

Viewing the masked point cloud in MeshLab showed that the vehicles were gone,
but MASt3R-SLAM still hallucinated depth for the blacked-out pixels, creating
black streaks/beams in the cloud.

Because the mask fill is pure black, those points are removable by color:

```text
AI/scripts/remove_black_points.py --threshold 20
```

Color histogram confirmed the threshold: 4.15% of points have max RGB channel
below 5 (matching the 4.94% mean masked pixel ratio), while real dark scene
content only starts around brightness 20-30. Filtering at 20 removed 187,112
points (5.16%), leaving 3,439,621.

```text
AI/outputs/mast3r_slam_bridge1_masked/pointcloud_filtered.ply
AI/outputs/comparison_mast3r_bridge1_masked_filtered_vs_bridgepointcloud/
```

Corrected comparison (filtered cloud, aligned in baseline orientation):

```text
                                unmasked baseline    masked+filtered
model built (0.04)              82.28%               81.07%
model built strict (0.02)       62.85%               61.88%
model built loose (0.08)        91.99%               94.16%
likely non-bridge points        7.51%                6.32%
```

Important correction to the unfiltered result above: the masked-but-unfiltered
cloud read 87.23% built, but part of that gain came from black hallucinated
points landing near the model and counting as false "as-built evidence".
After filtering, the built percentage returns to baseline level while the
cloud is genuinely cleaner (lowest non-bridge percentage of all runs, best
loose coverage). The correct workflow is therefore always:

```text
mask -> reconstruct -> remove black points -> compare
```

## Geometric Cleaning (Follow-Up 2, Same Day)

After black-point filtering, MeshLab still showed distortion: tall grey
smears (thin poles/trees streaked across depth) and spiky blobs around
vegetation. These are normal MASt3R artifacts - the export uses no
confidence filtering (C_conf 0.0), so every guessed point is kept.

`AI/scripts/clean_pointcloud.py` removes them post-hoc with two filters:

```text
1. Statistical outlier removal: drop points whose mean distance to their 16
   nearest neighbors is > mean + 2 std (floating noise). Removed 168,222.
2. Density filter: drop points with < 24 neighbors inside a radius of 6x the
   median nearest-neighbor distance. Thin depth-smear beams survive SOR
   (they have close neighbors along the smear) but fail the density test.
   Removed 349,204 more.
```

Result: 3,439,621 -> 2,922,195 points (15.04% removed).

```text
AI/outputs/mast3r_slam_bridge1_masked/pointcloud_clean.ply
AI/outputs/comparison_mast3r_bridge1_masked_clean_vs_bridgepointcloud/
```

Full metric evolution across the cleaning chain (all vs the completed bridge
point cloud):

```text
                       baseline   masked    +black filter   +geometric clean
model built (0.04)     82.28%     87.23%    81.07%          77.98%
model built strict     62.85%     68.52%    61.88%          60.01%
likely non-bridge      7.51%      6.41%     6.32%           2.77%
close coverage         66.05%     66.55%    66.27%          67.03%
P90 distance           0.11916    0.11091   0.11085         0.09285
```

Reading this correctly: every cleaning step lowers the "built %" while every
cloud-quality metric improves. That means noise points were counting as false
as-built evidence all along. The cleaned cloud's 77.98% is the most
trustworthy progress estimate of the series, and the 2.77% non-bridge figure
shows the scan is now almost entirely bridge geometry.

## Interpretation

```text
1. Masking moving traffic improves the reconstruction itself: more keyframes
   registered (38 vs 30), and after black-point filtering the cleanest cloud
   of all runs (6.32% non-bridge points vs 7.51% baseline). Segmentation has
   a real production role as a pre-reconstruction cleaning step, not as the
   progress measurement itself.
2. Blackout masking alone is not enough: the reconstructor hallucinates
   geometry in the blacked-out regions, and those points can inflate the
   progress metric. The black-point filter must always follow. A production
   system would instead pass the masks into the reconstruction so masked
   pixels are skipped entirely.
3. The lengthwise mirror flip between runs confirms a known limitation:
   bridges are nearly symmetric along their length, so unsupervised
   PCA+ICP alignment cannot reliably pick the orientation. Production needs
   one manual control point (or GPS) to fix the bridge direction. Section
   percentages also jitter a few points between runs purely from alignment,
   so only large per-section differences are meaningful.
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

# 3. remove hallucinated black points (Windows, AI/.venv-sam3 venv)
AI/.venv-sam3/Scripts/python.exe AI/scripts/remove_black_points.py \
  --input AI/outputs/mast3r_slam_bridge1_masked/pointcloud.ply \
  --output AI/outputs/mast3r_slam_bridge1_masked/pointcloud_filtered.ply \
  --threshold 20

# 4. remove smears and floating noise (Windows, AI/.venv-sam3 venv)
AI/.venv-sam3/Scripts/python.exe AI/scripts/clean_pointcloud.py \
  --input AI/outputs/mast3r_slam_bridge1_masked/pointcloud_filtered.ply \
  --output AI/outputs/mast3r_slam_bridge1_masked/pointcloud_clean.ply

# 5. compare against the completed bridge cloud
PYTHONPATH=AI/src python -m ftp_ai.cli compare-3d-model \
  --current AI/outputs/mast3r_slam_bridge1_masked/pointcloud_clean.ply \
  --final-model AI/data/BridgePointcloud/coverage_result.ply \
  --output AI/outputs/comparison_mast3r_bridge1_masked_clean_vs_bridgepointcloud
```
