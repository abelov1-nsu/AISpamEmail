"""Heuristic EML batch-analysis package."""

from .application import EmailAnalyzer, EmailParser, analyze_dataset, run_demo

__all__ = ["EmailAnalyzer", "EmailParser", "analyze_dataset", "run_demo"]
