"""Pydantic schemas for structured AI routing responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ALLOWED_DEPARTMENT_CODES = frozenset({"HR", "IT", "FIN", "FLEET", "LEGAL"})


class AIRoutingRecommendation(BaseModel):
    """Single structured JSON object returned by any AI provider."""

    recommended_department_code: str | None = Field(
        default=None,
        description="One of HR, IT, FIN, FLEET, LEGAL — or null if uncertain",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=2000)
    is_hr_sensitive: bool = False
    recommended_priority: Literal["low", "medium", "high", "urgent"] | None = None
    scenario_id: str | None = Field(
        default=None,
        description="Optional fixture/scenario identifier (mock)",
    )
    labels: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("recommended_department_code")
    @classmethod
    def normalize_department_code(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        code = value.strip().upper()
        if code not in ALLOWED_DEPARTMENT_CODES:
            raise ValueError(
                f"recommended_department_code must be one of {sorted(ALLOWED_DEPARTMENT_CODES)} or null"
            )
        return code

    @field_validator("rationale")
    @classmethod
    def strip_rationale(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("rationale must be non-empty")
        return cleaned


class AIProviderResult(BaseModel):
    """Normalized provider output including token/metrics metadata."""

    recommendation: AIRoutingRecommendation
    provider: str
    model_id: str
    prompt_version: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_response: dict


ScenarioId = Literal[
    "scenario_1_it",
    "scenario_2_hr",
    "scenario_3_finance",
    "scenario_4_fleet",
    "scenario_5_legal",
    "scenario_6_ambiguous",
]
