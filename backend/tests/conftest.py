"""Pytest fixtures for AIBRM API tests.

Uses a dedicated `aibrm_test` database so drop/create never touches
the development database used by Compose / seed.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

os.environ.setdefault(
    "JWT_SECRET",
    "test-jwt-secret-at-least-32-characters-long",
)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SEED_DEMO_PASSWORD", "DemoPass123!")
os.environ.setdefault("UPLOAD_DIR", "/tmp/aibrm-test-uploads")

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.department import Department
from app.models.role import Role, UserRole
from app.models.user import User
import app.models  # noqa: F401


DEMO_PASSWORD = os.environ["SEED_DEMO_PASSWORD"]


def _admin_and_test_urls() -> tuple[str, str]:
    settings = get_settings()
    base = os.environ.get("TEST_DATABASE_URL") or settings.sqlalchemy_database_uri
    parsed = urlparse(base)
    admin_url = urlunparse(parsed._replace(path="/postgres"))
    test_url = urlunparse(parsed._replace(path="/aibrm_test"))
    return admin_url, test_url



@pytest.fixture(scope="session")
def engine():
    admin_url, test_url = _admin_and_test_urls()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'aibrm_test'")
        ).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE aibrm_test"))
    admin_engine.dispose()

    Path(os.environ["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    eng = create_engine(test_url, poolclass=NullPool, future=True)
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    TestingSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestingSession()

    it = Department(code="IT", name="Information Technology", description="IT", is_active=True)
    fleet = Department(code="FLEET", name="Fleet Operations", description="Fleet", is_active=True)
    session.add_all([it, fleet])
    session.flush()

    roles = {
        name: Role(name=name, description=name)
        for name in ("employee", "department_manager", "reviewer", "hr", "admin")
    }
    session.add_all(roles.values())
    session.flush()

    def make_user(email: str, name: str, dept: Department, role_names: list[str]) -> User:
        user = User(
            email=email,
            full_name=name,
            password_hash=hash_password(DEMO_PASSWORD),
            department_id=dept.id,
            is_active=True,
        )
        session.add(user)
        session.flush()
        for rn in role_names:
            session.add(UserRole(user_id=user.id, role_id=roles[rn].id))
        return user

    employee = make_user("employee@aibrm.example.com", "Eva Employee", it, ["employee"])
    other = make_user("other@aibrm.example.com", "Omar Other", fleet, ["employee"])
    manager = make_user(
        "manager@aibrm.example.com",
        "Morgan Manager",
        it,
        ["employee", "department_manager"],
    )
    admin = make_user("admin@aibrm.example.com", "Alex Admin", it, ["employee", "admin"])

    session.flush()
    session.info["users"] = {
        "employee": employee,
        "other": other,
        "manager": manager,
        "admin": admin,
    }
    session.info["departments"] = {"IT": it, "FLEET": fleet}

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    get_settings.cache_clear()
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def auth_headers(client: TestClient):
    def _login(email: str) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": DEMO_PASSWORD},
        )
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login
