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
    DEFAULT_MODEL = os.getenv("OPENWEBUI_MODEL", "Qwen3.8-Flash-Next")
    
    
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
            max_tokens: int = 2048,
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
    
    
    def _extract_json(text: str) -> Any:
        """Best-effort JSON extraction from model output."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    
    
    # ---------------------------------------------------------------------------
    # Semantic segmentation (type + content + pos)
    # ---------------------------------------------------------------------------
    
    SEGMENTATION_SYSTEM = """You are an email structure analyst.
    Your task is to split an email into semantic segments (paragraphs by meaning).
    
    For each segment return an object with exactly these fields:
    - "type": short label of the segment role
    - "content": the original text of this segment (do not invent or rewrite)
    - "pos": integer position starting from 0
    
    Typical type values (use the most appropriate, you may invent a short clear type if needed):
    - subject
    - greeting
    - introduction
    - main_body
    - request
    - offer
    - warning
    - cta          (call to action)
    - farewell
    - signature
    - disclaimer
    - ps
    - attachment_note
    - other
    
    Rules:
    1. Split by meaning, not only by empty lines.
    2. Keep original language and wording. Do not invent text.
    3. Subject of the email (if provided) should be the first segment with type "subject" and pos 0.
    4. Positions must be sequential: 0, 1, 2, ...
    5. Return ONLY valid JSON of this exact shape:
    {
      "segments": [
        {"type": "subject", "content": "...", "pos": 0},
        {"type": "greeting", "content": "...", "pos": 1}
      ]
    }
    """
    
    
    def segment_email(
        client: OpenWebUIClient,
        text: str,
        subject: str = "",
    ) -> list[dict[str, Any]]:
        """
        Split email into semantic segments.
        Returns list of {"type", "content", "pos"}.
        """
        if not text or len(text.strip()) < 5:
            segments = []
            if subject.strip():
                segments.append({"type": "subject", "content": subject.strip(), "pos": 0})
            if text.strip():
                segments.append({
                    "type": "main_body",
                    "content": text.strip(),
                    "pos": len(segments),
                })
            return segments
    
        user_content = f"Subject: {subject}\n\nEmail body:\n{text[:8000]}"
    
        raw = client.chat(
            messages=[
                {"role": "system", "content": SEGMENTATION_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=0.05,
            max_tokens=2500,
            response_format_json=True,
        )
    
        try:
            data = _extract_json(raw)
    
            # Accept both {"segments": [...]} and bare list
            if isinstance(data, list):
                segments = data
            else:
                segments = data.get("segments") or data.get("items") or []
    
            result = []
            for i, item in enumerate(segments):
                if not isinstance(item, dict):
                    continue
                result.append({
                    "type": str(item.get("type", "other")).strip().lower() or "other",
                    "content": str(item.get("content", "")).strip(),
                    "pos": int(item.get("pos", i)),
                })
    
            # Ensure sequential pos
            for i, seg in enumerate(result):
                seg["pos"] = i
    
            # Guarantee subject is present if we had one
            if subject.strip() and (not result or result[0]["type"] != "subject"):
                result.insert(0, {
                    "type": "subject",
                    "content": subject.strip(),
                    "pos": 0,
                })
                for i, seg in enumerate(result):
                    seg["pos"] = i
    
            return result
    
        except Exception:
            # Fallback: crude paragraph split
            parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
            result = []
            if subject.strip():
                result.append({"type": "subject", "content": subject.strip(), "pos": 0})
            for i, p in enumerate(parts):
                result.append({
                    "type": "main_body" if i == 0 else "other",
                    "content": p,
                    "pos": len(result),
                })
            return result
    
    
    # ---------------------------------------------------------------------------
    # AI judge
    # ---------------------------------------------------------------------------
    
    JUDGE_SYSTEM = """You are an expert forensic analyst of AI-generated text.
    Decide whether the given email (or its parts) was written with the help of a generative AI model (ChatGPT, Claude, Gemini, Llama, Qwen, etc.).
    
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
      "suspicious_parts": ["subject", "greeting", "main_body", ...]
    }
    """
    
    
    def ai_judge(
        client: OpenWebUIClient,
        text: str,
        subject: str = "",
        segments: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Ask the LLM whether the email looks AI-generated.
        Result is stored as an extra field in the report.
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
            lines = []
            for seg in segments:
                lines.append(f"[{seg.get('type', 'other')} | pos={seg.get('pos')}]\n{seg.get('content', '')}")
            parts_desc = "\n\nAlready segmented parts:\n" + "\n\n".join(lines)
    
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
        Convenience wrapper: run semantic segmentation + AI judge.
        Returns a dict ready to be inserted into the final report.
        """
        if client is None:
            client = OpenWebUIClient()
    
        segments = segment_email(client, text, subject=subject)
        judge = ai_judge(client, text, subject=subject, segments=segments)
    
        return {
            "segments": segments,          # list of {type, content, pos}
            "has_images": has_images,
            "ai_judge": judge,
        }
