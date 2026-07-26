"""Generic OpenAI-compatible chat completion provider.

Can be used for any OpenAI-compatible endpoint (DeepSeek, OpenAI, Groq,
OpenRouter, local Ollama, etc.).
"""
import json

import httpx

from app.core.config import settings
from app.core.logging import log


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        provider_name: str | None = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or ""
        self.base_url = (base_url or settings.AI_BASE_URL).rstrip("/")
        self.model = model or settings.AI_MODEL
        self.name = provider_name or f"openai:{self.model}"
        self.timeout = timeout

    def complete(self, system_prompt: str, user_prompt: str) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return {"content": parsed, "raw": data}
