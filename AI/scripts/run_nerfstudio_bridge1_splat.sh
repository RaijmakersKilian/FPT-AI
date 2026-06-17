#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$AI_DIR/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-/opt/nerfstudio-env/bin/python}"
NS_PROCESS_DATA="${NS_PROCESS_DATA:-/opt/nerfstudio-env/bin/ns-process-data}"
NS_TRAIN="${NS_TRAIN:-/opt/nerfstudio-env/bin/ns-train}"
COLMAP_CMD="${COLMAP_CMD:-/usr/local/bin/colmap-win}"
CUDA_HOME="${CUDA_HOME:-/usr/local/cuda-12.6}"

VIDEO="${VIDEO:-$AI_DIR/data/raw/BridgeVid1-271223.mp4}"
OUTPUT_DIR="${OUTPUT_DIR:-$AI_DIR/outputs/nerfstudio_bridgevid1_crop}"
TRAIN_OUTPUT_DIR="${TRAIN_OUTPUT_DIR:-$AI_DIR/outputs/nerfstudio_training}"
EXPERIMENT_NAME="${EXPERIMENT_NAME:-bridgevid1_splatfacto_crop}"

NUM_FRAMES_TARGET="${NUM_FRAMES_TARGET:-120}"
CROP_BOTTOM="${CROP_BOTTOM:-0.42}"
NUM_DOWNSCALES="${NUM_DOWNSCALES:-2}"
MATCHING_METHOD="${MATCHING_METHOD:-sequential}"
CAMERA_TYPE="${CAMERA_TYPE:-pinhole}"
MAX_NUM_ITERATIONS="${MAX_NUM_ITERATIONS:-3000}"
STEPS_PER_SAVE="${STEPS_PER_SAVE:-100}"
PROCESS_ONLY="${PROCESS_ONLY:-0}"
SKIP_PROCESS="${SKIP_PROCESS:-0}"
MAX_JOBS="${MAX_JOBS:-1}"

if [[ ! -x "$NS_PROCESS_DATA" ]]; then
  echo "Nerfstudio not found at $NS_PROCESS_DATA" >&2
  exit 1
fi

if ! command -v "$COLMAP_CMD" >/dev/null 2>&1 && [[ ! -x "$COLMAP_CMD" ]]; then
  echo "COLMAP command not found: $COLMAP_CMD" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR" "$TRAIN_OUTPUT_DIR"

if [[ -d "$CUDA_HOME" ]]; then
  export CUDA_HOME
  export PATH="$CUDA_HOME/bin:$PATH"
  export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
fi
export MAX_JOBS
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.9}"
export TORCH_COMPILE_DISABLE="${TORCH_COMPILE_DISABLE:-1}"
export TORCHDYNAMO_DISABLE="${TORCHDYNAMO_DISABLE:-1}"
export TORCHINDUCTOR_COMPILE_THREADS="${TORCHINDUCTOR_COMPILE_THREADS:-1}"

if [[ "$SKIP_PROCESS" != "1" ]]; then
  echo "Processing video for Nerfstudio:"
  echo "  video:  $VIDEO"
  echo "  output: $OUTPUT_DIR"

  "$NS_PROCESS_DATA" video \
    --data "$VIDEO" \
    --output-dir "$OUTPUT_DIR" \
    --num-frames-target "$NUM_FRAMES_TARGET" \
    --matching-method "$MATCHING_METHOD" \
    --sfm-tool colmap \
    --colmap-cmd "$COLMAP_CMD" \
    --crop-bottom "$CROP_BOTTOM" \
    --num-downscales "$NUM_DOWNSCALES" \
    --camera-type "$CAMERA_TYPE" \
    --no-gpu
else
  echo "SKIP_PROCESS=1, using existing Nerfstudio dataset:"
  echo "  output: $OUTPUT_DIR"
fi

if [[ "$PROCESS_ONLY" == "1" ]]; then
  echo "PROCESS_ONLY=1, skipping splatfacto training."
  exit 0
fi

echo "Training Splatfacto:"
echo "  output:     $TRAIN_OUTPUT_DIR"
echo "  experiment: $EXPERIMENT_NAME"

"$NS_TRAIN" splatfacto \
  --output-dir "$TRAIN_OUTPUT_DIR" \
  --experiment-name "$EXPERIMENT_NAME" \
  --max-num-iterations "$MAX_NUM_ITERATIONS" \
  --steps-per-save "$STEPS_PER_SAVE" \
  nerfstudio-data \
  --data "$OUTPUT_DIR"
