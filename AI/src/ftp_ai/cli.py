from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from .batch import run_roi_batch
from .classification import IdentitySegmentClassifier
from .config import PipelineConfig
from .panorama import build_drone_panorama, build_slitscan_panorama, build_smooth_panorama, build_strip_panorama
from .pipeline import run_image_pipeline, run_video_pipeline
from .roi import Sam3ConstructionRoiDetector
from .segmentation import ClassicalSegmenter, SAM3_PROGRESS_PROMPTS, Sam3TextPromptSegmenter
from .video import extract_panorama_frames


console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="GOT bridge AI progress pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    video_parser = subparsers.add_parser("run-video", help="Run pipeline from a drone video")
    video_parser.add_argument("--video", type=Path, required=True)
    video_parser.add_argument("--output", type=Path, required=True)
    video_parser.add_argument("--config", type=Path)
    video_parser.add_argument("--sample-every", type=int)
    video_parser.add_argument(
        "--segmenter",
        choices=["classical", "sam3", "sam3-progress"],
        default="classical",
    )
    video_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="none")
    video_parser.add_argument("--analysis-max-dimension", type=int)

    image_parser = subparsers.add_parser("run-image", help="Run pipeline from one image")
    image_parser.add_argument("--image", type=Path, required=True)
    image_parser.add_argument("--output", type=Path, required=True)
    image_parser.add_argument("--config", type=Path)
    image_parser.add_argument(
        "--segmenter",
        choices=["classical", "sam3", "sam3-progress"],
        default="classical",
    )
    image_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="none")
    image_parser.add_argument("--analysis-max-dimension", type=int)

    images_parser = subparsers.add_parser("run-images", help="Run pipeline from an image folder")
    images_parser.add_argument("--images", type=Path, required=True)
    images_parser.add_argument("--output", type=Path, required=True)
    images_parser.add_argument("--config", type=Path)
    images_parser.add_argument(
        "--segmenter",
        choices=["classical", "sam3", "sam3-progress"],
        default="classical",
    )
    images_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="none")
    images_parser.add_argument("--analysis-max-dimension", type=int)

    batch_parser = subparsers.add_parser(
        "run-roi-batch",
        help="Run ROI analysis on a spread of images and write a batch summary",
    )
    batch_parser.add_argument("--images", type=Path, required=True)
    batch_parser.add_argument("--output", type=Path, required=True)
    batch_parser.add_argument("--config", type=Path)
    batch_parser.add_argument("--limit", type=int, default=10)
    batch_parser.add_argument(
        "--segmenter",
        choices=["classical", "sam3", "sam3-progress"],
        default="classical",
    )
    batch_parser.add_argument("--roi", choices=["none", "sam3-construction"], default="sam3-construction")
    batch_parser.add_argument("--analysis-max-dimension", type=int)

    panorama_parser = subparsers.add_parser(
        "build-panorama",
        help="Build a smooth panorama from an image folder",
    )
    panorama_parser.add_argument("--images", type=Path, required=True)
    panorama_parser.add_argument("--output", type=Path, required=True)
    panorama_parser.add_argument("--max-dimension", type=int, default=4096)
    panorama_parser.add_argument("--method", choices=["stitcher", "strip"], default="stitcher")
    panorama_parser.add_argument("--max-images", type=int, default=80)

    video_pano_parser = subparsers.add_parser(
        "build-video-panorama",
        help="Extract frames from a drone video and stitch them into a full bridge panorama",
    )
    video_pano_parser.add_argument("--video", type=Path, required=True, help="Drone video file")
    video_pano_parser.add_argument("--output", type=Path, required=True, help="Output panorama path (.jpg)")
    video_pano_parser.add_argument(
        "--n-tiles",
        type=int,
        default=200,
        help="Maximum number of overlapping frames to extract from the video (default 200)",
    )
    video_pano_parser.add_argument(
        "--blur-threshold",
        type=float,
        default=80.0,
        help="Minimum sharpness score to keep a frame (default 80; lower if too few frames pass)",
    )
    video_pano_parser.add_argument(
        "--sample-every",
        type=int,
        default=15,
        help="Extract one frame every N video frames (default 15, tuned for 60fps drone footage; use 8 for 30fps, 1 for very short clips)",
    )
    video_pano_parser.add_argument(
        "--work-width",
        type=int,
        default=1280,
        help="Resize tiles to this width before feature matching (default 1280)",
    )
    video_pano_parser.add_argument(
        "--max-dimension",
        type=int,
        default=8192,
        help="Longest side of the output panorama in pixels (default 8192)",
    )
    video_pano_parser.add_argument(
        "--tiles-dir",
        type=Path,
        default=None,
        help="Where to save extracted tiles (defaults to <output_dir>/mosaic_tiles)",
    )
    video_pano_parser.add_argument(
        "--start-frame",
        type=int,
        default=0,
        help="Skip this many video frames before extracting (useful to skip takeoff/approach)",
    )
    video_pano_parser.add_argument(
        "--rotate",
        action="store_true",
        default=False,
        help="Rotate each frame 90 degrees clockwise before stitching (use when bridge runs top-to-bottom in the video)",
    )
    video_pano_parser.add_argument(
        "--method",
        choices=["drone", "slitscan"],
        default="drone",
        help="Stitching method: 'drone' = SIFT feature chain (default), 'slitscan' = fixed-strip concatenation (no rotation artefacts, best for steady forward flight)",
    )

    args = parser.parse_args()
    config = _load_config(getattr(args, "config", None))
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
        segmenter, classifier = _build_segmentation_stack(args.segmenter)
        report = run_video_pipeline(
            args.video,
            args.output,
            config,
            segmenter=segmenter,
            classifier=classifier,
            roi_detector=_build_roi_detector(args.roi),
            analysis_max_dimension=args.analysis_max_dimension,
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
            analysis_max_dimension=args.analysis_max_dimension,
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
            analysis_max_dimension=args.analysis_max_dimension,
            inputs={"images": str(args.images)},
        )
    elif args.command == "run-roi-batch":
        segmenter, classifier = _build_segmentation_stack(args.segmenter)
        items = run_roi_batch(
            images_dir=args.images,
            output_dir=args.output,
            config=config,
            limit=args.limit,
            segmenter=segmenter,
            classifier=classifier,
            roi_detector=_build_roi_detector(args.roi),
            analysis_max_dimension=args.analysis_max_dimension,
        )
        succeeded = [item for item in items if item.report is not None]
        average = (
            sum(item.report.overall_completion for item in succeeded if item.report)
            / len(succeeded)
            if succeeded
            else 0.0
        )
        console.print(f"[green]Batch succeeded:[/green] {len(succeeded)}/{len(items)}")
        console.print(f"[green]Average completion:[/green] {average:.1%}")
        console.print(f"[green]Summary:[/green] {args.output / 'summary.json'}")
        return
    elif args.command == "build-panorama":
        output_path = args.output
        if output_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            output_path = output_path / "panorama.jpg"
        image_paths = sorted(
            path
            for path in args.images.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        )
        if args.method == "strip":
            build_strip_panorama(
                image_paths,
                output_path,
                max_images=args.max_images,
                max_dimension=args.max_dimension,
            )
        else:
            build_smooth_panorama(image_paths, output_path, max_dimension=args.max_dimension)
        console.print(f"[green]Panorama:[/green] {output_path}")
        return
    elif args.command == "build-video-panorama":
        output_path = args.output
        if output_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            output_path = output_path / "panorama.jpg"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        frames_dir = args.tiles_dir or (output_path.parent / "mosaic_tiles")
        console.print(f"[cyan]Extracting overlapping frames from:[/cyan] {args.video}")
        frame_paths = extract_panorama_frames(
            video_path=args.video,
            output_dir=frames_dir,
            sample_every_n_frames=args.sample_every,
            blur_threshold=args.blur_threshold,
            target_frames=args.n_tiles,
            start_frame=args.start_frame,
        )
        if not frame_paths:
            console.print(
                "[red]No usable frames extracted — lower --blur-threshold or --sample-every and retry.[/red]"
            )
            return
        console.print(f"[cyan]Extracted {len(frame_paths)} frames - stitching panorama...[/cyan]")
        if args.method == "slitscan":
            build_slitscan_panorama(
                image_paths=frame_paths,
                output_path=output_path,
                work_width=args.work_width,
                max_dimension=args.max_dimension,
            )
        else:
            build_drone_panorama(
                image_paths=frame_paths,
                output_path=output_path,
                max_images=len(frame_paths),
                work_width=args.work_width,
                max_dimension=args.max_dimension,
                rotate_cw90=args.rotate,
            )
        console.print(f"[green]Panorama:[/green] {output_path}")
        return
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
    if name == "sam3-progress":
        return (
            Sam3TextPromptSegmenter(
                prompts=SAM3_PROGRESS_PROMPTS,
                min_score=0.25,
                max_segments_per_prompt=6,
                min_area_ratio=0.004,
                nms_iou_threshold=0.45,
            ),
            IdentitySegmentClassifier(),
        )
    return ClassicalSegmenter(), None


def _build_roi_detector(name: str):
    if name == "sam3-construction":
        return Sam3ConstructionRoiDetector()
    return None


if __name__ == "__main__":
    main()
