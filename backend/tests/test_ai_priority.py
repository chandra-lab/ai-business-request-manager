"""AI-applied priority + staff overrides; employees cannot set priority on create."""

from __future__ import annotations

from app.ai.mock_provider import MockAIProvider
from app.ai.service import process_request_analysis
from app.models.department import Department
from app.models.request import Request, RequestPriority, RequestStatus


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


def test_employee_create_rejects_priority_field(client, auth_headers):
    emp = auth_headers("employee@aibrm.example.com")
    rejected = client.post(
        "/api/v1/requests",
        headers=emp,
        json={
            "title": "Badge access issue",
            "description": "Cannot enter building B after hours with my badge.",
            "priority": "urgent",
            "submit": True,
        },
    )
    assert rejected.status_code == 422, rejected.text

    ok = client.post(
        "/api/v1/requests",
        headers=emp,
        json={
            "title": "Badge access issue",
            "description": "Cannot enter building B after hours with my badge.",
            "submit": True,
        },
    )
    assert ok.status_code == 201, ok.text
    # Placeholder until AI runs
    assert ok.json()["priority"] == "medium"


def test_ai_applies_recommended_priority(db):
    _ensure_depts(db)
    employee = db.info["users"]["employee"]
    req = Request(
        title="VPN access broken after password reset",
        description="I cannot connect to the corporate VPN since resetting my password yesterday.",
        status=RequestStatus.SUBMITTED,
        priority=RequestPriority.MEDIUM,
        requester_id=employee.id,
    )
    db.add(req)
    db.flush()

    analysis = process_request_analysis(db, request_id=req.id, provider=MockAIProvider())
    db.refresh(req)

    assert analysis.recommended_priority == "high"
    assert req.priority == RequestPriority.HIGH


def test_employee_cannot_patch_priority(client, auth_headers, db):
    _ensure_depts(db)
    emp = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/requests",
        headers=emp,
        json={
            "title": "Need help with something unclear",
            "description": "Something is wrong and someone should look into it when possible.",
            "submit": True,
        },
    )
    assert created.status_code == 201, created.text
    req_id = created.json()["id"]
    process_request_analysis(db, request_id=req_id, provider=MockAIProvider())

    denied = client.patch(
        f"/api/v1/requests/{req_id}",
        headers=emp,
        json={"priority": "urgent"},
    )
    assert denied.status_code == 403, denied.text


def test_reviewer_can_override_priority(client, auth_headers, db):
    _ensure_depts(db)
    emp = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/requests",
        headers=emp,
        json={
            "title": "Need help with something unclear",
            "description": "Something is wrong and someone should look into it when possible.",
            "submit": True,
        },
    )
    req_id = created.json()["id"]
    process_request_analysis(db, request_id=req_id, provider=MockAIProvider())

    reviewer = auth_headers("reviewer@aibrm.example.com")
    updated = client.patch(
        f"/api/v1/requests/{req_id}",
        headers=reviewer,
        json={"priority": "urgent"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["priority"] == "urgent"

    admin = auth_headers("admin@aibrm.example.com")
    hist = client.get(f"/api/v1/requests/{req_id}/history", headers=admin)
    assert hist.status_code == 200
    assert any(h["action"] == "priority_changed" for h in hist.json())


def test_manager_can_override_priority_after_dept_assign(client, auth_headers, db):
    _ensure_depts(db)
    emp = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/requests",
        headers=emp,
        json={
            "title": "VPN access broken after password reset",
            "description": "I cannot connect to the corporate VPN since resetting my password yesterday.",
            "submit": True,
        },
    )
    req_id = created.json()["id"]
    process_request_analysis(db, request_id=req_id, provider=MockAIProvider())
    db.expire_all()
    req = db.query(Request).filter(Request.id == req_id).one()
    assert req.status == RequestStatus.PENDING_ASSIGNMENT
    assert req.department_id is not None

    manager = auth_headers("manager@aibrm.example.com")
    updated = client.patch(
        f"/api/v1/requests/{req_id}",
        headers=manager,
        json={"priority": "low"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["priority"] == "low"
