# Finding: Reconstruction Geometry at the Bridge/Road Junction

Date: 2026-06-15 (corrected after reviewing the footage)

## The question

The MASt3R-SLAM reconstructions of the bridge look curved/crooked instead of a
single straight span.

## Important correction

The curve is NOT simply SLAM drift bending a straight bridge. Reviewing the
footage and a top-down render of the cloud shows the bend at one end is a
**real connecting road / ramp that branches off the bridge at an angle**. That
geometry is genuine - it is in the video.

```text
AI/outputs/_singlepass_04032024/bothpass_topdown_big.png
  -> main deck runs left-right; a real connecting road branches off at the
     right end (the "banana").
```

So part of what looked like error is correct geometry. Do not present the curve
as pure drift.

## The actual reconstruction problem

The real weakness is at the **junction**: the connecting road does not join the
main deck cleanly - there is a seam / offset where the two meet, rather than a
smooth connection. Causes:

```text
- Branch/junction points are hard for monocular SLAM: the deck and the ramp are
  captured at slightly different local scale and pose, so they do not fuse
  cleanly where they meet.
- The footage is out-and-back. Trajectory data confirms it (04 Mar: 66
  keyframes, path length 50 vs net displacement 10 = out and back). The reverse
  return leg is flown in the opposite heading, which the neural matcher cannot
  recognize as the same place, so SLAM does not close the loop and the passes do
  not reinforce each other at the junction.
```

## Supporting test

Reconstructing only the forward pass (89 frames, before the turn) gives a
cleaner, straighter strip than feeding both passes:

```text
AI/outputs/_singlepass_04032024/compare_passes.png
  both passes (66 keyframes)  -> junction seam + curl, doubled look
  forward pass only (38 kf)   -> cleaner single strip
```

This is consistent with "the return pass and the junction are where the
reconstruction degrades," not with "the bridge is straight and drift bent it."

## Implications

For processing now:

```text
For out-and-back videos, reconstructing a single clean pass avoids the
un-fused return leg and gives a cleaner model. The real connecting road is
still present; it just is not duplicated/offset by a second pass.
```

For the flight-plan recommendation:

```text
1. Fly passes in a consistent heading (loop around to re-enter the same way, or
   parallel offset lanes) so overlapping views match and SLAM can fuse them -
   especially important across junctions where geometry branches.
2. Log GPS/IMU so pose/scale are known - junctions then align by coordinate,
   not by fragile visual matching.
3. Calibrate the camera (known intrinsics) to reduce local scale error.
```

## Honest framing for the presentation

```text
The reconstruction captures both the bridge and its connecting road. The AI
works; its weak point is fusing geometry at the junction and across a reversed
return pass - a capture/limitation issue, not a modelling failure. Consistent-
heading flights + GPS/IMU would let the same pipeline join these cleanly.
```
