"""Default Mock AI provider — no external API key required."""

from __future__ import annotations

from app.ai.fixtures import match_scenario
from app.ai.prompt import PROMPT_VERSION
from app.ai.schemas import AIProviderResult


class MockAIProvider:
    name = "mock"

    def __init__(self) -> None:
        self.call_count = 0

    def analyze_request(self, *, title: str, description: str) -> AIProviderResult:
        self.call_count += 1
        recommendation = match_scenario(title, description)
        raw = recommendation.model_dump()
        return AIProviderResult(
            recommendation=recommendation,
            provider=self.name,
            model_id="mock-fixtures-v1",
            prompt_version=PROMPT_VERSION,
            input_tokens=None,
            output_tokens=None,
            raw_response=raw,
        )
