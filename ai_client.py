"""
Open WebUI client for email segmentation and AI-generation judgement.

Uses the official chat completions endpoint:
  POST {base_url}/api/chat/completions

Configuration (environment variables or explicit args):
  OPENWEBUI_BASE_URL   – e.g. http://localhost:3000
  OPENWEBUI_API_KEY    – Bearer token (optional if auth disabled)
  OPENWEBUI_MODEL      – model id as shown in Open WebUI
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import requests


DEFAULT_BASE_URL = os.getenv("OPENWEBUI_BASE_URL", "http://localhost:3000")
DEFAULT_API_KEY = os.getenv("OPENWEBUI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENWEBUI_MODEL", "llama3.2")  # change to your model


class OpenWebUIClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = DEFAULT_API_KEY,
        model: str = DEFAULT_MODEL,
        timeout: float = 90.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1024,
        response_format_json: bool = True,
    ) -> str:
        """
        Call /api/chat/completions and return the assistant message content.
        """
        url = f"{self.base_url}/api/chat/completions"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        # Open WebUI / OpenAI-compatible: ask for JSON when needed
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        resp = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected Open WebUI response shape: {data}") from exc


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from model output."""
    text = text.strip()
    # strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Public high-level functions
# ---------------------------------------------------------------------------

SEGMENTATION_SYSTEM = """You are an email structure analyst.
Your task is to split the body of an email into exactly these parts:
- greeting
- main_body
- farewell

Rules:
- greeting: opening salutation / hello / dear ... (can be empty)
- main_body: the actual content of the message
- farewell: closing / signature / regards / best wishes / disclaimer (can be empty)
- If a part is missing, put an empty string.
- Do not invent text that is not present.
- Keep original language and wording.
- Return ONLY valid JSON with keys: greeting, main_body, farewell.
"""


def segment_email(
    client: OpenWebUIClient,
    text: str,
    subject: str = "",
) -> dict[str, str]:
    """
    Split email text into greeting / main_body / farewell via LLM.
    """
    if not text or len(text.strip()) < 10:
        return {
            "greeting": "",
            "main_body": text.strip(),
            "farewell": "",
        }

    user_content = f"Subject: {subject}\n\nEmail body:\n{text[:6000]}"

    raw = client.chat(
        messages=[
            {"role": "system", "content": SEGMENTATION_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.05,
        max_tokens=1500,
        response_format_json=True,
    )

    try:
        data = _extract_json(raw)
        return {
            "greeting": str(data.get("greeting", "")).strip(),
            "main_body": str(data.get("main_body", "")).strip(),
            "farewell": str(data.get("farewell", "")).strip(),
        }
    except Exception:
        # fallback – put everything into main_body
        return {
            "greeting": "",
            "main_body": text.strip(),
            "farewell": "",
            "_parse_error": True,
        }


JUDGE_SYSTEM = """You are an expert forensic analyst of AI-generated text.
Decide whether the given email (or its parts) was written with the help of a generative AI model (ChatGPT, Claude, Gemini, Llama, etc.).

Look for typical signals:
- overly polished / formulaic phrasing
- generic corporate tone
- classic AI stock phrases
- unnatural regularity of sentence length
- lack of personal voice / concrete details
- perfect grammar + slightly "too helpful" style

Return ONLY valid JSON:
{
  "is_ai_generated": true | false,
  "confidence": 0.0-1.0,
  "label": "likely_ai" | "possibly_ai" | "likely_human" | "inconclusive",
  "reasoning": "short explanation in 1-3 sentences",
  "suspicious_parts": ["greeting" | "main_body" | "farewell"]
}
"""


def ai_judge(
    client: OpenWebUIClient,
    text: str,
    subject: str = "",
    segments: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """
    Ask the LLM whether the email looks AI-generated.
    Result is meant to be stored as an extra field in the report.
    """
    if not text or len(text.strip()) < 15:
        return {
            "is_ai_generated": False,
            "confidence": 0.0,
            "label": "inconclusive",
            "reasoning": "Text too short for reliable judgement.",
            "suspicious_parts": [],
        }

    parts_desc = ""
    if segments:
        parts_desc = (
            f"\n\nAlready segmented parts:\n"
            f"GREETING:\n{segments.get('greeting', '')}\n\n"
            f"MAIN BODY:\n{segments.get('main_body', '')}\n\n"
            f"FAREWELL:\n{segments.get('farewell', '')}"
        )

    user_content = (
        f"Subject: {subject}\n\n"
        f"Full email text:\n{text[:7000]}"
        f"{parts_desc}"
    )

    raw = client.chat(
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        max_tokens=800,
        response_format_json=True,
    )

    try:
        data = _extract_json(raw)
        return {
            "is_ai_generated": bool(data.get("is_ai_generated", False)),
            "confidence": float(data.get("confidence", 0.0)),
            "label": str(data.get("label", "inconclusive")),
            "reasoning": str(data.get("reasoning", "")),
            "suspicious_parts": list(data.get("suspicious_parts") or []),
        }
    except Exception as exc:
        return {
            "is_ai_generated": False,
            "confidence": 0.0,
            "label": "error",
            "reasoning": f"Failed to parse LLM response: {exc}",
            "suspicious_parts": [],
            "raw": raw[:500] if isinstance(raw, str) else str(raw),
        }


def analyze_with_ai(
    text: str,
    subject: str = "",
    has_images: bool = False,
    client: Optional[OpenWebUIClient] = None,
) -> dict[str, Any]:
    """
    Convenience wrapper: run segmentation + AI judge.
    Returns a dict ready to be inserted into the final report.
    """
    if client is None:
        client = OpenWebUIClient()

    segments = segment_email(client, text, subject=subject)
    judge = ai_judge(client, text, subject=subject, segments=segments)

    return {
        "segmentation": {
            "greeting": segments.get("greeting", ""),
            "main_body": segments.get("main_body", ""),
            "farewell": segments.get("farewell", ""),
            "has_images": has_images,
        },
        "ai_judge": judge,
    }
