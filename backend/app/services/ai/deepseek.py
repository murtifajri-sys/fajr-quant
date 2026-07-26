"""DeepSeek chat completion provider (OpenAI-compatible API)."""
import json

import httpx

from app.core.config import settings
from app.core.logging import log
from app.services.ai.fallback import FallbackProvider
from app.services.ai.openai_compatible import OpenAICompatibleProvider


class DeepSeekProvider:
    name = "deepseek"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.AI_API_KEY
        self.base_url = (base_url or settings.AI_BASE_URL).rstrip("/")
        self.model = model or settings.AI_MODEL

    def complete(self, system_prompt: str, user_prompt: str) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return {"content": parsed, "raw": data}


def _build_primary() -> DeepSeekProvider:
    name = settings.AI_PROVIDER.lower()
    if name != "deepseek":
        log.warning(f"AI provider '{name}' not implemented, falling back to deepseek")
    return DeepSeekProvider()


def _build_fallback():
    if not settings.AI_FALLBACK_MODEL:
        return None
    return OpenAICompatibleProvider(
        api_key=settings.AI_FALLBACK_API_KEY or settings.AI_API_KEY or None,
        base_url=settings.AI_FALLBACK_BASE_URL or settings.AI_BASE_URL,
        model=settings.AI_FALLBACK_MODEL,
        provider_name=f"fallback:{settings.AI_FALLBACK_MODEL}",
    )


def get_provider():
    primary = _build_primary()
    fallback = _build_fallback()
    if fallback:
        return FallbackProvider(primary=primary, fallback=fallback)
    return primary
