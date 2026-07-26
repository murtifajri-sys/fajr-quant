"""LLM provider interface."""
from typing import Protocol


class AIProvider(Protocol):
    name: str

    def complete(self, system_prompt: str, user_prompt: str) -> dict:
        """Return {content: str, raw: dict}."""
        ...
