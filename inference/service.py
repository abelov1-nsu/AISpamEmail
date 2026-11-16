"""Application service orchestrating one forensic EML analysis."""

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inference.artifacts import artifact_error
from inference.config import merge_config
from inference.extraction import parse_eml
from inference.image_analysis import analyze_images
from inference.reporting import determine_overall_ruling, save_report
from inference.text_artifacts import analyze_text_artifacts, build_text_artifacts


logger = logging.getLogger("email_pipeline")


def configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def process_non_image_attachments(eml_path: str | Path) -> list[dict[str, Any]]:
    """Extension seam for PDF/DOCX/XLSX/PPTX/ZIP extraction; currently empty."""
    return []


def _new_report(eml_path: Path, started: datetime, email_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "analysis": {"analysis_id": str(uuid.uuid4()), "started_at": started.isoformat(), "completed_at": None, "status": "processing"},
        "input": {"filename": eml_path.name, "absolute_path": str(eml_path.resolve())},
        "email_metadata": email_data["metadata"], "artifacts": [],
        "errors": list(email_data.get("extraction_errors", [])), "ruling": None,
        "extensions": {"text_analysis": "not_implemented", "document_analysis": "not_implemented", "ocr": "not_implemented", "fine_grained_text_segmentation": "not_implemented"},
    }


def process_email(eml_path: str | Path, output_dir: str | Path | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Analyze one EML, retain partial failures, and atomically persist its report."""
    configure_logging()
    effective_config = merge_config(config)
    eml_path = Path(eml_path)
    started = datetime.now(timezone.utc)
    email_data: dict[str, Any] | None = None
    try:
        email_data = parse_eml(eml_path, effective_config)
        report = _new_report(eml_path, started, email_data)
        text_results = analyze_text_artifacts(build_text_artifacts(email_data), effective_config)
        image_results = analyze_images(email_data.get("image_paths", []), effective_config)
        try:
            attachment_results = process_non_image_attachments(eml_path)
        except Exception as exc:
            logger.exception("Non-image attachment processing failed")
            attachment_results = [artifact_error("attachment-processing", "attachment", exc, source=eml_path.name)]
        report["artifacts"].extend(text_results)
        report["artifacts"].extend(image_results)
        report["artifacts"].extend(attachment_results)
        report["ruling"] = determine_overall_ruling(image_results, text_results, attachment_results)
        report["analysis"]["status"] = "completed"
    except Exception as exc:
        logger.exception("Fatal email processing failure")
        report = {
            "schema_version": "1.0",
            "analysis": {"analysis_id": str(uuid.uuid4()), "started_at": started.isoformat(), "completed_at": None, "status": "failed"},
            "input": {"filename": eml_path.name, "absolute_path": str(eml_path.resolve())},
            "email_metadata": {}, "artifacts": [],
            "errors": [artifact_error("email-processing", "email", exc, source=eml_path.name)],
            "ruling": {"label": "processing_failed", "strongest_ai_score": None, "basis": "email_parser_or_pipeline_failure"},
            "extensions": {},
        }
    finally:
        if email_data and email_data.get("temp_dir") and not effective_config.get("keep_temp_files", False):
            shutil.rmtree(email_data["temp_dir"], ignore_errors=True)
    report["analysis"]["completed_at"] = datetime.now(timezone.utc).isoformat()
    report_path = save_report(report, output_dir or effective_config["output_dir"])
    report["output"] = {"report_path": str(report_path)}
    logger.info("Pipeline complete: %s", report_path)
    return report
