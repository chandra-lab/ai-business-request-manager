"""Resolve the configured AI provider."""

from __future__ import annotations

from app.ai.anthropic_provider import AnthropicAIProvider
from app.ai.interface import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.core.config import get_settings


def get_ai_provider() -> AIProvider:
    """Return Mock by default; Anthropic only when explicitly configured with a key."""
    settings = get_settings()
    provider = (settings.ai_provider or "mock").strip().lower()

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            # Safe fallback — never require a key to boot the app/worker
            return MockAIProvider()
        return AnthropicAIProvider()

    if provider == "mock":
        return MockAIProvider()

    # Unknown value → mock (documented in README)
    return MockAIProvider()
