# vSLAM And Gaussian Splat Testing

Date: 2026-06-09

Branch: `ai-vslam-gaussian-splat-test`

## Goal

Test two extra AI/3D directions requested by the AI teacher:

- vSLAM with MASt3R-SLAM
- Gaussian Splatting as an alternative visualization/reconstruction direction

## vSLAM Test: MASt3R-SLAM

MASt3R-SLAM was used as the vSLAM experiment because it tracks camera movement
through video and saves a reconstructed point cloud and trajectory.

Run script:

```bash
wsl -d Ubuntu-24.04 -u root -- bash /mnt/c/Users/kilia/Documents/Howest\ 2025-2026/Courses\ Semester\ 2/IndustryProject/Project/FTP-AI/AI/scripts/run_mast3r_bridge1_fast.sh
```

Tracked config:

```text
AI/configs/mast3r_bridge_video_fast.yaml
```

Input:

```text
AI/data/raw/BridgeVid1-271223.mp4
```

Output copied to:

```text
AI/outputs/mast3r_slam_bridge1_fast/pointcloud.ply
AI/outputs/mast3r_slam_bridge1_fast/trajectory.txt
```

Result:

- MASt3R-SLAM completed successfully.
- It produced a point cloud with `3,077,001` vertices.
- It saved `30` camera/keyframe trajectory entries.
- The output is a dense point cloud, not a clean BIM-style mesh.

Conclusion:

- vSLAM works on the drone footage.
- It is useful for camera trajectory and dense reconstruction testing.
- The output is still noisy because drone video includes trees, roads, traffic,
  water, and buildings, not only the bridge.
- Better results need bridge-only filtering, calibration, or control points.

## Gaussian Splat Test

A full trained 3D Gaussian Splatting pipeline was not added yet. Instead, we
created a first Gaussian Splat seed from the MASt3R-SLAM point cloud. This tests
whether splat-style representation is worth exploring before spending time on a
full 3DGS training setup.

Command:

```powershell
$env:PYTHONPATH="AI/src"

AI\.venv-sam3\Scripts\python.exe -m ftp_ai.cli pointcloud-to-gaussian-splat `
  --input AI\outputs\mast3r_slam_bridge1_fast\pointcloud.ply `
  --output AI\outputs\gaussian_splat_bridge1_seed `
  --max-points 250000 `
  --splat-scale 0.008 `
  --opacity 0.7
```

Output:

```text
AI/outputs/gaussian_splat_bridge1_seed/gaussian_splat_seed.ply
AI/outputs/gaussian_splat_bridge1_seed/gaussian_splat_preview.jpg
AI/outputs/gaussian_splat_bridge1_seed/gaussian_splat_summary.json
```

Result:

- Source point cloud: `3,077,001` points
- Generated splat seed: `250,000` gaussians
- Output file: `gaussian_splat_seed.ply`

Important limitation:

This is not trained 3D Gaussian Splatting. It is a splat-compatible seed where
each sampled point becomes one isotropic gaussian. Real 3DGS should train from
images and camera poses, ideally using COLMAP camera outputs.

## Comparison With Final Model

The previous branch added rough current-vs-final model comparison. Current best
comparison result:

- MASt3R-SLAM point cloud vs final model:
  - median distance: `0.02386`
  - P90 distance: `0.08911`
  - close coverage: `68.6%`

This supports the idea that the final bridge model can be used as a comparison
target, but the current alignment is still experimental.

## Recommended Next Steps

1. Improve bridge-only filtering before vSLAM/3DGS.
2. Use COLMAP camera poses as input for a real 3DGS training pipeline.
3. Add manual control points between reconstruction and final GLB/BIM model.
4. Compare only bridge deck/column regions instead of the full scene.
5. Convert distance differences into section-based progress indicators.

