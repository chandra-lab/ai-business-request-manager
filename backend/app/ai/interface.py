"""Provider-independent AI interface."""

from __future__ import annotations

from typing import Protocol

from app.ai.schemas import AIProviderResult


class AIProvider(Protocol):
    """Analyze a business request and return structured routing JSON."""

    name: str

    def analyze_request(self, *, title: str, description: str) -> AIProviderResult:
        """Perform exactly one model/fixture evaluation for the request text."""
        ...
