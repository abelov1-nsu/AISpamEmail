"""Text artifact preparation and its current explicit analysis placeholder."""

import html
import re
from typing import Any


def html_to_visible_text(html_body: str) -> str:
    if not html_body:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_body)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def build_text_artifacts(email_data: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    plain = email_data.get("text_body", "").strip()
    html_body = email_data.get("html_body", "").strip()
    if plain:
        artifacts.append({"id": "text-plain-001", "type": "text", "source": "email.text/plain", "content": plain, "status": "pending_analysis"})
    if html_body and (visible := html_to_visible_text(html_body)):
        artifacts.append({"id": "text-html-001", "type": "text", "source": "email.text/html", "content": visible, "status": "pending_analysis"})
    return artifacts


def analyze_text_artifacts(
    text_artifacts: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Preserve text provenance without claiming unimplemented analysis."""
    results: list[dict[str, Any]] = []
    for artifact in text_artifacts:
        result = dict(artifact)
        result["status"] = "not_implemented"
        result["ruling"] = {"label": "not_analyzed", "score": None}
        result.pop("content", None)
        results.append(result)
    return results
