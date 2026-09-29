"""
pipeline.py

Robust orchestration layer for email AI-content analysis.

Current capabilities:
    - Parses .eml files.
    - Extracts plain text and HTML.
    - Extracts MIME image attachments.
    - Extracts data-URI images from HTML.
    - Runs the local image detector through the project's image_analyzer module.
    - Optionally runs a Qwen/OpenAI-compatible explanation layer through image_analyzer.
    - Produces a timestamped JSON report.
    - Keeps processing when an individual artifact fails.
    - Cleans temporary files even when processing raises an exception.

Future extension points are marked with TODOs:
    - text analysis
    - PDF/DOCX/etc. extraction
    - attachment recursion
    - OCR
    - finer-grained text segmentation
    - email-level aggregation
"""

from __future__ import annotations

import base64
import binascii
import email
import email.policy
import html
import json
import logging
import mimetypes
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from image_analyzer import analyze_image


# ============================================================
# CONFIGURATION
# ============================================================

CONFIG: dict[str, Any] = {
    # Local detector
    "image_analyzer_enabled": True,

    # Optional external/local LLM.
    # The actual provider implementation belongs in image_analyzer.
    "use_llm": True,
    "llm_provider": "openai",

    # These are passed to image_analyzer where supported.
    "ollama_model": "llava:7b",
    "openai_model": "gpt-4o-mini",

    # Detector behavior.
    "confidence_low": 0.20,
    "confidence_high": 0.80,

    # Output.
    "output_dir": "forensic_reports",

    # Extraction limits.
    # These protect the pipeline from pathological/malicious messages.
    "max_html_inline_images": 100,
    "max_image_bytes": 25 * 1024 * 1024,
    "max_total_extracted_bytes": 200 * 1024 * 1024,

    # Keep temporary extracted files until the end of one analysis.
    "keep_temp_files": False,
}


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("email_pipeline")


def configure_logging() -> None:
    """Configure a useful default logger without touching application logging."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(levelname)s] %(message)s",
        )


# ============================================================
# HELPERS
# ============================================================

def utc_timestamp() -> str:
    """Filesystem-friendly UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_filename(name: str, fallback: str = "unnamed") -> str:
    """
    Make an email/attachment name safe for use in a filesystem path.

    This is deliberately conservative: path separators and control characters
    are removed rather than interpreted.
    """
    name = Path(name or fallback).name
    name = re.sub(r"[\x00-\x1f\x7f]", "_", name)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = name.strip(" .")
    return name or fallback


def safe_subject(subject: str) -> str:
    """Create a compact safe name from the email subject."""
    subject = str(subject or "").strip()
    subject = re.sub(r"\s+", " ", subject)
    subject = safe_filename(subject, "no_subject")
    return subject[:100]


