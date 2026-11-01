"""Assign department from ticket detail (by-request review APIs)."""

from __future__ import annotations

from app.ai.mock_provider import MockAIProvider
from app.ai.service import process_request_analysis
from app.models.department import Department
from app.models.request import Request, RequestPriority, RequestStatus
from app.models.user import User


def _ensure_depts(db):
    for code, name in [
        ("IT", "Information Technology"),
        ("FLEET", "Fleet"),
        ("FIN", "Finance"),
        ("LEGAL", "Legal"),
        ("HR", "HR"),
    ]:
        if db.query(Department).filter(Department.code == code).first() is None:
            db.add(Department(code=code, name=name, description=name, is_active=True))
    db.flush()


def _make_pending_review(db, client, auth_headers):
    """Ambiguous request → pending_review with open queue item."""
    _ensure_depts(db)
    employee = db.info["users"]["employee"]
    emp = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/requests",
        headers=emp,
        json={
            "title": "Need help",
            "description": "Something is wrong and someone should look into it when possible.",
            "priority": "medium",
            "submit": True,
        },
    )
    assert created.status_code == 201, created.text
    req_id = created.json()["id"]
    # Drive AI synchronously in case worker is not running in tests
    process_request_analysis(db, request_id=req_id, provider=MockAIProvider())
    db.expire_all()
    req = db.query(Request).filter(Request.id == req_id).one()
    assert req.status == RequestStatus.PENDING_REVIEW, req.status
    return req


def test_reviewer_gets_open_review_by_request(client, auth_headers, db):
    req = _make_pending_review(db, client, auth_headers)
    reviewer = auth_headers("reviewer@aibrm.example.com")
    resp = client.get(f"/api/v1/review-queue/by-request/{req.id}", headers=reviewer)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["request_id"] == str(req.id)
    assert body["status"] in {"open", "in_review"}


def test_reviewer_assigns_department_from_ticket_detail(client, auth_headers, db):
    req = _make_pending_review(db, client, auth_headers)
    reviewer = auth_headers("reviewer@aibrm.example.com")
    it = db.query(Department).filter(Department.code == "IT").one()

    routed = client.post(
        f"/api/v1/review-queue/by-request/{req.id}/assign-department",
        headers=reviewer,
        json={
            "department_id": str(it.id),
            "decision_reason": "Routed from ticket detail for 2nd temp style flow",
        },
    )
    assert routed.status_code == 200, routed.text
    assert routed.json()["status"] == "pending_assignment"
    assert routed.json()["department_id"] == str(it.id)

    # No longer an open review item
    missing = client.get(f"/api/v1/review-queue/by-request/{req.id}", headers=reviewer)
    assert missing.status_code == 404

    # Reviewer can list assignable users and assign a person
    other: User = db.info["users"]["other"]
    other.department_id = it.id
    db.flush()

    users = client.get(f"/api/v1/requests/{req.id}/assignable-users", headers=reviewer)
    assert users.status_code == 200, users.text
    assert any(u["id"] == str(other.id) for u in users.json())

    assigned = client.post(
        f"/api/v1/requests/{req.id}/assign",
        headers=reviewer,
        json={"assignee_id": str(other.id), "notes": "From detail"},
    )
    assert assigned.status_code == 200, assigned.text

    detail = client.get(f"/api/v1/requests/{req.id}", headers=reviewer)
    assert detail.status_code == 200
    assert detail.json()["status"] == "assigned"


def test_employee_cannot_use_by_request_review_apis(client, auth_headers, db):
    req = _make_pending_review(db, client, auth_headers)
    emp = auth_headers("employee@aibrm.example.com")
    it = db.query(Department).filter(Department.code == "IT").one()
    assert (
        client.get(f"/api/v1/review-queue/by-request/{req.id}", headers=emp).status_code == 403
    )
    assert (
        client.post(
            f"/api/v1/review-queue/by-request/{req.id}/assign-department",
            headers=emp,
            json={"department_id": str(it.id), "decision_reason": "nope"},
        ).status_code
        == 403
    )


def test_reviewer_can_comment_on_pending_review(client, auth_headers, db):
    req = _make_pending_review(db, client, auth_headers)
    reviewer = auth_headers("reviewer@aibrm.example.com")
    posted = client.post(
        f"/api/v1/requests/{req.id}/comments",
        headers=reviewer,
        json={"body": "Looking into routing for this ticket."},
    )
    assert posted.status_code == 201, posted.text
    listed = client.get(f"/api/v1/requests/{req.id}/comments", headers=reviewer)
    assert listed.status_code == 200
    assert any("Looking into routing" in c["body"] for c in listed.json())
