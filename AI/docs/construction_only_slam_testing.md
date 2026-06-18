# Construction-Only SLAM: testing the teacher's "remove background first" idea

Date: 2026-06-16
Branch: `ai-vslam-gaussian-splat-test`

## What the teacher suggested

In the 2026-06-15 meeting (`meetingwithteacher.md`) the teacher floated an
alternative ordering: instead of reconstructing the whole scene and cleaning it
afterwards, **remove the background first with a vision model, then build the
position map** - so the map has fewer points and focuses on what is being built.
We narrowed "what is being built" to the user's target: the **active
construction between the two finished roads** (yellow falsework/gantry, the new
pier, the pylon).

## What we did

```text
1. mask_keep_construction.py: SAM3 keeps ONLY the construction structure
   (gantry / scaffolding / formwork / pier / pylon, cranes excluded) and blacks
   out everything else - finished roads, city, river, trees, sky.
2. Ran it on all 230 frames of BridgeVid1 (the proven flyover).
3. Took the contiguous construction-visible band (frames 54-163, 110 frames)
   and fed those masked frames to MASt3R-SLAM.
```

The masking itself works well: see
`AI/outputs/keep_construction_bridge1_probe/debug/frame_00120.png` - the
under-construction span and new pier are cleanly isolated on black, the two
finished roads and the whole city/river background removed. That is exactly
"detect the construction between the roads".

Construction visibility across the flyover:

```text
- 101 / 230 frames contain construction (>= 0.5% of pixels).
- It is a contiguous MIDDLE band (~frame 54-163): the drone passes the
  construction zone mid-flight. The approach and departure frames have none.
- Even where present, it is small: mean ~2-5% of the frame, max 16.6%.
```

## Result: SLAM cannot reconstruct from construction-only frames

```text
Same video, FULL frames     -> ~3,000,000 points, 30+ keyframes (works).
Same video, construction    -> 0 points, 1 keyframe (fails).
                only band
```

MASt3R-SLAM ran without error but produced an empty map: 1 keyframe, **0 points**
(`logs/keep_construction_bridge1/slam_input.ply` = `element vertex 0`). It could
not track.

The smoking gun is the saved trajectory - a single line, the identity pose:

```text
logs/keep_construction_bridge1/slam_input.txt:
0.0 0.0 0.0 0.0 0.0 0.0 0.0 1.0
```

That is position (0,0,0) with no rotation: SLAM stayed on the first frame and
never estimated any camera motion. With nothing to match between frames, it never
moved, never added keyframes, and never triangulated a point. Compare to a normal
run, where the trajectory has 30+ entries that move through space.

Presentation figure (raw frame vs construction-isolated, with the verdict):

```text
AI/outputs/keep_construction_bridge1_full/EXPERIMENT_RESULT.png
```

## Why - and why this is the right conclusion, not a bug

Monocular SLAM estimates the camera pose by matching features **across the whole
frame** between consecutive views. The background (roads, buildings, riverbank,
trees) is what provides those features. When we black it out to leave only a
small construction patch (2-16% of the frame, much of it repetitive
scaffold/gantry texture, near the frame edge, only in view briefly), there is not
enough to match, so SLAM never establishes motion and never triangulates a map.

In other words: **you cannot remove the background before SLAM, because SLAM is
the step that needs the background.** Removing it first removes the very signal
the reconstruction depends on.

This actually *confirms* the teacher's deeper point from the same meeting:

```text
"eigenlijk is die localisation niet nodig als je exact weet waar je ligt"
 (localisation isn't needed if you know exactly where you are)
```

The correct ordering is the opposite of background-first:

```text
WRONG (tested here): remove background -> then SLAM            -> 0 points
RIGHT (future):      known drone pose (Unity/GPS) -> no SLAM   -> map just the
                     localisation needed -> isolate construction  construction
```

Once Giada's Unity digital twin gives the exact drone pose, the camera position
is known, so no SLAM localisation is required. Then - and only then - you can
keep just the construction pixels and triangulate/map that region directly,
because pose no longer depends on the background. Background-removal-first becomes
valid precisely when you no longer need SLAM to find the camera.

## Takeaway for the presentation

```text
- We tried the teacher's "remove the background first, then map" idea, focused on
  the construction between the roads. The 2D isolation works; the 3D mapping does
  not, because monocular SLAM needs the full scene to localise.
- This is concrete evidence for the project's central recommendation: the value
  comes from KNOWN CAMERA POSE (planned Unity flight path / GPS). With pose, the
  background can be dropped and only the construction mapped; without it, you must
  keep the whole scene and clean afterwards (our main pipeline).
```

## Artifacts (what this run produced)

```text
AI/scripts/mask_keep_construction.py                            the inverse masker
AI/outputs/keep_construction_bridge1_full/EXPERIMENT_RESULT.png the presentation figure
AI/outputs/keep_construction_bridge1_full/masked/               230 construction-only frames
AI/outputs/keep_construction_bridge1_full/slam_input/           the 110-frame band fed to SLAM
AI/outputs/keep_construction_bridge1_full/debug/                46 before/after mask images
AI/outputs/keep_construction_bridge1_full/keep_summary.json     per-frame kept % (101/230 with construction)
AI/outputs/keep_construction_bridge1_probe/debug/               6 before/after probe visuals
AI/.external/MASt3R-SLAM/logs/keep_construction_bridge1/        SLAM output: 0-point ply +
                                                                identity-only trajectory
```

Note: the masked-frames folders are large (~1 GB of PNGs) and live under the
git-ignored `AI/outputs/`. The presentation figure + this doc are the parts worth
keeping; the raw frame dumps can be deleted to reclaim space.
