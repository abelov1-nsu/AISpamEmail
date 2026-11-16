"""Email-specific LLM prompts, response normalization and fallback behavior."""

import json
import re
from typing import Any, Optional

from .transport import OpenWebUIClient


SEGMENTATION_SYSTEM = """You are an email structure analyst. Split an email into semantic segments.
Return ONLY JSON: {"segments": [{"type":"short role", "content":"original text", "pos":0}]}.
Keep original wording, put a supplied subject first as type subject, and use sequential positions."""

JUDGE_SYSTEM = """You are an expert forensic analyst of AI-generated email text.
Return ONLY JSON: {"is_ai_generated":true|false,"confidence":0.0,"label":"likely_ai|possibly_ai|likely_human|inconclusive","reasoning":"1-3 sentences","suspicious_parts":["segment type"]}.
Use only visible textual evidence; do not claim hidden provenance."""


def extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _fallback_segments(text: str, subject: str) -> list[dict[str, Any]]:
    result = ([{"type": "subject", "content": subject.strip(), "pos": 0}] if subject.strip() else [])
    for index, part in enumerate(p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()):
        result.append({"type": "main_body" if index == 0 else "other", "content": part, "pos": len(result)})
    return result


def segment_email(client: OpenWebUIClient, text: str, subject: str = "") -> list[dict[str, Any]]:
    if not text or len(text.strip()) < 5:
        return _fallback_segments(text, subject)
    raw = client.chat([{"role": "system", "content": SEGMENTATION_SYSTEM}, {"role": "user", "content": f"Subject: {subject}\n\nEmail body:\n{text[:8000]}"}], temperature=0.05, max_tokens=2500)
    try:
        data = extract_json(raw); segments = data if isinstance(data, list) else data.get("segments") or data.get("items") or []
        result = [{"type": str(item.get("type", "other")).strip().lower() or "other", "content": str(item.get("content", "")).strip(), "pos": index} for index, item in enumerate(segments) if isinstance(item, dict)]
        if subject.strip() and (not result or result[0]["type"] != "subject"):
            result.insert(0, {"type": "subject", "content": subject.strip(), "pos": 0})
        for index, segment in enumerate(result): segment["pos"] = index
        return result
    except Exception:
        return _fallback_segments(text, subject)


def ai_judge(client: OpenWebUIClient, text: str, subject: str = "", segments: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    if not text or len(text.strip()) < 15:
        return {"is_ai_generated": False, "confidence": 0.0, "label": "inconclusive", "reasoning": "Text too short for reliable judgement.", "suspicious_parts": []}
    parts = "\n\n".join(f"[{part.get('type', 'other')} | pos={part.get('pos')}]\n{part.get('content', '')}" for part in (segments or []))
    raw = client.chat([{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": f"Subject: {subject}\n\nFull email text:\n{text[:7000]}\n\nSegments:\n{parts}"}], temperature=0.1, max_tokens=800)
    try:
        data = extract_json(raw)
        return {"is_ai_generated": bool(data.get("is_ai_generated", False)), "confidence": float(data.get("confidence", 0.0)), "label": str(data.get("label", "inconclusive")), "reasoning": str(data.get("reasoning", "")), "suspicious_parts": list(data.get("suspicious_parts") or [])}
    except Exception as exc:
        return {"is_ai_generated": False, "confidence": 0.0, "label": "error", "reasoning": f"Failed to parse LLM response: {exc}", "suspicious_parts": [], "raw": raw[:500] if isinstance(raw, str) else str(raw)}


def analyze_with_ai(text: str, subject: str = "", has_images: bool = False, client: Optional[OpenWebUIClient] = None) -> dict[str, Any]:
    client = client or OpenWebUIClient()
    segments = segment_email(client, text, subject)
    return {"segments": segments, "has_images": has_images, "ai_judge": ai_judge(client, text, subject, segments)}
