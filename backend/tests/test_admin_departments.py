"""Admin create/list departments."""


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
