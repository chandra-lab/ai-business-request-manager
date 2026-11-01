"""Admin create/list/update/delete departments + inactive routing exclusion."""

from app.models.department import Department
from app.models.request import Request, RequestPriority, RequestStatus
from app.modules.routing.service import RoutingDecision, apply_routing_after_analysis
from app.models.ai_analysis import AIAnalysis, AIAnalysisStatus
from decimal import Decimal


def test_admin_can_create_department(client, auth_headers):
    admin = auth_headers("admin@aibrm.example.com")
    created = client.post(
        "/api/v1/departments",
        headers=admin,
        json={
            "name": "IT Support",
            "description": "Access and technical support team from assessment pack.",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "IT Support"
    assert body["code"]
    assert body["description"]

    listed = client.get("/api/v1/departments", headers=admin)
    assert listed.status_code == 200
    assert any(d["name"] == "IT Support" for d in listed.json())

    # Unique name conflict
    dup = client.post(
        "/api/v1/departments",
        headers=admin,
        json={"name": "IT Support", "description": "dup"},
    )
    assert dup.status_code == 409


def test_non_admin_cannot_create_department(client, auth_headers):
    employee = auth_headers("employee@aibrm.example.com")
    resp = client.post(
        "/api/v1/departments",
        headers=employee,
        json={"name": "Finance Ops Shadow", "description": "should fail"},
    )
    assert resp.status_code == 403

    manager = auth_headers("manager@aibrm.example.com")
    resp2 = client.post(
        "/api/v1/departments",
        headers=manager,
        json={"name": "Operations Shadow", "description": "should fail"},
    )
    assert resp2.status_code == 403


def test_admin_create_with_manager(client, auth_headers, db):
    admin = auth_headers("admin@aibrm.example.com")
    manager = db.info["users"]["manager"]
    created = client.post(
        "/api/v1/departments",
        headers=admin,
        json={
            "name": "General Administration",
            "description": "General admin team",
            "manager_user_id": str(manager.id),
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["manager_user_id"] == str(manager.id)


def test_admin_can_update_department(client, auth_headers, db):
    admin = auth_headers("admin@aibrm.example.com")
    manager = db.info["users"]["manager"]
    created = client.post(
        "/api/v1/departments",
        headers=admin,
        json={"name": "Finance Ops", "description": "before"},
    )
    assert created.status_code == 201, created.text
    dept_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/departments/{dept_id}",
        headers=admin,
        json={
            "name": "Finance Operations",
            "description": "after",
            "manager_user_id": str(manager.id),
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Finance Operations"
    assert body["description"] == "after"
    assert body["manager_user_id"] == str(manager.id)
    assert body["is_active"] is True


def test_non_admin_cannot_update_or_delete(client, auth_headers):
    admin = auth_headers("admin@aibrm.example.com")
    employee = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/departments",
        headers=admin,
        json={"name": "Temp Team", "description": "x"},
    )
    dept_id = created.json()["id"]

    patch = client.patch(
        f"/api/v1/departments/{dept_id}",
        headers=employee,
        json={"name": "Hacked"},
    )
    assert patch.status_code == 403

    delete = client.delete(f"/api/v1/departments/{dept_id}", headers=employee)
    assert delete.status_code == 403


def test_admin_deactivate_and_activate(client, auth_headers):
    admin = auth_headers("admin@aibrm.example.com")
    employee = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/departments",
        headers=admin,
        json={"name": "Manual Review Desk", "description": "queue overflow"},
    )
    dept_id = created.json()["id"]

    deactivated = client.patch(
        f"/api/v1/departments/{dept_id}",
        headers=admin,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    # Admins still see inactive; non-admins do not
    admin_list = client.get("/api/v1/departments", headers=admin).json()
    assert any(d["id"] == dept_id and d["is_active"] is False for d in admin_list)

    emp_list = client.get("/api/v1/departments", headers=employee).json()
    assert all(d["id"] != dept_id for d in emp_list)

    reactivated = client.patch(
        f"/api/v1/departments/{dept_id}",
        headers=admin,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True


def test_delete_hard_when_unused(client, auth_headers):
    admin = auth_headers("admin@aibrm.example.com")
    created = client.post(
        "/api/v1/departments",
        headers=admin,
        json={"name": "Ephemeral Team", "description": "no refs"},
    )
    dept_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/departments/{dept_id}", headers=admin)
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["deletion"] == "hard"
    assert body["department"] is None

    listed = client.get("/api/v1/departments", headers=admin).json()
    assert all(d["id"] != dept_id for d in listed)


def test_delete_soft_when_request_references(client, auth_headers, db):
    admin = auth_headers("admin@aibrm.example.com")
    employee = db.info["users"]["employee"]
    created = client.post(
        "/api/v1/departments",
        headers=admin,
        json={"name": "Restricted HR Review", "description": "sensitive"},
    )
    assert created.status_code == 201, created.text
    dept_id = created.json()["id"]

    req = Request(
        title="Existing HR case",
        description="Already routed historically",
        status=RequestStatus.PENDING_ASSIGNMENT,
        priority=RequestPriority.MEDIUM,
        requester_id=employee.id,
        department_id=dept_id,
    )
    db.add(req)
    db.commit()

    deleted = client.delete(f"/api/v1/departments/{dept_id}", headers=admin)
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["deletion"] == "soft"
    assert body["department"]["is_active"] is False

    # Existing request still references the department
    db.refresh(req)
    assert str(req.department_id) == dept_id


def test_inactive_department_skipped_in_auto_routing(db):
    it = db.query(Department).filter(Department.code == "IT").one()
    it.is_active = False
    db.commit()

    employee = db.info["users"]["employee"]
    req = Request(
        title="VPN access",
        description="Need VPN for remote work",
        status=RequestStatus.AI_PROCESSING,
        priority=RequestPriority.MEDIUM,
        requester_id=employee.id,
    )
    db.add(req)
    db.flush()

    analysis = AIAnalysis(
        request_id=req.id,
        provider="mock",
        status=AIAnalysisStatus.COMPLETED,
        confidence=Decimal("0.95"),
        recommended_department_id=it.id,
        rationale="Would have been IT",
        raw_response={},
        idempotency_key=f"test-inactive-{req.id}",
    )
    db.add(analysis)
    db.flush()

    decision = apply_routing_after_analysis(db, request=req, analysis=analysis)
    db.commit()

    assert decision == RoutingDecision.HUMAN_REVIEW
    db.refresh(req)
    assert req.status == RequestStatus.PENDING_REVIEW
    assert req.department_id is None
