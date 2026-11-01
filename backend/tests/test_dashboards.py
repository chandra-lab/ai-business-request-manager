"""Phase 6 role dashboard endpoint smoke tests."""


def test_employee_dashboard_ok(client, auth_headers):
    headers = auth_headers("employee@aibrm.example.com")
    resp = client.get("/api/v1/dashboard/employee", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "open_count" in body
    assert "recent" in body


def test_department_dashboard_manager(client, auth_headers):
    headers = auth_headers("manager@aibrm.example.com")
    resp = client.get("/api/v1/dashboard/department", headers=headers)
    assert resp.status_code == 200
    assert "pending_assignment_count" in resp.json()


def test_department_dashboard_forbidden_for_employee(client, auth_headers):
    headers = auth_headers("employee@aibrm.example.com")
    resp = client.get("/api/v1/dashboard/department", headers=headers)
    assert resp.status_code == 403


def test_hr_dashboard_requires_hr(client, auth_headers):
    admin = auth_headers("admin@aibrm.example.com")
    assert client.get("/api/v1/dashboard/hr", headers=admin).status_code == 403
    hr = auth_headers("hr@aibrm.example.com")
    resp = client.get("/api/v1/dashboard/hr", headers=hr)
    assert resp.status_code == 200
    assert "case_count" in resp.json()


def test_review_dashboard(client, auth_headers):
    headers = auth_headers("reviewer@aibrm.example.com")
    resp = client.get("/api/v1/dashboard/review", headers=headers)
    assert resp.status_code == 200
    assert "open_count" in resp.json()