def make_report_path(
    output_dir: str | Path,
    subject: str,
    extension: str = ".json",
) -> Path:
    """Build a unique timestamped report path containing the email subject."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = utc_timestamp()
    subject_part = safe_subject(subject)

    return output_dir / f"{timestamp}_{subject_part}_{uuid.uuid4().hex[:8]}{extension}"


def artifact_error(
    artifact_id: str,
    artifact_type: str,
    error: Exception | str,
    *,
    source: str | None = None,
) -> dict[str, Any]:
    """Create a standardized non-fatal artifact failure."""
    result = {
        "id": artifact_id,
        "type": artifact_type,
        "status": "error",
        "ruling": {
            "label": "not_analyzed",
            "score": None,
        },
        "error": str(error),
    }

    if source is not None:
        result["source"] = source

    return result


def artifact_skipped(
    artifact_id: str,
    artifact_type: str,
    reason: str,
    *,
    source: str | None = None,
) -> dict[str, Any]:
    """Create a standardized skipped-artifact result."""
    result = {
        "id": artifact_id,
        "type": artifact_type,
        "status": "skipped",
        "ruling": {
            "label": "not_analyzed",
            "score": None,
        },
        "reason": reason,
    }

    if source is not None:
        result["source"] = source

    return result


# ============================================================
# INLINE IMAGE EXTRACTION
# ============================================================

_DATA_URI_PATTERN = re.compile(
    r"data:image/(?P<ext>png|jpeg|jpg|gif|webp|bmp);base64,"
    r"(?P<data>[A-Za-z0-9+/=\s]+)",
    re.IGNORECASE,
)


def _extract_inline_base64(
    html_content: str,
    temp_dir: Path,
    *,
    max_images: int,
    max_image_bytes: int,
    total_bytes_used: int,
) -> tuple[list[Path], list[dict[str, Any]], int]:
    """
    Extract data:image/... base64 images from HTML.

    Malformed/oversized images are recorded as failures instead of stopping
    the complete email analysis.
    """
    image_paths: list[Path] = []
    errors: list[dict[str, Any]] = []

    matches = list(_DATA_URI_PATTERN.finditer(html_content))

    for index, match in enumerate(matches[:max_images]):
        artifact_id = f"inline-image-{index + 1:04d}"

        try:
            raw = re.sub(r"\s+", "", match.group("data"))
            data = base64.b64decode(raw, validate=True)

            if len(data) > max_image_bytes:
                raise ValueError(
                    f"inline image exceeds limit of {max_image_bytes} bytes"
                )

            if total_bytes_used + len(data) > CONFIG["max_total_extracted_bytes"]:
                raise ValueError("total extracted attachment limit exceeded")

            ext = match.group("ext").lower()
            if ext == "jpg":
                ext = "jpeg"

            path = temp_dir / f"{artifact_id}.{ext}"
            path.write_bytes(data)

            image_paths.append(path)
            total_bytes_used += len(data)

        except (binascii.Error, ValueError, OSError) as exc:
            errors.append(
                artifact_error(
                    artifact_id,
                    "image",
                    exc,
                    source="html_data_uri",
                )
            )

    if len(matches) > max_images:
        errors.append(
            artifact_skipped(
                f"inline-image-limit-{uuid.uuid4().hex[:8]}",
                "image",
                f"inline image limit reached; {len(matches) - max_images} "
                "additional images were not extracted",
                source="html_data_uri",
            )
        )

    return image_paths, errors, total_bytes_used


# ============================================================
# EMAIL PARSING
# ============================================================

def parse_eml(eml_path: str | Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Parse an EML into metadata, text, HTML and extracted image files.

    Extraction failures are recorded rather than aborting the entire message.
    """
    config = config or CONFIG
    eml_path = Path(eml_path)

    if not eml_path.is_file():
        raise FileNotFoundError(f"EML file not found: {eml_path}")

    temp_dir = Path(tempfile.mkdtemp(prefix="eml_forensics_"))

    parsed: dict[str, Any] = {
        "metadata": {},
        "text_body": "",
        "html_body": "",
        "image_paths": [],
        "extraction_errors": [],
        "temp_dir": str(temp_dir),
        "source_path": str(eml_path.resolve()),
    }

    total_extracted_bytes = 0

    try:
        with eml_path.open("rb") as f:
            msg = email.message_from_binary_file(
                f,
                policy=email.policy.default,
            )

        parsed["metadata"] = {
            "subject": str(msg.get("subject", "")),
            "from": str(msg.get("from", "")),
            "to": str(msg.get("to", "")),
            "cc": str(msg.get("cc", "")),
            "date": str(msg.get("date", "")),
            "message_id": str(msg.get("message-id", "")),
        }

        image_index = 0

        for part in msg.walk():
            content_type = part.get_content_type()

            # --------------------------------------------
            # Text
            # --------------------------------------------
            if content_type == "text/plain" and not parsed["text_body"]:
                try:
                    parsed["text_body"] = part.get_content()
                except Exception as exc:
                    parsed["extraction_errors"].append(
                        artifact_error(
                            "email-text-001",
                            "text",
                            exc,
                            source="text/plain",
                        )
                    )

            elif content_type == "text/html" and not parsed["html_body"]:
                try:
                    parsed["html_body"] = part.get_content()
                except Exception as exc:
                    parsed["extraction_errors"].append(
                        artifact_error(
                            "email-html-001",
                            "html",
                            exc,
                            source="text/html",
                        )
                    )

            # --------------------------------------------
            # Image attachments / inline MIME images
            # --------------------------------------------
            if part.get_content_maintype() == "image":
                image_index += 1
                artifact_id = f"image-{image_index:04d}"

                try:
                    img_data = part.get_payload(decode=True)

                    if not img_data:
                        raise ValueError("image MIME part contained no decoded data")

                    if len(img_data) > config["max_image_bytes"]:
                        raise ValueError(
                            f"image exceeds limit of {config['max_image_bytes']} bytes"
                        )

                    if (
                        total_extracted_bytes + len(img_data)
                        > config["max_total_extracted_bytes"]
                    ):
                        raise ValueError(
                            "total extracted attachment limit exceeded"
                        )

                    filename = safe_filename(
                        part.get_filename()
                        or f"{artifact_id}.{mimetypes.guess_extension(content_type) or '.bin'}"
                    )

                    img_path = temp_dir / f"{artifact_id}_{filename}"
                    img_path.write_bytes(img_data)

                    parsed["image_paths"].append(img_path)
                    total_extracted_bytes += len(img_data)

                except Exception as exc:
                    parsed["extraction_errors"].append(
                        artifact_error(
                            artifact_id,
                            "image",
                            exc,
                            source="mime_image",
                        )
                    )

        # HTML data URIs.
        if parsed["html_body"]:
            paths, errors, total_extracted_bytes = _extract_inline_base64(
                parsed["html_body"],
                temp_dir,
                max_images=config["max_html_inline_images"],
                max_image_bytes=config["max_image_bytes"],
                total_bytes_used=total_extracted_bytes,
            )

            parsed["image_paths"].extend(paths)
            parsed["extraction_errors"].extend(errors)

        return parsed

    except Exception:
        # If parsing itself fails, the caller gets the original exception,
        # but the temporary extraction directory is still removed.
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


