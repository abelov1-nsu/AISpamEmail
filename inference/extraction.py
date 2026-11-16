"""Safe EML parsing and image extraction."""

import base64
import binascii
import email
import email.policy
import mimetypes
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

from inference.artifacts import artifact_error, artifact_skipped
from inference.reporting import safe_filename


DATA_URI_PATTERN = re.compile(
    r"data:image/(?P<ext>png|jpeg|jpg|gif|webp|bmp);base64,"
    r"(?P<data>[A-Za-z0-9+/=\s]+)",
    re.IGNORECASE,
)


def extract_inline_images(
    html_content: str, temp_dir: Path, config: dict[str, Any], total_bytes_used: int
) -> tuple[list[Path], list[dict[str, Any]], int]:
    image_paths: list[Path] = []
    errors: list[dict[str, Any]] = []
    matches = list(DATA_URI_PATTERN.finditer(html_content))
    max_images = config["max_html_inline_images"]
    for index, match in enumerate(matches[:max_images], start=1):
        artifact_id = f"inline-image-{index:04d}"
        try:
            data = base64.b64decode(re.sub(r"\s+", "", match.group("data")), validate=True)
            if len(data) > config["max_image_bytes"]:
                raise ValueError(f"inline image exceeds limit of {config['max_image_bytes']} bytes")
            if total_bytes_used + len(data) > config["max_total_extracted_bytes"]:
                raise ValueError("total extracted attachment limit exceeded")
            extension = "jpeg" if match.group("ext").lower() == "jpg" else match.group("ext").lower()
            path = temp_dir / f"{artifact_id}.{extension}"
            path.write_bytes(data)
            image_paths.append(path)
            total_bytes_used += len(data)
        except (binascii.Error, ValueError, OSError) as exc:
            errors.append(artifact_error(artifact_id, "image", exc, source="html_data_uri"))
    if len(matches) > max_images:
        errors.append(artifact_skipped(
            f"inline-image-limit-{uuid.uuid4().hex[:8]}", "image",
            f"inline image limit reached; {len(matches) - max_images} additional images were not extracted",
            source="html_data_uri",
        ))
    return image_paths, errors, total_bytes_used


def parse_eml(eml_path: str | Path, config: dict[str, Any]) -> dict[str, Any]:
    """Parse one EML and extract bounded image artifacts into a temporary directory."""
    eml_path = Path(eml_path)
    if not eml_path.is_file():
        raise FileNotFoundError(f"EML file not found: {eml_path}")
    temp_dir = Path(tempfile.mkdtemp(prefix="eml_forensics_"))
    parsed: dict[str, Any] = {
        "metadata": {}, "text_body": "", "html_body": "", "image_paths": [],
        "extraction_errors": [], "temp_dir": str(temp_dir), "source_path": str(eml_path.resolve()),
    }
    total_extracted_bytes = 0
    try:
        with eml_path.open("rb") as source:
            message = email.message_from_binary_file(source, policy=email.policy.default)
        parsed["metadata"] = {
            "subject": str(message.get("subject", "")), "from": str(message.get("from", "")),
            "to": str(message.get("to", "")), "cc": str(message.get("cc", "")),
            "date": str(message.get("date", "")), "message_id": str(message.get("message-id", "")),
        }
        image_index = 0
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and not parsed["text_body"]:
                try:
                    parsed["text_body"] = part.get_content()
                except Exception as exc:
                    parsed["extraction_errors"].append(artifact_error("email-text-001", "text", exc, source="text/plain"))
            elif content_type == "text/html" and not parsed["html_body"]:
                try:
                    parsed["html_body"] = part.get_content()
                except Exception as exc:
                    parsed["extraction_errors"].append(artifact_error("email-html-001", "html", exc, source="text/html"))
            if part.get_content_maintype() != "image":
                continue
            image_index += 1
            artifact_id = f"image-{image_index:04d}"
            try:
                image_data = part.get_payload(decode=True)
                if not image_data:
                    raise ValueError("image MIME part contained no decoded data")
                if len(image_data) > config["max_image_bytes"]:
                    raise ValueError(f"image exceeds limit of {config['max_image_bytes']} bytes")
                if total_extracted_bytes + len(image_data) > config["max_total_extracted_bytes"]:
                    raise ValueError("total extracted attachment limit exceeded")
                guessed_extension = mimetypes.guess_extension(content_type) or ".bin"
                filename = safe_filename(part.get_filename() or f"{artifact_id}{guessed_extension}")
                image_path = temp_dir / f"{artifact_id}_{filename}"
                image_path.write_bytes(image_data)
                parsed["image_paths"].append(image_path)
                total_extracted_bytes += len(image_data)
            except Exception as exc:
                parsed["extraction_errors"].append(artifact_error(artifact_id, "image", exc, source="mime_image"))
        if parsed["html_body"]:
            paths, errors, total_extracted_bytes = extract_inline_images(
                parsed["html_body"], temp_dir, config, total_extracted_bytes
            )
            parsed["image_paths"].extend(paths)
            parsed["extraction_errors"].extend(errors)
        return parsed
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
