"""UX fixes: comments visibility, reviewer reassign, IT manager dept queue."""

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


def test_employee_history_hidden_comments_visible(client, auth_headers, db):
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
    process_request_analysis(db, request_id=req.id, provider=MockAIProvider())

    emp = auth_headers("employee@aibrm.example.com")
    hist = client.get(f"/api/v1/requests/{req.id}/history", headers=emp)
    assert hist.status_code == 200
    assert hist.json() == []

    comment = client.post(
        f"/api/v1/requests/{req.id}/comments",
        headers=emp,
        json={"body": "Still broken after reboot."},
    )
    assert comment.status_code == 201, comment.text

    listed = client.get(f"/api/v1/requests/{req.id}/comments", headers=emp)
    assert listed.status_code == 200
    assert any("Still broken" in c["body"] for c in listed.json())

    # Staff still see history
    mgr = auth_headers("manager@aibrm.example.com")
    staff_hist = client.get(f"/api/v1/requests/{req.id}/history", headers=mgr)
    assert staff_hist.status_code == 200
    assert len(staff_hist.json()) > 0


def test_reviewer_can_reassign_individual(client, auth_headers, db):
    _ensure_depts(db)
    employee = db.info["users"]["employee"]
    other: User = db.info["users"]["other"]
    # Put other in IT so they are assignable
    it = db.query(Department).filter(Department.code == "IT").first()
    other.department_id = it.id
    db.flush()

    req = Request(
        title="VPN access broken after password reset",
        description="I cannot connect to the corporate VPN since resetting my password yesterday.",
        status=RequestStatus.SUBMITTED,
        priority=RequestPriority.MEDIUM,
        requester_id=employee.id,
    )
    db.add(req)
    db.flush()
    process_request_analysis(db, request_id=req.id, provider=MockAIProvider())
    db.refresh(req)
    assert req.status == RequestStatus.PENDING_ASSIGNMENT

    reviewer = auth_headers("reviewer@aibrm.example.com")
    assigned = client.post(
        f"/api/v1/requests/{req.id}/assign",
        headers=reviewer,
        json={"assignee_id": str(other.id), "notes": "Reviewer assign"},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignee_id"] == str(other.id)

    # Reassign to employee (also IT)
    reassigned = client.post(
        f"/api/v1/requests/{req.id}/reassign",
        headers=reviewer,
        json={"assignee_id": str(employee.id)},
    )
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json()["assignee_id"] == str(employee.id)


def test_it_manager_sees_department_queue(client, auth_headers, db):
    _ensure_depts(db)
    # Align seeded/conftest manager with IT
    manager_user = db.info["users"]["manager"]
    it = db.query(Department).filter(Department.code == "IT").first()
    manager_user.department_id = it.id
    db.flush()

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
    process_request_analysis(db, request_id=req.id, provider=MockAIProvider())

    mgr = auth_headers("manager@aibrm.example.com")
    queue = client.get("/api/v1/manager/queue", headers=mgr)
    assert queue.status_code == 200
    assert any(i["id"] == str(req.id) for i in queue.json())

    dash = client.get("/api/v1/dashboard/department", headers=mgr)
    assert dash.status_code == 200
    assert dash.json()["pending_assignment_count"] >= 1
    assert any(i["id"] == str(req.id) for i in dash.json()["recent"])
