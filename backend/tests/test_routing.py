"""Phase 4 routing, review, assignment, and reliability tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.ai.mock_provider import MockAIProvider
from app.ai.service import process_request_analysis
from app.core.config import get_settings
from app.models.ai_analysis import AIAnalysis, AIAnalysisStatus
from app.models.assignment import Assignment, AssignmentStatus
from app.models.department import Department
from app.models.request import Request, RequestPriority, RequestStatus
from app.models.request_review_queue import RequestReviewQueue, ReviewQueueStatus
from app.models.user import User
from app.modules.routing.service import RoutingDecision, classify_confidence


def _ensure_departments(db) -> dict[str, Department]:
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


def _make_request(db, user: User, title: str, description: str) -> Request:
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


def test_classify_confidence_thresholds(monkeypatch):
    get_settings.cache_clear()
    assert classify_confidence(0.90) == RoutingDecision.AUTO_ASSIGN
    assert classify_confidence(0.85) == RoutingDecision.AUTO_ASSIGN
    assert classify_confidence(0.70) == RoutingDecision.HUMAN_REVIEW
    assert classify_confidence(0.60) == RoutingDecision.HUMAN_REVIEW
    assert classify_confidence(0.59) == RoutingDecision.REVIEW_CLARIFICATION
    assert classify_confidence(None) == RoutingDecision.FAILURE_REVIEW


def test_auto_route_it_high_confidence(db):
    depts = _ensure_departments(db)
    user = db.info["users"]["employee"]
    req = _make_request(
        db,
        user,
        "VPN access broken after password reset",
        "I cannot connect to the corporate VPN since resetting my password yesterday.",
    )
    analysis = process_request_analysis(db, request_id=req.id, provider=MockAIProvider())
    db.refresh(req)
    assert analysis.status == AIAnalysisStatus.COMPLETED
    assert float(analysis.confidence) >= 0.85
    assert req.status == RequestStatus.PENDING_ASSIGNMENT
    assert req.department_id == depts["IT"].id
    active = (
        db.query(Assignment)
        .filter(Assignment.request_id == req.id, Assignment.status == AssignmentStatus.ACTIVE)
        .first()
    )
    assert active is not None
    assert active.assignee_id is None
    assert active.department_id == depts["IT"].id


def test_ambiguous_goes_to_review_with_clarification(db):
    _ensure_departments(db)
    user = db.info["users"]["employee"]
    req = _make_request(
        db,
        user,
        "Need help",
        "Something is wrong and someone should look into it when possible.",
    )
    process_request_analysis(db, request_id=req.id, provider=MockAIProvider())
    db.refresh(req)
    assert req.status == RequestStatus.PENDING_REVIEW
    assert req.clarification_required is True
    review = (
        db.query(RequestReviewQueue)
        .filter(RequestReviewQueue.request_id == req.id)
        .first()
    )
    assert review is not None
    assert review.clarification_required is True
    assert review.status == ReviewQueueStatus.OPEN


def test_ai_failure_routes_to_review(db, monkeypatch):
    _ensure_departments(db)
    user = db.info["users"]["employee"]
    req = _make_request(db, user, "Any title here", "Any description long enough here.")

    class Boom:
        name = "boom"

        def analyze_request(self, *, title: str, description: str):
            raise RuntimeError("provider down")

    process_request_analysis(db, request_id=req.id, provider=Boom())  # type: ignore[arg-type]
    db.refresh(req)
    assert req.status == RequestStatus.PENDING_REVIEW
    failed = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.request_id == req.id, AIAnalysis.status == AIAnalysisStatus.FAILED)
        .first()
    )
    assert failed is not None


def test_routing_idempotent_with_ai(db):
    _ensure_departments(db)
    user = db.info["users"]["employee"]
    req = _make_request(
        db,
        user,
        "Laptop replacement needed urgently",
        "My laptop hardware failed and I need a replacement from IT support.",
    )
    provider = MockAIProvider()
    first = process_request_analysis(db, request_id=req.id, provider=provider)
    second = process_request_analysis(db, request_id=req.id, provider=provider)
    assert first.id == second.id
    assert provider.call_count == 1
    assert db.query(Assignment).filter(Assignment.request_id == req.id).count() == 1


def test_review_assign_department_api(client, auth_headers, db):
    _ensure_departments(db)
    # Create ambiguous request via employee then process AI inside DB session used by override
    employee = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/requests",
        json={
            "title": "Need help",
            "description": "Something is wrong and someone should look into it when possible.",

            "submit": True,
        },
        headers=employee,
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    # Run AI+routing in the same test DB session
    from uuid import UUID

    process_request_analysis(db, request_id=UUID(request_id), provider=MockAIProvider())

    reviewer = auth_headers("admin@aibrm.example.com")  # admin can review
    # Need a reviewer role user — seed admin; also allow admin in _require_reviewer
    queue = client.get("/api/v1/review-queue", headers=reviewer)
    assert queue.status_code == 200
    items = queue.json()
    assert any(i["request_id"] == request_id for i in items)
    review_id = next(i["id"] for i in items if i["request_id"] == request_id)

    it = db.query(Department).filter(Department.code == "IT").first()
    assigned = client.post(
        f"/api/v1/review-queue/{review_id}/assign-department",
        headers=reviewer,
        json={
            "department_id": str(it.id),
            "decision_reason": "Looks like an IT access issue after clarification.",
        },
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "pending_assignment"
    assert assigned.json()["department_id"] == str(it.id)


def test_manager_assign_employee_api(client, auth_headers, db):
    depts = _ensure_departments(db)
    # Ensure manager dept is IT (seed manager is FLEET in seed script; conftest manager is IT)
    manager_headers = auth_headers("manager@aibrm.example.com")
    employee_user = db.info["users"]["employee"]

    # Create and auto-route an IT request
    req = _make_request(
        db,
        employee_user,
        "VPN access broken after password reset",
        "I cannot connect to the corporate VPN since resetting my password yesterday.",
    )
    process_request_analysis(db, request_id=req.id, provider=MockAIProvider())
    db.refresh(req)
    assert req.status == RequestStatus.PENDING_ASSIGNMENT

    queue = client.get("/api/v1/manager/queue", headers=manager_headers)
    assert queue.status_code == 200
    assert any(i["id"] == str(req.id) for i in queue.json())

    assigned = client.post(
        f"/api/v1/requests/{req.id}/assign",
        headers=manager_headers,
        json={"assignee_id": str(employee_user.id), "notes": "Please handle"},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignee_id"] == str(employee_user.id)

    # Idempotent same assignee
    again = client.post(
        f"/api/v1/requests/{req.id}/assign",
        headers=manager_headers,
        json={"assignee_id": str(employee_user.id)},
    )
    assert again.status_code == 200
    assert again.json()["id"] == assigned.json()["id"]
    active_count = (
        db.query(Assignment)
        .filter(
            Assignment.request_id == req.id,
            Assignment.status == AssignmentStatus.ACTIVE,
        )
        .count()
    )
    assert active_count == 1
