"""Central configuration and filesystem paths for the dataset pipeline.

Values may be overridden in ``dataset/.env``. Environment variables always
take precedence over values from that file, which is convenient for CI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DATASET_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DATASET_ROOT.parent


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE pairs without an additional dependency."""
    if not path.is_file():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv(DATASET_ROOT / ".env")


def _path(variable: str, default: Path) -> Path:
    """Return an absolute configured path, resolving relative values to root."""
    value = os.getenv(variable)
    path = Path(value) if value else default
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


@dataclass(frozen=True)
class DatasetPaths:
    raw_spamassassin: Path
    raw_ai_spam: tuple[Path, ...]
    raw_partially_ai: Path
    raw_enron: Path
    processed_dataset: Path
    processed_dataset_clean: Path
    feature_table: Path
    label_table: Path
    temporary_images: Path
    baseline_results: Path
    shap_summary: Path


PATHS = DatasetPaths(
    raw_spamassassin=_path(
        "DATASET_RAW_SPAMASSASSIN", DATASET_ROOT / "data/raw/spamassassin/dataset_spamassassin.csv"
    ),
    raw_ai_spam=(
        _path("DATASET_RAW_AI_SPAM_1", DATASET_ROOT / "data/raw/ai_spam/dataset_ai_spam.csv"),
        _path("DATASET_RAW_AI_SPAM_2", DATASET_ROOT / "data/raw/ai_spam/dataset_ai_spam_2.csv"),
    ),
    raw_partially_ai=_path(
        "DATASET_RAW_PARTIALLY_AI", DATASET_ROOT / "data/raw/partially_ai/dataset_ai_spam_partial.json"
    ),
    raw_enron=_path(
        "DATASET_RAW_ENRON", DATASET_ROOT / "data/raw/enron/enron_spam_data.csv"
    ),
    processed_dataset=_path(
        "DATASET_PROCESSED_DATASET", DATASET_ROOT / "data/processed/dataset.csv"
    ),
    processed_dataset_clean=_path(
        "DATASET_PROCESSED_DATASET_CLEAN", DATASET_ROOT / "data/processed/dataset_clean.csv"
    ),
    feature_table=_path(
        "DATASET_FEATURE_TABLE", DATASET_ROOT / "data/interim/features.csv"
    ),
    label_table=_path(
        "DATASET_LABEL_TABLE", DATASET_ROOT / "data/interim/labels.csv"
    ),
    temporary_images=_path(
        "DATASET_TEMP_IMAGES", DATASET_ROOT / "data/external/downloaded_images"
    ),
    baseline_results=_path(
        "DATASET_BASELINE_RESULTS", DATASET_ROOT / "reports/metrics/baseline_results.txt"
    ),
    shap_summary=_path(
        "DATASET_SHAP_SUMMARY", DATASET_ROOT / "reports/explanations/shap_summary.png"
    ),
)
