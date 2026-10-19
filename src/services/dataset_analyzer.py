"""Services for batch analysis and simple evaluation of EML datasets."""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..parsing.email_parser import EmailParser
from ..schemas import AnalysisResult
from ..utils.text import safe_mean
from .email_analyzer import EmailAnalyzer
from .reporting import save_json


class DatasetLoader:
    """Locate EML files and load plain text fixtures."""

    def load_directory(self, directory: Path) -> list[Path]:
        """Return all EML files below ``directory`` in stable order."""
        return sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() == ".eml"
        )

    def load_text_file(self, path: Path) -> dict[str, Any]:
        """Wrap a text fixture in the parser's email dictionary format."""
        return {
            "email_id": path.name,
            "headers": {},
            "text": path.read_text(encoding="utf-8", errors="replace"),
            "html": "",
            "attachments": [],
        }


class DatasetEvaluator:
    """Compare analyzer judgements against known labels."""

    def evaluate(
        self,
        results: list[AnalysisResult],
        labels: dict[str, str],
    ) -> dict[str, Any]:
        rows = [
            {
                "id": result.email_id,
                "truth": labels[result.email_id],
                "prediction": result.judgement,
            }
            for result in results
            if result.email_id in labels
        ]
        correct = sum(row["truth"] == row["prediction"] for row in rows)
        confusion = Counter(
            (row["truth"], row["prediction"])
            for row in rows
        )
        return {
            "samples": len(rows),
            "correct": correct,
            "accuracy": correct / len(rows) if rows else 0.0,
            "confusion": {str(key): value for key, value in confusion.items()},
        }


def analyze_dataset(
    input_directory: Path,
    output_directory: Path,
) -> None:
    """Analyze every EML in a directory and save per-file JSON reports."""
    parser = EmailParser()
    analyzer = EmailAnalyzer()
    files = DatasetLoader().load_directory(input_directory)
    results: list[AnalysisResult] = []

    print(f"Found {len(files)} .eml files")

    for index, path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {path.name}")
        try:
            result = analyzer.analyze(parser.parse_file(path))
            results.append(result)
            save_json(asdict(result), output_directory / f"{path.stem}.json")
            print(
                f"    spam:        {result.spam_score:.2f}\n"
                f"    phishing:    {result.phishing_score:.2f}\n"
                f"    AI-assisted: {result.ai_assisted_score:.2f}\n"
                f"    judgement:   {result.judgement}"
            )
        except Exception as exc:
            print(f"    ERROR: {exc}", file=sys.stderr)

    summary = {
        "emails_analyzed": len(results),
        "judgements": dict(Counter(result.judgement for result in results)),
        "average_scores": {
            "spam": safe_mean([result.spam_score for result in results]),
            "phishing": safe_mean([result.phishing_score for result in results]),
            "ai_assisted": safe_mean(
                [result.ai_assisted_score for result in results]
            ),
        },
    }
    save_json(summary, output_directory / "summary.json")
    print("\n========== SUMMARY ==========")
    print(json.dumps(summary, indent=2))


__all__ = ["DatasetLoader", "DatasetEvaluator", "analyze_dataset"]
