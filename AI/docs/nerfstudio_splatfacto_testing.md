# Nerfstudio Splatfacto Testing

Date: 2026-06-09

Branch: `ai-vslam-gaussian-splat-test`

## Goal

Test a proper Gaussian Splatting route from the bridge video, not just a point
cloud converted into a splat-style PLY.

Proper route:

```text
video -> frames -> COLMAP camera poses -> Splatfacto training -> trained gaussians
```

## Environment

Nerfstudio was installed in WSL:

```text
/opt/nerfstudio-env
```

CUDA was visible to PyTorch:

```text
torch 2.5.1+cu121
CUDA: available
GPU: RTX 4070 Laptop GPU
```

System tools installed in WSL:

```text
ffmpeg
colmap
```

The reusable script is:

```text
AI/scripts/run_nerfstudio_bridge1_splat.sh
```

## What Worked

Nerfstudio processing works when using a no-spaces Linux path such as:

```text
/opt/ftp_ai_ns_bridge1
```

The project path on Windows contains spaces, and COLMAP/Nerfstudio was not
reliable with those paths.

A 40-frame processing run completed successfully once:

```text
Starting with 3439 video frames
Extracted 41 images
COLMAP matched 41 images
COLMAP found poses for all images
```

This means a real Gaussian Splat training pipeline is possible in principle:
the video can be converted into a Nerfstudio dataset with camera poses.

## 2026-06-10 Retry Result

We retried Splatfacto after precompiling the `gsplat` CUDA backend with one
compile job:

```text
CUDA_HOME=/usr/local/cuda-12.6
TORCH_CUDA_ARCH_LIST=8.9
MAX_JOBS=1
TORCH_COMPILE_DISABLE=1
TORCHDYNAMO_DISABLE=1
```

This time training produced a real Nerfstudio checkpoint:

```text
/opt/ftp_ai_ns_bridge1/nerfstudio_training/bridgevid1_splatfacto_compile_disabled/splatfacto/2026-06-10_105022/nerfstudio_models/step-000000049.ckpt
```

The checkpoint was exported to a Gaussian Splat PLY:

```text
AI/outputs/nerfstudio_bridgevid1_trained_splat/bridgevid1_trained_splat.ply
```

The exported file contains `7927` gaussian vertices and is about `458 KB`.

This is a real trained Splatfacto output, not just a point cloud converted into
a splat-like file.

## Remaining Problems

Observed issues:

- Larger `123` frame processing registered only `2` images.
- Later `40` frame processing produced only `8` usable poses.
- `gsplat` initially failed because `CUDA_HOME` was not set.
- After setting `CUDA_HOME=/usr/local/cuda-12.6`, `gsplat` started compiling.
- Parallel CUDA compilation was killed, likely due memory pressure.
- Retrying with `MAX_JOBS=1` fixed the compile problem, but the dataset still
  has too few registered poses for a good visual result.

Current output available in WSL:

```text
/opt/ftp_ai_ns_bridge1/nerfstudio_bridgevid1_crop/transforms.json
/opt/ftp_ai_ns_bridge1/nerfstudio_bridgevid1_crop/sparse_pc.ply
/opt/ftp_ai_ns_bridge1/nerfstudio_training/
```

The current `transforms.json` contains `8` camera frames, which is too small for
a good bridge splat. The 50-iteration export is mainly proof that the pipeline
works.

## Conclusion

We tested the correct Gaussian Splat direction using Nerfstudio/Splatfacto. The
video preprocessing and COLMAP pose estimation can work, and Splatfacto can now
train/export on this machine.

For now, MASt3R-SLAM remains the strongest 3D result because it produced a much
denser reconstruction from the same bridge video. The Splatfacto result needs a
better posed frame set before it becomes useful visually.

## Recommended Next Steps

1. Use a clean no-spaces WSL folder for all Nerfstudio/3DGS work.
2. Use shorter bridge-only clips and tune frame counts until COLMAP registers
   many cameras consistently.
3. Keep `MAX_JOBS=1` for `gsplat` compilation on this laptop.
4. Train for more iterations only after pose registration improves; otherwise it
   will spend time improving a weak reconstruction.
5. Only train Splatfacto when the dataset has at least `20+` registered poses;
   `50+` would be better.
