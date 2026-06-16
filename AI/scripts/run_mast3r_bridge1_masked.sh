#!/usr/bin/env bash
set -euo pipefail

# Run MASt3R-SLAM on vehicle-masked frames produced by mask_dynamic_objects.py.
# The frames are already extracted at the experiment stride, so this uses the
# subsample:1 frames config.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AI_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SLAM="${SLAM:-$AI_DIR/.external/MASt3R-SLAM}"
FRAMES="${FRAMES:-$AI_DIR/outputs/bridgevid1_masked_frames/masked}"
CONFIG_SOURCE="${CONFIG_SOURCE:-$AI_DIR/configs/mast3r_bridge_frames_fast.yaml}"
CONFIG_TARGET="$SLAM/config/bridge_frames_fast.yaml"
TORCH_LIB="${TORCH_LIB:-/opt/mast3r-slam-env/lib/python3.12/site-packages/torch/lib}"
PYTHON_BIN="${PYTHON_BIN:-/opt/mast3r-slam-env/bin/python}"
SAVE_AS="${SAVE_AS:-bridge1_fast_masked}"

export PYTHONPATH="$SLAM/thirdparty/mast3r:$SLAM/thirdparty/mast3r/dust3r:$SLAM/thirdparty/mast3r/dust3r/croco:$SLAM"
export LD_LIBRARY_PATH="$TORCH_LIB"

cp "$CONFIG_SOURCE" "$CONFIG_TARGET"
cd "$SLAM"

"$PYTHON_BIN" main.py \
  --dataset "$FRAMES" \
  --config config/bridge_frames_fast.yaml \
  --no-viz \
  --save-as "$SAVE_AS"
