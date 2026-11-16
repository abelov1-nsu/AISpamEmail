"""Filesystem layout owned by the dataset module."""

from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = MODULE_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = MODULE_ROOT / "reports"
TEMP_IMAGES_DIR = DATA_DIR / ".tmp_images"


def ensure_output_directories() -> None:
    """Create only generated-output directories required by a script."""
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
