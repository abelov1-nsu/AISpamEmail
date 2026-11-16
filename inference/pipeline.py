"""Backward-compatible CLI entry point for the forensic EML pipeline."""

import argparse
import json
import logging
import sys
from pathlib import Path

# Support both ``python -m inference.pipeline`` from the repository root and
# the legacy ``python inference/pipeline.py`` invocation.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inference.config import DEFAULT_CONFIG
from inference.service import process_email


# Retained for callers that previously imported CONFIG from this module.
CONFIG = DEFAULT_CONFIG


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze an EML for AI-generated content.")
    parser.add_argument("eml", help="Path to the .eml file")
    parser.add_argument("-o", "--output-dir", default=CONFIG["output_dir"], help="Directory for timestamped JSON reports")
    args = parser.parse_args()
    try:
        report = process_email(args.eml, args.output_dir)
        # ASCII escaping keeps the CLI usable in legacy Windows code pages;
        # the persisted forensic report itself remains UTF-8.
        print(json.dumps({"status": report["analysis"]["status"], "ruling": report["ruling"], "report": report["output"]["report_path"]}, indent=2, ensure_ascii=True))
        return 0 if report["analysis"]["status"] == "completed" else 1
    except Exception as exc:
        logging.getLogger("email_pipeline").exception("Could not produce a report: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
