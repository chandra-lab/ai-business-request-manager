"""Phase 7 — automated coverage for the six mandatory AI+routing scenarios."""

from __future__ import annotations

import pytest

from app.ai.fixtures import SCENARIOS, scenario_sample_inputs
from app.ai.mock_provider import MockAIProvider
from app.ai.service import process_request_analysis
from app.models.ai_analysis import AIAnalysisStatus
from app.models.department import Department
from app.models.request import Request, RequestPriority, RequestStatus
from app.models.request_review_queue import RequestReviewQueue
from app.models.user import User


def _ensure_all_departments(db) -> dict[str, Department]:
    codes = {
        "HR": "Human Resources",
        "IT": "Information Technology",
        "FIN": "Finance",
        "FLEET": "Fleet Operations",
        "LEGAL": "Legal & Compliance",
    }
    out: dict[str, Department] = {}
    for code, name in codes.items():
        dept = db.query(Department).filter(Department.code == code).first()
        if dept is None:
            dept = Department(code=code, name=name, description=name, is_active=True)
            db.add(dept)
            db.flush()
        out[code] = dept
    return out


def _submit(db, user: User, title: str, description: str) -> Request:
    req = Request(
        title=title,
        description=description,
        status=RequestStatus.SUBMITTED,
        priority=RequestPriority.MEDIUM,
        requester_id=user.id,
    )
    db.add(req)
    db.flush()
    return req


@pytest.mark.parametrize(
    "scenario_id",
    [
        "scenario_1_it",
        "scenario_2_hr",
        "scenario_3_finance",
        "scenario_4_fleet",
        "scenario_5_legal",
        "scenario_6_ambiguous",
    ],
)
def test_mandatory_scenario_ai_and_routing(db, scenario_id: str):
    depts = _ensure_all_departments(db)
    user = db.info["users"]["employee"]
    title, description = scenario_sample_inputs()[scenario_id]
    expected = SCENARIOS[scenario_id]

    req = _submit(db, user, title, description)
    analysis = process_request_analysis(db, request_id=req.id, provider=MockAIProvider())
    db.refresh(req)

    assert analysis.status == AIAnalysisStatus.COMPLETED
    assert analysis.raw_response.get("scenario_id") == scenario_id
    assert float(analysis.confidence) == pytest.approx(expected.confidence, abs=1e-4)
    assert analysis.recommended_priority == expected.recommended_priority

    if expected.recommended_department_code:
        assert analysis.recommended_department_id == depts[expected.recommended_department_code].id
    else:
        assert analysis.recommended_department_id is None

    if scenario_id == "scenario_1_it":
        assert req.status == RequestStatus.PENDING_ASSIGNMENT
        assert req.department_id == depts["IT"].id
        assert req.clarification_required is False
    elif scenario_id == "scenario_2_hr":
        # High confidence but HR-sensitive → force human review + highly confidential
        assert req.is_hr_sensitive is True
        assert req.status == RequestStatus.PENDING_REVIEW
        review = (
            db.query(RequestReviewQueue)
            .filter(RequestReviewQueue.request_id == req.id)
            .first()
        )
        assert review is not None
    elif scenario_id in {"scenario_3_finance", "scenario_4_fleet", "scenario_5_legal"}:
        code = expected.recommended_department_code
        assert code is not None
        assert req.status == RequestStatus.PENDING_ASSIGNMENT
        assert req.department_id == depts[code].id
    elif scenario_id == "scenario_6_ambiguous":
        assert req.status == RequestStatus.PENDING_REVIEW
        assert req.clarification_required is True
        review = (
            db.query(RequestReviewQueue)
            .filter(RequestReviewQueue.request_id == req.id)
            .first()
        )
        assert review is not None
        assert review.clarification_required is True


def test_scenario_fixture_catalog_complete():
    samples = scenario_sample_inputs()
    assert set(samples) == set(SCENARIOS)
    for sid, rec in SCENARIOS.items():
        assert rec.scenario_id == sid
        assert 0.0 <= rec.confidence <= 1.0
