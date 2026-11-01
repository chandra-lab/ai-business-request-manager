"""Department members can view/work team tickets; reviewer assignee filtered by dept."""

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


def _route_it_ticket(db, client, auth_headers) -> Request:
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
    assert created.status_code == 201, created.text
    req_id = created.json()["id"]
    process_request_analysis(db, request_id=req_id, provider=MockAIProvider())
    db.expire_all()
    req = db.query(Request).filter(Request.id == req_id).one()
    assert req.status == RequestStatus.PENDING_ASSIGNMENT
    return req


def test_reviewer_lists_active_department_members_only(client, auth_headers, db):
    _ensure_depts(db)
    it = db.query(Department).filter(Department.code == "IT").one()
    fleet = db.query(Department).filter(Department.code == "FLEET").one()
    other: User = db.info["users"]["other"]
    other.department_id = fleet.id
    other.is_active = True
    inactive = db.info["users"]["employee"]
    # Keep employee in IT but mark a copy path: use other as inactive in IT briefly
    db.flush()

    reviewer = auth_headers("reviewer@aibrm.example.com")
    members = client.get(f"/api/v1/departments/{it.id}/members", headers=reviewer)
    assert members.status_code == 200, members.text
    ids = {m["id"] for m in members.json()}
    # IT seeded users: employee, manager, admin (all IT in conftest)
    assert str(db.info["users"]["employee"].id) in ids
    assert str(db.info["users"]["manager"].id) in ids
    # Fleet user must not appear in IT members
    assert str(other.id) not in ids

    # Inactive excluded
    emp_user: User = db.info["users"]["employee"]
    emp_user.is_active = False
    db.flush()
    members2 = client.get(f"/api/v1/departments/{it.id}/members", headers=reviewer)
    assert str(emp_user.id) not in {m["id"] for m in members2.json()}


def test_reviewer_assign_department_then_member(client, auth_headers, db):
    _ensure_depts(db)
    emp = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/requests",
        headers=emp,
        json={
            "title": "Need help",
            "description": "Something is wrong and someone should look into it when possible.",
            "submit": True,
        },
    )
    req_id = created.json()["id"]
    process_request_analysis(db, request_id=req_id, provider=MockAIProvider())
    db.expire_all()
    req = db.query(Request).filter(Request.id == req_id).one()
    assert req.status == RequestStatus.PENDING_REVIEW

    it = db.query(Department).filter(Department.code == "IT").one()
    assignee = db.info["users"]["employee"]
    reviewer = auth_headers("reviewer@aibrm.example.com")

    members = client.get(f"/api/v1/departments/{it.id}/members", headers=reviewer)
    assert any(m["id"] == str(assignee.id) for m in members.json())

    routed = client.post(
        f"/api/v1/review-queue/by-request/{req_id}/assign-department",
        headers=reviewer,
        json={"department_id": str(it.id), "decision_reason": "Route to IT Support"},
    )
    assert routed.status_code == 200, routed.text

    assignable = client.get(f"/api/v1/requests/{req_id}/assignable-users", headers=reviewer)
    assert assignable.status_code == 200
    assert all(u["department_id"] == str(it.id) for u in assignable.json())
    assert any(u["id"] == str(assignee.id) for u in assignable.json())

    assigned = client.post(
        f"/api/v1/requests/{req_id}/assign",
        headers=reviewer,
        json={"assignee_id": str(assignee.id)},
    )
    assert assigned.status_code == 200, assigned.text


def test_dept_member_sees_team_queue_and_can_comment(client, auth_headers, db):
    req = _route_it_ticket(db, client, auth_headers)
    # employee is IT member (not manager)
    emp = auth_headers("employee@aibrm.example.com")

    listed = client.get("/api/v1/requests", headers=emp)
    assert listed.status_code == 200
    assert any(i["id"] == str(req.id) for i in listed.json()["items"])

    detail = client.get(f"/api/v1/requests/{req.id}", headers=emp)
    assert detail.status_code == 200

    dash = client.get("/api/v1/dashboard/department", headers=emp)
    assert dash.status_code == 200, dash.text
    assert any(i["id"] == str(req.id) for i in dash.json()["recent"])

    comment = client.post(
        f"/api/v1/requests/{req.id}/comments",
        headers=emp,
        json={"body": "Looking at this from the IT team."},
    )
    assert comment.status_code == 201, comment.text


def test_dept_member_can_claim_and_progress(client, auth_headers, db):
    req = _route_it_ticket(db, client, auth_headers)
    # Use "other" moved into IT so requester != worker
    other: User = db.info["users"]["other"]
    it = db.query(Department).filter(Department.code == "IT").one()
    other.department_id = it.id
    db.flush()

    worker = auth_headers("other@aibrm.example.com")
    claimed = client.post(
        f"/api/v1/requests/{req.id}/assign",
        headers=worker,
        json={"assignee_id": str(other.id), "notes": "Self-claim"},
    )
    assert claimed.status_code == 200, claimed.text

    started = client.patch(
        f"/api/v1/requests/{req.id}",
        headers=worker,
        json={"status": "in_progress"},
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "in_progress"

    resolved = client.patch(
        f"/api/v1/requests/{req.id}",
        headers=worker,
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200, resolved.text


def test_fleet_member_cannot_see_it_ticket(client, auth_headers, db):
    req = _route_it_ticket(db, client, auth_headers)
    other: User = db.info["users"]["other"]
    fleet = db.query(Department).filter(Department.code == "FLEET").one()
    other.department_id = fleet.id
    db.flush()

    fleet_user = auth_headers("other@aibrm.example.com")
    listed = client.get("/api/v1/requests", headers=fleet_user)
    assert all(i["id"] != str(req.id) for i in listed.json()["items"])

    detail = client.get(f"/api/v1/requests/{req.id}", headers=fleet_user)
    assert detail.status_code == 404
