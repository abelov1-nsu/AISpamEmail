"""OpenAI-compatible HTTP transport for Open WebUI."""

from typing import Any

import requests

from .config import settings


class OpenWebUIClient:
    def __init__(self, base_url: str = settings.openwebui_base_url, api_key: str = settings.openwebui_api_key, model: str = settings.openwebui_model, timeout: float = 90.0) -> None:
        self.base_url, self.api_key, self.model, self.timeout = base_url.rstrip("/"), api_key, model, timeout

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.1, max_tokens: int = 2048, response_format_json: bool = True) -> str:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False}
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(f"{self.base_url}/api/chat/completions", headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected Open WebUI response shape: {response.text}") from exc
