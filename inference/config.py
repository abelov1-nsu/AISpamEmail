"""Configuration defaults for the forensic EML pipeline."""

from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CONFIG: dict[str, Any] = {
    "image_analyzer_enabled": True,
    "image_checkpoint": str(
        PROJECT_ROOT / "models" / "checkpoints" / "ai_image_detector_mobilenet_v3_small.pth"
    ),
    "image_architecture": "mobilenet_v3_small",
    "image_threshold": 0.5,
    "output_dir": "forensic_reports",
    "max_html_inline_images": 100,
    "max_image_bytes": 25 * 1024 * 1024,
    "max_total_extracted_bytes": 200 * 1024 * 1024,
    "keep_temp_files": False,
}


def merge_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a fresh effective configuration without mutating defaults."""
    return {**DEFAULT_CONFIG, **(overrides or {})}
