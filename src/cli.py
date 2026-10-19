"""Command-line interface for the multi-signal email analyzer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .services.dataset_analyzer import analyze_dataset
from .services.email_analyzer import EmailAnalyzer


def _demo_messages() -> list[dict]:
    """Return small deterministic examples used by the ``--demo`` command."""
    return [
        {
            "email_id": "example_legitimate",
            "headers": {},
            "text": (
                "Hello everyone. I've uploaded the lecture materials for "
                "Monday. Best regards, Alex."
            ),
            "html": "",
            "attachments": [],
        },
        {
            "email_id": "example_spam",
            "headers": {},
            "text": (
                "URGENT!!! Congratulations! Click here immediately to "
                "claim your free reward. Act now!!!"
            ),
            "html": "<a href='https://example.xyz/verify'>Click here</a>",
            "attachments": [],
        },
    ]


def run_demo() -> None:
    """Analyze and print the built-in demonstration messages."""
    analyzer = EmailAnalyzer()

    for email in _demo_messages():
        result = analyzer.analyze(email)
        print("\n" + "=" * 70)
        print(json.dumps(result.__dict__, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Multi-signal email analyzer prototype",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        help="Directory containing .eml files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("analysis_results"),
        help="Directory for JSON analysis results",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run built-in synthetic examples",
    )
    return parser


def main() -> int:
    """Dispatch the selected command and return its exit status."""
    args = build_parser().parse_args()

    if args.demo:
        run_demo()
        return 0

    if args.dataset is None:
        print("No dataset supplied. Use --demo or --dataset <directory>.")
        return 0

    analyze_dataset(args.dataset, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
