"""Adapter between extracted image files and the local image detector."""

import logging
from pathlib import Path
from typing import Any, Callable

from inference.artifacts import artifact_error, artifact_skipped


logger = logging.getLogger("email_pipeline")
ImageAnalyzer = Callable[[Path, dict[str, Any]], dict[str, Any]]


def build_local_image_analyzer(config: dict[str, Any]) -> ImageAnalyzer:
    """Load one checkpoint and expose the pipeline's path/config callable contract."""
    from inference.image_analyzer import ImageDetector, analyze_image

    detector = ImageDetector(
        checkpoint=config["image_checkpoint"],
        architecture=config["image_architecture"],
        threshold=config["image_threshold"],
    )

    def analyze(path: Path, _: dict[str, Any]) -> dict[str, Any]:
        return analyze_image(detector, path)

    return analyze


def analyze_images(image_paths: list[Path], config: dict[str, Any]) -> list[dict[str, Any]]:
    if not image_paths:
        return []
    if not config.get("image_analyzer_enabled", True):
        return [artifact_skipped(f"image-{index:04d}", "image", "image analyzer disabled", source=path.name)
                for index, path in enumerate(image_paths, start=1)]
    try:
        analyzer: ImageAnalyzer = config.get("image_analyzer") or build_local_image_analyzer(config)
    except Exception as exc:
        return [artifact_error(f"image-{index:04d}", "image", exc, source=path.name)
                for index, path in enumerate(image_paths, start=1)]
    results: list[dict[str, Any]] = []
    for index, image_path in enumerate(image_paths, start=1):
        artifact_id = f"image-{index:04d}"
        try:
            logger.info("Analyzing image: %s", image_path.name)
            result = analyzer(image_path, config)
            results.append({"id": artifact_id, "type": "image", "source": image_path.name,
                            "status": "analyzed", "ruling": result if isinstance(result, dict) else {"raw_result": result}})
        except Exception as exc:
            logger.exception("Image analysis failed for %s", image_path)
            results.append(artifact_error(artifact_id, "image", exc, source=image_path.name))
    return results
