from __future__ import annotations

import argparse
import os
from pathlib import Path

import torch
from PIL import Image


DEFAULT_PROMPTS = [
    "construction site",
    "bridge construction site",
    "bridge deck",
    "concrete bridge deck",
    "road surface",
    "construction formwork",
    "steel rebar",
    "construction equipment",
    "crane",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.2)
    parser.add_argument("--prompts", nargs="*", default=DEFAULT_PROMPTS)
    args = parser.parse_args()

    load_local_env()

    from sam3.model.sam3_image_processor import Sam3Processor
    from sam3.model_builder import build_sam3_image_model

    model = build_sam3_image_model()
    processor = Sam3Processor(model, confidence_threshold=args.threshold)
    image = Image.open(args.image).convert("RGB")

    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        state = processor.set_image(image)

    for prompt in args.prompts:
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            output = processor.set_text_prompt(state=state, prompt=prompt)
        scores = output["scores"].detach().cpu().float()
        boxes = output["boxes"].detach().cpu().float()
        top_score = float(scores.max()) if len(scores) else 0.0
        print(f"{prompt}: count={len(scores)} top_score={top_score:.3f}")
        if len(scores):
            print(f"  first_box={boxes[0].tolist()}")
        torch.cuda.empty_cache()


def load_local_env() -> None:
    for env_path in (Path(".env"), Path("data/.env")):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()
