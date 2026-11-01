"""Phase 1 smoke tests: health, login, me."""

from __future__ import annotations

import os

DEMO_PASSWORD = os.environ.get("SEED_DEMO_PASSWORD", "DemoPass123!")


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_success(client) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@aibrm.example.com", "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_failure(client) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@aibrm.example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_me_requires_auth(client) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_token(client) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@aibrm.example.com", "password": DEMO_PASSWORD},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "employee@aibrm.example.com"
    assert data["full_name"] == "Eva Employee"
    assert "employee" in data["roles"]
    assert data["is_active"] is True
