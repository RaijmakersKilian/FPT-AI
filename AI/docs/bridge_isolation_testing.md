# Bridge Isolation: Cropping The Reconstruction To The Bridge Only

Date: 2026-06-11

Question tested:

```text
Can the reconstruction be limited to the bridge only, removing trees,
buildings, roads, and water around it?
```

Answer: mostly yes, with a combination of reference-model cropping and
color-based vegetation removal. Fully surgical isolation is blocked by
alignment precision, which is the project's recurring bottleneck.

## Approach

2D masking of everything except the bridge was rejected: SLAM needs visible
features around the bridge to track camera motion, and blacking out 80% of
each frame would break tracking (the traffic masking only removed ~5%).

Instead the crop happens in 3D, after reconstruction:

```text
1. Align the cleaned reconstruction to a bridge reference
   (same PCA + sign-flip + trimmed ICP as the comparison pipeline).
2. Keep only points within a normalized distance threshold of the reference.
3. Optionally remove vegetation by color (excess-green ratio for bright
   foliage + HSV green-hue test for dark/shadowed foliage; a saturation
   floor protects the grey deck and roads).
```

Script:

```text
AI/scripts/extract_bridge_points.py
  --current   <cleaned reconstruction .ply>
  --reference <bridge model .glb or bridge point cloud .ply>
  --threshold 0.04
  --remove-vegetation
```

Output keeps the reconstruction's original coordinates and colors.

## Findings

Reference choice matters:

```text
AI/data/BridgePointcloud/coverage_result.ply is a thin, nearly flat strip
(bridge deck only, ~494 m). ICP alignment of a full scene to a flat strip is
ill-posed: the fit collapsed scale to 0.75 and squashed the scene onto the
strip plane, so the crop kept wide bands of terrain.

Frontend/KCPT_Ki_centered.glb (the 3D design model with deck and supports)
constrains the alignment much better: scale 0.96, residual p75 0.029 vs
0.057. Use the GLB as the crop reference.
```

Distance cropping alone is not surgical:

```text
The alignment residual (~0.03 normalized, roughly 7 m) is larger than the
gap between the deck edge and the adjacent trees. Tightening the threshold
below the residual starts cutting real bridge before it cuts the trees
next to it. Distance cropping reliably removes distant buildings, water,
and terrain - not vegetation touching the corridor.
```

Color-based vegetation removal closes most of the gap:

```text
excess-green: g > 1.06*r and g > 1.06*b and g > 40  (bright foliage)
HSV: hue 25-95 and saturation >= 50                 (dark foliage)
```

## Result On The Best Cloud (2026-06-11)

Input: `AI/outputs/mast3r_slam_bridge1_masked_s15/pointcloud_clean.ply`
(masked + black-filtered + geometrically cleaned, 3,212,993 points).

```text
distance crop (GLB, 0.04):  3,212,993 -> 2,598,397  (removes far surroundings)
vegetation filter:          -956,927 vegetation points
final bridge-only cloud:    1,640,712 points (51% of input)
```

Output:

```text
AI/outputs/mast3r_slam_bridge1_masked_s15/pointcloud_bridge_only.ply
```

What remains besides the bridge: the construction worksite alongside the
bridge (arguably wanted), parts of the parallel access roads (same grey as
the deck, geometrically adjacent), and fragments of nearby buildings. What
is gone: most trees, the river area, distant buildings and terrain.

## Production Conclusion

```text
With unsupervised alignment, bridge isolation is approximate. With
calibrated alignment (control points or GPS, ~1 m accuracy), a simple
corridor crop around the design model would isolate the bridge almost
perfectly - no color heuristics needed. This is the same bottleneck as the
progress measurement itself: alignment precision, not AI capability.
A trained 3D semantic segmentation model (or projecting SAM3 bridge masks
into the cloud via the keyframe poses) is the heavier alternative if no
calibration is available.
```
