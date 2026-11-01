"""Pytest fixtures for Phase 1 smoke tests.

Uses a dedicated `aibrm_test` database so drop/create never touches
the development database used by Compose / seed.
"""

from __future__ import annotations

import os
from collections.abc import Generator
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

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.department import Department
from app.models.role import Role, UserRole
from app.models.user import User
import app.models  # noqa: F401


def _admin_and_test_urls() -> tuple[str, str]:
    settings = get_settings()
    base = os.environ.get("TEST_DATABASE_URL") or settings.sqlalchemy_database_uri
    parsed = urlparse(base)
    # Connect to maintenance DB to create aibrm_test
    admin_path = "/postgres"
    test_path = "/aibrm_test"
    admin_url = urlunparse(parsed._replace(path=admin_path))
    test_url = urlunparse(parsed._replace(path=test_path))
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

    dept = Department(code="IT", name="Information Technology", description="IT", is_active=True)
    role = Role(name="employee", description="Employee")
    session.add_all([dept, role])
    session.flush()

    user = User(
        email="employee@aibrm.example.com",
        full_name="Eva Employee",
        password_hash=hash_password(os.environ["SEED_DEMO_PASSWORD"]),
        department_id=dept.id,
        is_active=True,
    )
    session.add(user)
    session.flush()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    session.flush()

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
