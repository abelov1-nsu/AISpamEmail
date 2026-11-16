"""Command-line adapter for heuristic email batch analysis."""

import argparse
from pathlib import Path

from .application import analyze_dataset, run_demo


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-signal email analyzer prototype")
    parser.add_argument("--dataset", type=Path, help="Directory containing .eml files")
    parser.add_argument("--output", type=Path, default=Path("analysis_results"), help="Directory for JSON results")
    parser.add_argument("--demo", action="store_true", help="Run built-in synthetic examples")
    parser.add_argument("--use-ai", action="store_true", help="Enable Open WebUI segmentation + AI judge")
    args = parser.parse_args()
    if args.demo:
        run_demo(use_ai=args.use_ai)
        return 0
    if args.dataset is None:
        parser.error("use --demo or --dataset <directory>")
    analyze_dataset(args.dataset, args.output, use_ai=args.use_ai)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

