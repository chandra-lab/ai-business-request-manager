"""AI provider interface placeholder (Phase 3).

Default runtime uses Mock; Anthropic is optional and not required for Phase 1.
"""

from __future__ import annotations

from typing import Any, Protocol


class AIProvider(Protocol):
    def analyze_request(self, *, title: str, description: str) -> dict[str, Any]:
        """Return structured routing recommendation JSON."""
        ...


class MockAIProvider:
    """Placeholder mock — full fixtures arrive in Phase 3."""

    def analyze_request(self, *, title: str, description: str) -> dict[str, Any]:
        return {
            "provider": "mock",
            "recommended_department_code": None,
            "confidence": 0.0,
            "rationale": "Phase 1 stub — AI analysis not implemented yet.",
            "title": title,
            "description_preview": description[:120],
        }
