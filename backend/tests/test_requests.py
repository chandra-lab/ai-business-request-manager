"""Phase 2 request management tests."""

from __future__ import annotations

import io


def test_create_list_detail_history(client, auth_headers):
    headers = auth_headers("employee@aibrm.example.com")
    response = client.post(
        "/api/v1/requests",
        json={
            "title": "Badge access issue",
            "description": "Cannot enter building B after hours with my badge.",

            "submit": True,
        },
        headers={**headers, "Idempotency-Key": "test-key-create-1"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "submitted"
    request_id = data["id"]

    listed = client.get("/api/v1/requests", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert any(i["id"] == request_id for i in listed.json()["items"])

    detail = client.get(f"/api/v1/requests/{request_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["title"] == "Badge access issue"

    # Employees do not see internal RequestHistory
    history = client.get(f"/api/v1/requests/{request_id}/history", headers=headers)
    assert history.status_code == 200
    assert history.json() == []

    admin = auth_headers("admin@aibrm.example.com")
    staff_history = client.get(f"/api/v1/requests/{request_id}/history", headers=admin)
    assert staff_history.status_code == 200
    actions = [h["action"] for h in staff_history.json()]
    assert "created" in actions
    assert staff_history.json()[0]["to_status"] == "submitted"

    analysis = client.get(f"/api/v1/requests/{request_id}/analysis", headers=headers)
    assert analysis.status_code == 404


def test_idempotent_create(client, auth_headers):
    headers = auth_headers("employee@aibrm.example.com")
    body = {
        "title": "Printer jam help",
        "description": "Floor 3 printer keeps jamming on duplex jobs.",

        "submit": True,
    }
    key_headers = {**headers, "Idempotency-Key": "same-key-abc"}
    first = client.post("/api/v1/requests", json=body, headers=key_headers)
    second = client.post("/api/v1/requests", json=body, headers=key_headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_authz_hides_other_employees_requests(client, auth_headers):
    employee = auth_headers("employee@aibrm.example.com")
    other = auth_headers("other@aibrm.example.com")

    created = client.post(
        "/api/v1/requests",
        json={
            "title": "Private employee ticket",
            "description": "Should not be visible to another employee.",

            "submit": True,
        },
        headers=employee,
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    forbidden = client.get(f"/api/v1/requests/{request_id}", headers=other)
    assert forbidden.status_code == 404

    listed = client.get("/api/v1/requests", headers=other)
    assert listed.status_code == 200
    assert all(i["id"] != request_id for i in listed.json()["items"])


def test_admin_can_view_any(client, auth_headers):
    employee = auth_headers("employee@aibrm.example.com")
    admin = auth_headers("admin@aibrm.example.com")
    created = client.post(
        "/api/v1/requests",
        json={
            "title": "Admin visibility check",
            "description": "Admin should be able to open this request.",

            "submit": True,
        },
        headers=employee,
    )
    request_id = created.json()["id"]
    detail = client.get(f"/api/v1/requests/{request_id}", headers=admin)
    assert detail.status_code == 200


def test_patch_submit_and_cancel(client, auth_headers):
    headers = auth_headers("employee@aibrm.example.com")
    draft = client.post(
        "/api/v1/requests",
        json={
            "title": "Draft then submit",
            "description": "Start as draft then move to submitted.",

            "submit": False,
        },
        headers=headers,
    )
    assert draft.status_code == 201
    assert draft.json()["status"] == "draft"
    request_id = draft.json()["id"]

    submitted = client.patch(
        f"/api/v1/requests/{request_id}",
        json={"status": "submitted"},
        headers=headers,
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    cancelled = client.patch(
        f"/api/v1/requests/{request_id}",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    assert client.get(f"/api/v1/requests/{request_id}/history", headers=headers).json() == []
    admin = auth_headers("admin@aibrm.example.com")
    history = client.get(f"/api/v1/requests/{request_id}/history", headers=admin)
    assert any(h["to_status"] == "draft" for h in history.json())
    assert any(h["to_status"] == "submitted" for h in history.json())
    assert any(h["to_status"] == "cancelled" for h in history.json())


def test_attachment_upload(client, auth_headers):
    headers = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/requests",
        json={
            "title": "Attachment upload test",
            "description": "Need to attach a short text note for support.",

            "submit": True,
        },
        headers=headers,
    )
    request_id = created.json()["id"]
    files = {"file": ("note.txt", io.BytesIO(b"hello attachment"), "text/plain")}
    uploaded = client.post(
        f"/api/v1/requests/{request_id}/attachments",
        headers=headers,
        files=files,
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["filename"] == "note.txt"

    detail = client.get(f"/api/v1/requests/{request_id}", headers=headers)
    assert len(detail.json()["attachments"]) == 1


def test_employee_dashboard(client, auth_headers):
    headers = auth_headers("employee@aibrm.example.com")
    client.post(
        "/api/v1/requests",
        json={
            "title": "Dashboard visible request",
            "description": "This should appear on the employee dashboard recent list.",

            "submit": True,
        },
        headers=headers,
    )
    dash = client.get("/api/v1/dashboard/employee", headers=headers)
    assert dash.status_code == 200
    body = dash.json()
    assert body["open_count"] >= 1
    assert body["submitted_count"] >= 1
    assert len(body["recent"]) >= 1


def test_reject_disallowed_content_type(client, auth_headers):
    headers = auth_headers("employee@aibrm.example.com")
    created = client.post(
        "/api/v1/requests",
        json={
            "title": "Bad attachment type",
            "description": "Upload should reject executable content types.",

            "submit": True,
        },
        headers=headers,
    )
    request_id = created.json()["id"]
    files = {"file": ("evil.exe", io.BytesIO(b"MZ"), "application/x-msdownload")}
    uploaded = client.post(
        f"/api/v1/requests/{request_id}/attachments",
        headers=headers,
        files=files,
    )
    assert uploaded.status_code == 415
