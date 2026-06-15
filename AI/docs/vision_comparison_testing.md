# Vision-Only Bridge Comparison (Teacher-Recommended Direction)

Date: 2026-06-15 (final week, presentation Friday 2026-06-19)

This is the direction the AI teacher recommended in the 2026-06-15 meeting
(transcript: `AI/docs/meetingwithteacher.md`). It is the second AI track
alongside the now-finished point-cloud work.

## What The Teacher Said

Distilled from the meeting:

```text
1. STOP on the point cloud. It is done and proven: MASt3R-SLAM turns a drone
   video into a usable 3D reconstruction, and the same model handles a drone
   flying the bridge several times (multi-pass), so for the new Unity-planned
   capture you can tell the client "upload the video and it will work" with a
   better, denser, fewer-holes result.

2. NEW focus: a vision-only comparison that does NOT use the MASt3R-SLAM cloud.
   Take a single drone frame, use Segment Anything to isolate the bridge
   structure and remove the background, and compare it against the Unity / 3D
   model render (which already has no background, no water, no trees).

3. Why it becomes powerful later: once Giada's Unity digital twin defines the
   drone flight path, we get the exact drone pose. Then the real frame and the
   model render share the same viewpoint, so the comparison is automatic and
   1:1 - the only difference between them is the background, which this step
   removes.
```

## What We Built

A three-script vision pipeline (all run in the `AI/.venv-sam3` environment):

```text
AI/scripts/segment_bridge_frame.py   - SAM3 isolates the bridge, removes background
AI/scripts/render_bridge_model.py    - software render of the GLB model, no background
AI/scripts/build_vision_comparison.py - composes the 4-panel presentation figure
```

### 1. Construction-zone segmentation + isolation

IMPORTANT (2026-06-15 correction): the target is NOT the whole bridge - the
two roadways are already finished. Progress tracking must focus on the ACTIVE
CONSTRUCTION happening between/alongside the finished roads: the yellow
falsework/gantry, the new pier being built, the pylon, and cranes. This
matches the teacher's brief ("search for what is currently being built, ignore
the rest").

`segment_bridge_frame.py --focus construction` (default) runs SAM3 with
prompts that localize the construction apparatus and produces:

```text
structures_overlay.jpg        - construction classes colored (finished road dimmed grey)
bridge_only.jpg               - everything except the construction zone removed
bridge_only_transparent.png   - same with a real alpha channel
bridge_mask.png               - binary construction-zone mask
segmentation_summary.json     - per-class pixel coverage + construction_pixel_pct
```

Prompt selection mattered. A SAM3 prompt probe on frame 120 showed broad terms
over-fire onto the whole deck, so they were dropped:

```text
over-fires onto whole bridge:  "bridge construction formwork",
                               "unfinished bridge segment", "bridge construction site"
localizes the construction:    "yellow steel gantry" (0.62), "scaffolding" (0.56),
                               "bridge pylon tower", "construction crane"
```

`--focus full-bridge` keeps the old whole-bridge prompts if ever needed.
Equipment (cranes) is segmented but excluded from the isolated zone by default
(`--include-equipment` to keep it).

### 2. Model render (no background)

EGL/offscreen OpenGL is unavailable on this Windows machine, so
`render_bridge_model.py` is a pure-numpy/OpenCV perspective renderer: it
samples the GLB surface, projects through a pinhole camera with a painter's
depth sort, and splats colored disks on black. Viewpoint is controllable
(`--azimuth`, `--elevation`). The GLB is the bridge deck split into ~70 spans
(twin carriageways), so the render shows two parallel deck ribbons - matching
the twin decks visible in the drone frames.

### 3. Presentation figure

`build_vision_comparison.py` stitches the four steps into one panel:
drone frame -> SAM segmentation -> background removed -> planned 3D model,
with a caption explaining the future 1:1 Unity mapping.

## Results

Outputs in `AI/outputs/vision_compare/`:

```text
frame_00120/comparison_figure.jpg   strong example (oblique, deck + construction)
frame_00090/comparison_figure.jpg   strong example (deck + pylon + cranes split out)
model_render.jpg                    oblique model render
model_render_topdown.jpg            near top-down model render
```

Per-frame construction-zone coverage (focus=construction, min-score 0.4):

```text
frame 120: construction zone = 2.78% of frame - yellow falsework/gantry + pier isolated,
           both finished roads correctly left out
frame 90:  construction zone = 2.86% of frame - falsework segments + cranes, roads left out
```

The tight 2-3% figures are the point: the segmentation now isolates only the
active construction between the roads, not the whole bridge (which earlier read
10-13%). Whole-bridge `--focus full-bridge` still works for context.

## Honest Findings (for the presentation)

```text
+ SAM3 can isolate the as-built bridge from a single frame and cleanly remove
  city/river/tree background - no 3D reconstruction needed for this check.
+ It distinguishes bridge structure from equipment (cranes) on good frames.
+ The output is exactly the background-free image needed for a 1:1 model
  comparison once drone pose is known.

- It is viewpoint-dependent: it fired well on oblique side views (90, 120) and
  failed on flatter/receding views (60, 150). Open-vocabulary prompting is not
  reliable enough for automatic per-frame progress on its own.
- Masks have holes where traffic was blacked out or contrast was low.
- Without the drone pose we cannot yet align the real frame to the model
  viewpoint, so the current comparison is side-by-side (method demo), not a
  pixel overlap score.
```

## Presentation Talking Points

```text
1. Two AI tracks delivered:
   a) 3D point-cloud track (MASt3R-SLAM) - DONE and proven, incl. masking +
      cleaning + per-section comparison vs the completed bridge cloud.
   b) Vision track (this) - isolate the bridge in 2D and compare to the model
      without needing a 3D map.

2. The data-capture process is the real bottleneck, not the AI model. With
   Giada's Unity-planned flight path we get the drone pose, which makes BOTH
   tracks better: denser multi-pass reconstruction, and automatic 1:1 frame-to-
   model vision comparison.

3. MASt3R-SLAM already supports multi-pass flights with the same model, so the
   client message is simply "fly the planned path, upload the video, it works."

4. What a production team still needs: planned repeatable flights, drone pose
   (Unity/GPS), and - for fully automatic 2D progress - a project-specific
   trained segmentation model instead of open-vocabulary prompts.
```

## How To Reproduce

```text
# segment one frame (isolate bridge, remove background)
AI/.venv-sam3/Scripts/python.exe AI/scripts/segment_bridge_frame.py \
  --image AI/outputs/bridgevid1_masked_frames_s15/frames/frame_00120.png \
  --output AI/outputs/vision_compare/frame_00120

# render the planned model with no background
AI/.venv-sam3/Scripts/python.exe AI/scripts/render_bridge_model.py \
  --model Frontend/KCPT_Ki_centered.glb \
  --output AI/outputs/vision_compare/model_render.jpg --azimuth 35 --elevation 25

# compose the presentation figure
AI/.venv-sam3/Scripts/python.exe AI/scripts/build_vision_comparison.py \
  --frame AI/outputs/bridgevid1_masked_frames_s15/frames/frame_00120.png \
  --overlay AI/outputs/vision_compare/frame_00120/structures_overlay.jpg \
  --bridge-only AI/outputs/vision_compare/frame_00120/bridge_only.jpg \
  --model-render AI/outputs/vision_compare/model_render.jpg \
  --output AI/outputs/vision_compare/frame_00120/comparison_figure.jpg
```
