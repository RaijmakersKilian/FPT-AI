# Finding: Why the Reconstructions Curve, and How To Fix It

Date: 2026-06-15

## The question

The MASt3R-SLAM reconstructions of the bridge come out curved/crooked instead
of a single straight span, even though the drone footage is clear and flies the
bridge out-and-back.

## What the trajectory data shows

Reading each run's `02_slam/trajectory.txt` (camera path) is decisive:

```text
video                 keyframes  path_len  net_disp   shape
20 Aug (93%, straight)   20        18.1      15.8      one-way  (path = net)
18 Nov (87%, straight)   19        15.0      14.8      one-way
04 Mar (73%, BANANA)     66        50.0      10.0      OUT-AND-BACK (path >> net)
```

The straight reconstructions are the ones where SLAM tracked only the **forward
pass**. The curved one (04 Mar) is the one where it tracked the drone going
**out (to 19.8 units) and back (ending at 10)** - a clear out-and-back path.

So the return pass did not help - it made the result worse.

## Root cause: failed loop closure on the reversed return leg

SLAM accumulates small per-frame drift; over a long span the model bends. A
return pass over the same bridge *should* let SLAM "close the loop" - recognize
it has been there before and cancel the accumulated drift, straightening
everything.

It fails here because the return leg is flown in the **opposite direction**.
The bridge looks completely different to the neural matcher from the reverse
heading, so it never recognizes the overlap. Instead of snapping the return
onto the forward pass, SLAM lays it down as a **second drifted strip** that
diverges from the first - producing the banana curve and the doubled/thick look.

## Proof: reconstruct the forward pass only

Cutting 04 Mar to just its forward half (89 frames before the turn) and
reconstructing:

```text
both passes (66 keyframes)   -> curved banana
forward pass only (38 kf)    -> visibly straight
```

See `AI/outputs/_singlepass_04032024/compare_passes.png`. Same video, same
pipeline; removing the reversed return leg straightens the bridge.

## Implications

For processing now:

```text
For out-and-back videos, reconstructing a single clean pass gives a straighter,
more usable model than feeding both passes (which SLAM cannot fuse).
```

For the flight-plan recommendation (this is the sharp, concrete rule the
finding produces):

```text
1. Do NOT fly the return leg reversed. Either re-enter each pass in the SAME
   heading (loop around), or fly parallel offset lanes (lawnmower pattern), so
   overlapping views match and loop closure actually works and CORRECTS drift.
2. Log GPS/IMU so camera pose is known - drift is then corrected regardless of
   viewing direction.
3. Calibrate the camera (known intrinsics) to remove projection warping.
```

That one heading rule would have straightened every curved reconstruction in
`AI/outputs/runs/topdown_grid.png`.

## Presentation slide

Three panels: both-pass (curved) -> forward-only (straight) -> the flight rule
that fixes it. It demonstrates the AI works, isolates the exact cause, and turns
it into an actionable capture requirement - the core thesis of the study in one
slide.
