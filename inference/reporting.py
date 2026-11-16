"""Report paths, report persistence and conservative evidence aggregation."""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_filename(name: str, fallback: str = "unnamed") -> str:
    name = Path(name or fallback).name
    name = re.sub(r"[\x00-\x1f\x7f]", "_", name)
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip(" .")
    return name or fallback


def make_report_path(output_dir: str | Path, subject: str) -> Path:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    subject = safe_filename(re.sub(r"\s+", " ", str(subject or "").strip()), "no_subject")[:100]
    return target_dir / f"{utc_timestamp()}_{subject}_{uuid.uuid4().hex[:8]}.json"


def save_report(report: dict[str, Any], output_dir: str | Path) -> Path:
    path = make_report_path(output_dir, report.get("email_metadata", {}).get("subject", ""))
    temporary_path = path.with_suffix(".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as destination:
            json.dump(report, destination, indent=2, ensure_ascii=False)
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return path.resolve()


def determine_overall_ruling(
    image_results: list[dict[str, Any]], text_results: list[dict[str, Any]], attachment_results: list[dict[str, Any]]
) -> dict[str, Any]:
    """Aggregate only evidence the current implementation actually produces."""
    analyzed_images = [item for item in image_results if item.get("status") == "analyzed"]
    ai_scores: list[float] = []
    for item in analyzed_images:
        classification = item.get("ruling", {}).get("classification", {})
        if classification.get("label") == "ai" and isinstance(classification.get("score"), (int, float)):
            ai_scores.append(float(classification["score"]))
    if ai_scores:
        return {"label": "contains_ai_content", "strongest_ai_score": max(ai_scores), "basis": "image_detector"}
    if analyzed_images:
        return {"label": "no_ai_detected_in_analyzed_images", "strongest_ai_score": 0.0, "basis": "image_detector"}
    return {"label": "insufficient_evidence", "strongest_ai_score": None, "basis": "no_successfully_analyzed_artifacts"}
