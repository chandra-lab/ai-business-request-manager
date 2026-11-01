"""Phase 3 AI schema, mock fixtures, and worker idempotency tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ai.fixtures import SCENARIOS, match_scenario, scenario_sample_inputs
from app.ai.mock_provider import MockAIProvider
from app.ai.schemas import AIRoutingRecommendation
from app.ai.service import process_request_analysis
from app.models.ai_analysis import AIAnalysis, AIAnalysisStatus
from app.models.department import Department
from app.models.request import Request, RequestPriority, RequestStatus
from app.models.user import User


def test_schema_rejects_invalid_department():
    with pytest.raises(ValidationError):
        AIRoutingRecommendation(
            recommended_department_code="SALES",
            confidence=0.5,
            rationale="bad dept",
        )


def test_schema_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        AIRoutingRecommendation(
            recommended_department_code="IT",
            confidence=1.5,
            rationale="too confident",
        )


def test_schema_accepts_null_department():
    rec = AIRoutingRecommendation(
        recommended_department_code=None,
        confidence=0.2,
        rationale="unclear",
    )
    assert rec.recommended_department_code is None


@pytest.mark.parametrize(
    "scenario_id",
    [
        "scenario_1_it",
        "scenario_2_hr",
        "scenario_3_finance",
        "scenario_4_fleet",
        "scenario_5_legal",
    ],
)
def test_mock_fixtures_scenarios_1_to_5(scenario_id):
    title, description = scenario_sample_inputs()[scenario_id]
    expected = SCENARIOS[scenario_id]
    matched = match_scenario(title, description)
    assert matched.scenario_id == scenario_id
    assert matched.recommended_department_code == expected.recommended_department_code
    assert matched.confidence == expected.confidence
    assert matched.is_hr_sensitive == expected.is_hr_sensitive

    provider = MockAIProvider()
    result = provider.analyze_request(title=title, description=description)
    assert result.provider == "mock"
    assert result.recommendation.scenario_id == scenario_id
    assert result.recommendation.recommended_department_code == expected.recommended_department_code


def test_mock_scenario_6_ambiguous():
    title, description = scenario_sample_inputs()["scenario_6_ambiguous"]
    matched = match_scenario(title, description)
    assert matched.scenario_id == "scenario_6_ambiguous"
    assert matched.recommended_department_code is None
    assert matched.confidence < 0.5


def test_worker_idempotency_single_ai_call(db):
    # Ensure departments exist for code resolution
    for code, name in [
        ("HR", "Human Resources"),
        ("IT", "Information Technology"),
        ("FIN", "Finance"),
        ("FLEET", "Fleet Operations"),
        ("LEGAL", "Legal & Compliance"),
    ]:
        if not db.query(Department).filter(Department.code == code).first():
            db.add(Department(code=code, name=name, description=name, is_active=True))
    db.flush()

    user: User = db.info["users"]["employee"]
    request = Request(
        title="VPN access broken after password reset",
        description="I cannot connect to the corporate VPN since resetting my password yesterday.",
        status=RequestStatus.SUBMITTED,
        priority=RequestPriority.MEDIUM,
        requester_id=user.id,
    )
    db.add(request)
    db.flush()

    provider = MockAIProvider()
    first = process_request_analysis(db, request_id=request.id, provider=provider)
    assert first.status == AIAnalysisStatus.COMPLETED
    assert provider.call_count == 1

    second = process_request_analysis(db, request_id=request.id, provider=provider)
    assert second.id == first.id
    assert provider.call_count == 1  # no duplicate LLM/fixture call

    count = db.query(AIAnalysis).filter(AIAnalysis.request_id == request.id).count()
    assert count == 1

    db.refresh(request)
    assert request.status == RequestStatus.AI_PROCESSING
