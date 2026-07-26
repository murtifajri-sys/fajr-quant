"""AI provider with automatic fallback when the primary runs out of quota/tokens."""
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.logging import log


# Error substrings that indicate quota / balance / token exhaustion on the primary.
_QUOTA_ERROR_HINTS = (
    "insufficient",
    "quota",
    "balance",
    "exceeded",
    "exhausted",
    "token",
    "rate limit",
    "429",
    "402",
    "payment",
)


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    if isinstance(exc, httpx.HTTPStatusError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (402, 429):
            return True
    return any(hint in msg for hint in _QUOTA_ERROR_HINTS)


class FallbackProvider:
    """Try the primary provider; on quota/token exhaustion, use the fallback.

    If no fallback is configured, behaves exactly like the primary provider.
    """

    name = "fallback"

    def __init__(self, primary, fallback=None):
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name
        self.active_provider = primary

    def complete(self, system_prompt: str, user_prompt: str) -> dict:
        try:
            result = self.primary.complete(system_prompt, user_prompt)
            self.active_provider = self.primary
            return result
        except Exception as e:
            if self.fallback and _is_quota_error(e):
                log.warning(
                    "ai_provider_fallback",
                    primary=self.primary.name,
                    error=str(e)[:200],
                    fallback=self.fallback.name,
                )
                result = self.fallback.complete(system_prompt, user_prompt)
                self.active_provider = self.fallback
                return result
            # Non-quota error (timeout, parse error, etc.) — don't burn fallback.
            raise
