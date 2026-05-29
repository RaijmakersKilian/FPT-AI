from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from .classification import IdentitySegmentClassifier
from .config import PipelineConfig
from .pipeline import run_image_pipeline, run_video_pipeline
from .roi import Sam3ConstructionRoiDetector
from .segmentation import ClassicalSegmenter, Sam3TextPromptSegmenter


console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="GOT bridge AI progress pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    video_parser = subparsers.add_parser("run-video", help="Run pipeline from a drone video")
    video_parser.add_argument("--video", type=Path, required=True)
    video_parser.add_argument("--output", type=Path, required=True)
    video_parser.add_argument("--config", type=Path)
    video_parser.add_argument("--sample-every", type=int)
    video_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="none")

    image_parser = subparsers.add_parser("run-image", help="Run pipeline from one image")
    image_parser.add_argument("--image", type=Path, required=True)
    image_parser.add_argument("--output", type=Path, required=True)
    image_parser.add_argument("--config", type=Path)
    image_parser.add_argument("--segmenter", choices=["classical", "sam3"], default="classical")
    image_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="none")

    images_parser = subparsers.add_parser("run-images", help="Run pipeline from an image folder")
    images_parser.add_argument("--images", type=Path, required=True)
    images_parser.add_argument("--output", type=Path, required=True)
    images_parser.add_argument("--config", type=Path)
    images_parser.add_argument("--segmenter", choices=["classical", "sam3"], default="classical")
    images_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="none")

    args = parser.parse_args()
    config = _load_config(args.config)
    if getattr(args, "sample_every", None):
        config = PipelineConfig(
            project_name=config.project_name,
            sample_every_n_frames=args.sample_every,
            blur_threshold=config.blur_threshold,
            motion_threshold=config.motion_threshold,
            target_keyframes=config.target_keyframes,
            sections=config.sections,
            weights=config.weights,
        )

    if args.command == "run-video":
        report = run_video_pipeline(
            args.video,
            args.output,
            config,
            roi_detector=_build_roi_detector(args.roi),
        )
    elif args.command == "run-image":
        segmenter, classifier = _build_segmentation_stack(args.segmenter)
        report = run_image_pipeline(
            [args.image],
            args.output,
            config,
            segmenter=segmenter,
            classifier=classifier,
            roi_detector=_build_roi_detector(args.roi),
            inputs={"image": str(args.image)},
        )
    elif args.command == "run-images":
        image_paths = sorted(
            path
            for path in args.images.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        )
        segmenter, classifier = _build_segmentation_stack(args.segmenter)
        report = run_image_pipeline(
            image_paths,
            args.output,
            config,
            segmenter=segmenter,
            classifier=classifier,
            roi_detector=_build_roi_detector(args.roi),
            inputs={"images": str(args.images)},
        )
    else:
        raise ValueError(f"Unsupported command: {args.command}")

    console.print(f"[green]Overall completion:[/green] {report.overall_completion:.1%}")
    console.print(f"[green]Report:[/green] {args.output / 'report.json'}")
    console.print(f"[green]Annotated image:[/green] {args.output / 'annotated.jpg'}")


def _load_config(path: Path | None) -> PipelineConfig:
    return PipelineConfig.from_json(path) if path else PipelineConfig()


def _build_segmentation_stack(name: str):
    if name == "sam3":
        return Sam3TextPromptSegmenter(), IdentitySegmentClassifier()
    return ClassicalSegmenter(), None


def _build_roi_detector(name: str):
    if name == "sam3-construction":
        return Sam3ConstructionRoiDetector()
    return None


if __name__ == "__main__":
    main()