# ============================================================
# TEXT PREPARATION
# ============================================================

def html_to_visible_text(html_body: str) -> str:
    """
    Basic HTML-to-text conversion.

    This is intentionally not the final text-analysis implementation.
    A proper HTML parser/sanitizer can replace this later.
    """
    if not html_body:
        return ""

    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_body)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def build_text_artifacts(email_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Create text artifacts while preserving the distinction between plain and
    HTML-derived text.

    TODO:
        Replace this with paragraph/sentence/semantic segmentation and the
        future text AI detector.
    """
    artifacts: list[dict[str, Any]] = []

    plain = email_data.get("text_body", "").strip()
    html_body = email_data.get("html_body", "").strip()

    if plain:
        artifacts.append(
            {
                "id": "text-plain-001",
                "type": "text",
                "source": "email.text/plain",
                "content": plain,
                "status": "pending_analysis",
            }
        )

    if html_body:
        visible = html_to_visible_text(html_body)

        if visible:
            artifacts.append(
                {
                    "id": "text-html-001",
                    "type": "text",
                    "source": "email.text/html",
                    "content": visible,
                    "status": "pending_analysis",
                }
            )

    return artifacts


# ============================================================
# IMAGE ANALYSIS
# ============================================================

def analyze_images(
    image_paths: list[Path],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Analyze each image independently.

    One broken image/API call cannot prevent subsequent images from being
    processed.
    """
    results: list[dict[str, Any]] = []

    if not image_paths:
        return results

    if not config.get("image_analyzer_enabled", True):
        for index, path in enumerate(image_paths, start=1):
            results.append(
                artifact_skipped(
                    f"image-{index:04d}",
                    "image",
                    "image analyzer disabled",
                    source=str(path.name),
                )
            )
        return results

    for index, image_path in enumerate(image_paths, start=1):
        artifact_id = f"image-{index:04d}"

        try:
            logger.info("Analyzing image: %s", image_path.name)

            # Keep compatibility with the existing image_analyzer interface:
            # analyze_image(image_path, CONFIG)
            result = analyze_image(str(image_path), config)

            if not isinstance(result, dict):
                result = {
                    "raw_result": result,
                }

            results.append(
                {
                    "id": artifact_id,
                    "type": "image",
                    "source": image_path.name,
                    "status": "analyzed",
                    "ruling": result,
                }
            )

        except Exception as exc:
            logger.exception("Image analysis failed for %s", image_path)
            results.append(
                artifact_error(
                    artifact_id,
                    "image",
                    exc,
                    source=image_path.name,
                )
            )

    return results


# ============================================================
# TEXT ANALYSIS PLACEHOLDER
# ============================================================

def analyze_text_artifacts(
    text_artifacts: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Placeholder for the future text-analysis detector.

    TODO:
        - Add a local text classifier.
        - Split paragraphs/sentences into smaller artifacts.
        - Preserve character offsets.
        - Optionally analyze quoted/replied email sections separately.
        - Add an optional LLM explanation layer.
    """
    results: list[dict[str, Any]] = []

    for artifact in text_artifacts:
        result = dict(artifact)

        # For now we deliberately do NOT call anything.
        result["status"] = "not_implemented"
        result["ruling"] = {
            "label": "not_analyzed",
            "score": None,
        }

        # Never include full email text in the final report by default.
        result.pop("content", None)

        results.append(result)

    return results


# ============================================================
# ATTACHMENT EXTENSION POINT
# ============================================================

def process_non_image_attachments(
    eml_path: str | Path,
) -> list[dict[str, Any]]:
    """
    Future attachment extractor.

    TODO:
        - PDF -> text + images
        - DOCX -> paragraphs + embedded images
        - XLSX -> textual/cell artifacts
        - PPTX -> slide text + images
        - ZIP -> recursively inspect permitted file types
        - OCR for scanned documents
    """
    return []


# ============================================================
# OVERALL AGGREGATION
# ============================================================

def determine_overall_ruling(
    image_results: list[dict[str, Any]],
    text_results: list[dict[str, Any]],
    attachment_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Conservative email-level aggregation.

    The email-level label describes CONTENT FOUND IN THE EMAIL; it does not
    claim that the entire email was generated by AI.

    Current image-only logic:
        - any strong AI image -> contains_ai_content
        - otherwise, if analyzed images exist -> no_ai_detected_in_images
        - otherwise -> insufficient_evidence

    TODO:
        Add text detector evidence and weighted/typed aggregation.
    """
    analyzed_images = [
        item for item in image_results
        if item.get("status") == "analyzed"
    ]

    ai_scores: list[float] = []

    for item in analyzed_images:
        ruling = item.get("ruling", {})

        # Current image_analyzer compatibility.
        score = ruling.get("final_confidence")

        if isinstance(score, (int, float)):
            verdict = str(ruling.get("final_verdict", "")).upper()

            if verdict == "AI":
                ai_scores.append(float(score))

    if ai_scores:
        strongest = max(ai_scores)
        return {
            "label": "contains_ai_content",
            "strongest_ai_score": strongest,
            "basis": "image_detector",
        }

    if analyzed_images:
        return {
            "label": "no_ai_detected_in_analyzed_images",
            "strongest_ai_score": 0.0,
            "basis": "image_detector",
        }

    return {
        "label": "insufficient_evidence",
        "strongest_ai_score": None,
        "basis": "no_successfully_analyzed_artifacts",
    }


# ============================================================
# MAIN PIPELINE
# ============================================================

def process_email(
    eml_path: str | Path,
    output_dir: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Analyze an EML and save a timestamped JSON report.

    The function attempts to produce a report even when individual artifacts
    fail. Fatal failures are limited to failures that prevent the email itself
    from being parsed.
    """
    configure_logging()

    config = {**CONFIG, **(config or {})}
    eml_path = Path(eml_path)

    logger.info("Starting forensic pipeline: %s", eml_path)

    started = datetime.now(timezone.utc)

    email_data: dict[str, Any] | None = None

    try:
        email_data = parse_eml(eml_path, config)

        metadata = email_data["metadata"]
        subject = metadata.get("subject", "")

        report: dict[str, Any] = {
            "schema_version": "1.0",
            "analysis": {
                "analysis_id": str(uuid.uuid4()),
                "started_at": started.isoformat(),
                "completed_at": None,
                "status": "processing",
            },
            "input": {
                "filename": eml_path.name,
                "absolute_path": str(eml_path.resolve()),
            },
            "email_metadata": metadata,
            "artifacts": [],
            "errors": list(email_data.get("extraction_errors", [])),
            "ruling": None,
            "extensions": {
                "text_analysis": "not_implemented",
                "document_analysis": "not_implemented",
                "ocr": "not_implemented",
                "fine_grained_text_segmentation": "not_implemented",
            },
        }

        # ----------------------------------------------------
        # TEXT
        # ----------------------------------------------------
        text_artifacts = build_text_artifacts(email_data)
        text_results = analyze_text_artifacts(text_artifacts, config)
        report["artifacts"].extend(text_results)

        # ----------------------------------------------------
        # IMAGES
        # ----------------------------------------------------
        image_results = analyze_images(
            email_data.get("image_paths", []),
            config,
        )
        report["artifacts"].extend(image_results)

        # ----------------------------------------------------
        # OTHER ATTACHMENTS
        # ----------------------------------------------------
        try:
            attachment_results = process_non_image_attachments(eml_path)
        except Exception as exc:
            logger.exception("Non-image attachment processing failed")
            attachment_results = [
                artifact_error(
                    "attachment-processing",
                    "attachment",
                    exc,
                    source=eml_path.name,
                )
            ]

        report["artifacts"].extend(attachment_results)

        # ----------------------------------------------------
        # OVERALL RULING
        # ----------------------------------------------------
        report["ruling"] = determine_overall_ruling(
            image_results,
            text_results,
            attachment_results,
        )

        report["analysis"]["status"] = "completed"

    except Exception as exc:
        # Fatal only at the email-level. We still try to save a report.
        logger.exception("Fatal email processing failure")

        report = {
            "schema_version": "1.0",
            "analysis": {
                "analysis_id": str(uuid.uuid4()),
                "started_at": started.isoformat(),
                "completed_at": None,
                "status": "failed",
            },
            "input": {
                "filename": eml_path.name,
                "absolute_path": str(eml_path.resolve()),
            },
            "email_metadata": {},
            "artifacts": [],
            "errors": [
                artifact_error(
                    "email-processing",
                    "email",
                    exc,
                    source=eml_path.name,
                )
            ],
            "ruling": {
                "label": "processing_failed",
                "strongest_ai_score": None,
                "basis": "email_parser_or_pipeline_failure",
            },
            "extensions": {},
        }

    finally:
        # ----------------------------------------------------
        # CLEANUP
        # ----------------------------------------------------
        if email_data and email_data.get("temp_dir"):
            temp_dir = Path(email_data["temp_dir"])

            if config.get("keep_temp_files", False):
                logger.info("Temporary extraction retained: %s", temp_dir)
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)

    completed = datetime.now(timezone.utc)
    report["analysis"]["completed_at"] = completed.isoformat()

    # --------------------------------------------------------
    # SAVE REPORT
    # --------------------------------------------------------
    final_output_dir = output_dir or config["output_dir"]
    report_path = make_report_path(
        final_output_dir,
        report.get("email_metadata", {}).get("subject", ""),
    )

    # Atomic-ish write: write beside the final file and replace it.
    temp_report = report_path.with_suffix(".tmp")

    try:
        with temp_report.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        os.replace(temp_report, report_path)

    except Exception:
        try:
            temp_report.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    report["output"] = {
        "report_path": str(report_path.resolve()),
    }

    logger.info("Pipeline complete: %s", report_path)

    return report


# ============================================================
# COMMAND LINE ENTRY POINT
# ============================================================

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze an EML for AI-generated content."
    )
    parser.add_argument("eml", help="Path to the .eml file")
    parser.add_argument(
        "-o",
        "--output-dir",
        default=CONFIG["output_dir"],
        help="Directory for timestamped JSON reports",
    )

    args = parser.parse_args()

    try:
        report = process_email(args.eml, args.output_dir)

        print(json.dumps(
            {
                "status": report["analysis"]["status"],
                "ruling": report["ruling"],
                "report": report["output"]["report_path"],
            },
            indent=2,
            ensure_ascii=False,
        ))

        return 0 if report["analysis"]["status"] == "completed" else 1

    except Exception as exc:
        logger.exception("Could not produce a report: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
