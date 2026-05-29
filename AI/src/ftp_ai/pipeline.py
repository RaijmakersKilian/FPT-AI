from __future__ import annotations

from pathlib import Path

from .classification import RuleBasedSegmentClassifier, SegmentClassifier
from .config import PipelineConfig
from .models import ProgressReport
from .panorama import stitch_images
from .preprocess import crop_black_borders
from .progress import estimate_progress
from .report import write_annotated_image, write_json_report
from .roi import RoiDetector
from .segmentation import ClassicalSegmenter, Segmenter
from .video import extract_keyframes


def run_video_pipeline(
    video_path: Path,
    output_dir: Path,
    config: PipelineConfig,
    segmenter: Segmenter | None = None,
    classifier: SegmentClassifier | None = None,
    roi_detector: RoiDetector | None = None,
) -> ProgressReport:
    keyframes = extract_keyframes(
        video_path=video_path,
        output_dir=output_dir / "keyframes",
        sample_every_n_frames=config.sample_every_n_frames,
        blur_threshold=config.blur_threshold,
        motion_threshold=config.motion_threshold,
        target_keyframes=config.target_keyframes,
    )
    if not keyframes:
        raise RuntimeError("No usable keyframes were extracted from the video.")

    return run_image_pipeline(
        image_paths=[keyframe.path for keyframe in keyframes],
        output_dir=output_dir,
        config=config,
        segmenter=segmenter,
        classifier=classifier,
        roi_detector=roi_detector,
        inputs={"video": str(video_path), "keyframes": str(output_dir / "keyframes")},
    )


def run_image_pipeline(
    image_paths: list[Path],
    output_dir: Path,
    config: PipelineConfig,
    segmenter: Segmenter | None = None,
    classifier: SegmentClassifier | None = None,
    roi_detector: RoiDetector | None = None,
    inputs: dict[str, str] | None = None,
) -> ProgressReport:
    output_dir.mkdir(parents=True, exist_ok=True)
    panorama_path = stitch_images(image_paths, output_dir / "panorama.jpg")
    analysis_path = crop_black_borders(panorama_path, output_dir / "analysis_image.jpg")
    roi_inputs: dict[str, str] = {}

    if roi_detector is not None:
        roi = roi_detector.detect(analysis_path, output_dir)
        if roi is not None:
            analysis_path = roi.image_path
            roi_inputs = {
                "roi_image": str(roi.image_path),
                "roi_mask": str(roi.mask_path),
                "roi_bbox_xyxy": ",".join(str(value) for value in roi.bbox_xyxy),
                "roi_prompt": roi.prompt,
                "roi_confidence": f"{roi.confidence:.4f}",
            }

    segmenter = segmenter or ClassicalSegmenter()
    classifier = classifier or RuleBasedSegmentClassifier()
    segments = segmenter.segment(analysis_path)
    segments = classifier.classify(analysis_path, segments)

    image_shape = _image_shape(analysis_path)
    report = estimate_progress(
        segments=segments,
        image_shape=image_shape,
        config=config,
        inputs={
            "panorama": str(panorama_path),
            "analysis_image": str(analysis_path),
            **roi_inputs,
            **(inputs or {}),
        },
    )

    write_json_report(report, output_dir / "report.json")
    write_annotated_image(analysis_path, segments, output_dir / "annotated.jpg")
    return report


def _image_shape(path: Path) -> tuple[int, int]:
    cv2 = _import_cv2()
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Could not load image: {path}")
    height, width = image.shape[:2]
    return height, width


def _import_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for pipeline execution. Install opencv-python.") from exc
    return cv2
