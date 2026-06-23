"""Pytest fixtures.

Tests run entirely on in-memory SQLite (no Docker / Postgres needed). Required env vars are
set before any backend import so config/encryption load cleanly.
"""
import os

from cryptography.fernet import Fernet

os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("APP_BASE_CURRENCY", "EUR")
# The `client` fixture authenticates via /api/auth/register, which is gated off by default.
os.environ.setdefault("REGISTRATION_ENABLED", "true")
# The demo rate limiter is a module singleton; keep it out of the way across the whole test session.
os.environ.setdefault("DEMO_RATE_PER_HOUR", "1000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.auth.security import hash_password  # noqa: E402
from backend.main import app  # noqa: E402
from backend.persistence import models, repository  # noqa: E402,F401  (register tables)
from backend.persistence.database import Base, get_session  # noqa: E402


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False, class_=Session
    )


@pytest.fixture
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user(db_session):
    """A persisted user for service-level (repository) tests."""
    u = repository.create_user(
        db_session, email="svc@example.com", password_hash=hash_password("password123")
    )
    db_session.commit()
    return u


def _register(test_client: TestClient, email: str) -> TestClient:
    resp = test_client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    )
    assert resp.status_code == 201, resp.text
    test_client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    return test_client


@pytest.fixture
def client(session_factory):
    def _override():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as test_client:
        _register(test_client, "user-a@example.com")
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def second_client(client):
    """A second authenticated client (different user, same DB) for isolation tests."""
    other = TestClient(app)  # shares the app + the get_session override from `client`
    return _register(other, "user-b@example.com")
