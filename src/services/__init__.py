"""Application services for single-email and batch analysis."""

from .dataset_analyzer import DatasetEvaluator, DatasetLoader, analyze_dataset
from .email_analyzer import EmailAnalyzer
from .reporting import save_json

__all__ = [
    "EmailAnalyzer",
    "DatasetLoader",
    "DatasetEvaluator",
    "analyze_dataset",
    "save_json",
]
