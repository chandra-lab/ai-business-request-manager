"""HR visibility: body redaction + exclusion from non-HR team queues."""

from __future__ import annotations

from app.models.request import ConfidentialityLevel, Request, RequestPriority, RequestStatus
from app.models.user import User


SECRET = "CONFIDENTIAL_HR_BODY_PHRASE_XYZ_should_never_leak"


def _hr_sensitive_case(db, requester: User, *, department_id=None) -> Request:
    req = Request(
        title="Workplace harassment intake",
        description=SECRET,
        status=RequestStatus.PENDING_ASSIGNMENT,
        priority=RequestPriority.HIGH,
        requester_id=requester.id,
        department_id=department_id,
        is_hr_sensitive=True,
        confidentiality=ConfidentialityLevel.HIGHLY_CONFIDENTIAL,
    )
    db.add(req)
    db.flush()
    return req


def _hr_department_case(db, requester: User, hr_dept_id) -> Request:
    """Routed to HR department without the sensitive flag (still protected)."""
    req = Request(
        title="Benefits enrollment question",
        description=SECRET,
        status=RequestStatus.PENDING_ASSIGNMENT,
        priority=RequestPriority.MEDIUM,
        requester_id=requester.id,
        department_id=hr_dept_id,
        is_hr_sensitive=False,
        confidentiality=ConfidentialityLevel.STANDARD,
    )
    db.add(req)
    db.flush()
    return req


def test_it_manager_cannot_read_hr_description(client, auth_headers, db):
    """Negative: non-HR manager must not open HR case or see the secret body."""
    it = db.info["departments"]["IT"]
    # Mis-routed sensitive case sitting on IT — still protected
    req = _hr_sensitive_case(db, db.info["users"]["employee"], department_id=it.id)
    manager = auth_headers("manager@aibrm.example.com")

    detail = client.get(f"/api/v1/requests/{req.id}", headers=manager)
    assert detail.status_code == 404
    assert SECRET not in detail.text

    listed = client.get("/api/v1/requests", headers=manager)
    assert listed.status_code == 200
    assert all(item["id"] != str(req.id) for item in listed.json()["items"])
    assert SECRET not in listed.text


def test_it_manager_queue_excludes_hr_protected(client, auth_headers, db):
    """Negative: HR / sensitive / highly confidential never appear in IT team queue."""
    it = db.info["departments"]["IT"]
    hr = db.info["departments"]["HR"]
    employee = db.info["users"]["employee"]

    sensitive_on_it = _hr_sensitive_case(db, employee, department_id=it.id)
    hr_dept_ticket = _hr_department_case(db, employee, hr.id)

    # Normal IT ticket should still appear
    normal = Request(
        title="VPN access for new hire",
        description="Need VPN credentials for onboarding laptop setup.",
        status=RequestStatus.PENDING_ASSIGNMENT,
        priority=RequestPriority.MEDIUM,
        requester_id=employee.id,
        department_id=it.id,
        is_hr_sensitive=False,
        confidentiality=ConfidentialityLevel.STANDARD,
    )
    db.add(normal)
    db.flush()

    mgr = auth_headers("manager@aibrm.example.com")
    queue = client.get("/api/v1/manager/queue", headers=mgr)
    assert queue.status_code == 200
    ids = {item["id"] for item in queue.json()}
    assert str(normal.id) in ids
    assert str(sensitive_on_it.id) not in ids
    assert str(hr_dept_ticket.id) not in ids
    assert SECRET not in queue.text

    dash = client.get("/api/v1/dashboard/department", headers=mgr)
    assert dash.status_code == 200
    recent_ids = {item["id"] for item in dash.json()["recent"]}
    assert str(normal.id) in recent_ids
    assert str(sensitive_on_it.id) not in recent_ids
    assert str(hr_dept_ticket.id) not in recent_ids
    assert SECRET not in dash.text


def test_dept_member_team_dashboard_excludes_hr(client, auth_headers, db):
    it = db.info["departments"]["IT"]
    req = _hr_sensitive_case(db, db.info["users"]["employee"], department_id=it.id)
    emp = auth_headers("employee@aibrm.example.com")

    dash = client.get("/api/v1/dashboard/department", headers=emp)
    assert dash.status_code == 200
    recent_ids = {item["id"] for item in dash.json()["recent"]}
    assert str(req.id) not in recent_ids
    assert SECRET not in dash.text


def test_requester_sees_own_summary_hr_and_reviewer_see_body(client, auth_headers, db):
    hr_dept = db.info["departments"]["HR"]
    req = _hr_sensitive_case(db, db.info["users"]["employee"], department_id=hr_dept.id)

    emp = auth_headers("employee@aibrm.example.com")
    own = client.get(f"/api/v1/requests/{req.id}", headers=emp)
    assert own.status_code == 200
    body = own.json()
    assert body["status"] == "pending_assignment"
    assert body["title"] == "Workplace harassment intake"
    # Own submission remains visible to the requester
    assert body["description"] == SECRET
    assert body.get("description_redacted") is False

    notes = client.get(f"/api/v1/requests/{req.id}/hr-notes", headers=emp)
    assert notes.status_code == 403

    reviewer = auth_headers("reviewer@aibrm.example.com")
    rev = client.get(f"/api/v1/requests/{req.id}", headers=reviewer)
    assert rev.status_code == 200
    assert rev.json()["description"] == SECRET

    hr = auth_headers("hr@aibrm.example.com")
    hr_detail = client.get(f"/api/v1/requests/{req.id}", headers=hr)
    assert hr_detail.status_code == 200
    assert hr_detail.json()["description"] == SECRET


def test_fleet_employee_cannot_open_hr_department_ticket(client, auth_headers, db):
    hr_dept = db.info["departments"]["HR"]
    req = _hr_department_case(db, db.info["users"]["employee"], hr_dept.id)
    other = auth_headers("other@aibrm.example.com")
    resp = client.get(f"/api/v1/requests/{req.id}", headers=other)
    assert resp.status_code == 404
    assert SECRET not in resp.text


def test_admin_list_excludes_hr_without_grant(client, auth_headers, db):
    hr_dept = db.info["departments"]["HR"]
    req = _hr_sensitive_case(db, db.info["users"]["employee"], department_id=hr_dept.id)
    admin = auth_headers("admin@aibrm.example.com")
    assert client.get(f"/api/v1/requests/{req.id}", headers=admin).status_code == 404
    listed = client.get("/api/v1/requests", headers=admin)
    assert listed.status_code == 200
    assert all(item["id"] != str(req.id) for item in listed.json()["items"])
