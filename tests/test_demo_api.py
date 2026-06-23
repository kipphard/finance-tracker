"""Public live-demo sandbox: isolation, feature-gating, registration lockdown, cleanup."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend import cleanup_demos
from backend.auth.ratelimit import RateLimiter
from backend.auth.security import hash_password
from backend.config import get_settings
from backend.main import app
from backend.persistence import repository
from backend.persistence.models import Transaction, User
from backend.seed_demo import seed_demo_for_user


def _as(token: str) -> TestClient:
    c = TestClient(app)  # shares the get_session override installed by the `client` fixture
    c.headers["Authorization"] = f"Bearer {token}"
    return c


def test_demo_creates_isolated_seeded_sandbox(client):
    a = client.post("/api/auth/demo").json()
    assert a["user"]["is_demo"] is True
    assert a["user"]["email"].startswith("demo+") and a["user"]["email"].endswith("@demo.invalid")
    txns_a = _as(a["access_token"]).get("/api/transactions").json()
    assert len(txns_a) > 0  # seeded with the demo data

    b = client.post("/api/auth/demo").json()
    assert b["user"]["id"] != a["user"]["id"]
    txns_b = _as(b["access_token"]).get("/api/transactions").json()
    assert len(txns_b) > 0
    # the two sandboxes share no rows — fully isolated
    assert {t["id"] for t in txns_a}.isdisjoint({t["id"] for t in txns_b})


def test_demo_user_blocked_from_email_and_bank(client):
    demo = _as(client.post("/api/auth/demo").json()["access_token"])
    assert demo.get("/api/banks/institutions").status_code == 403
    r = demo.post(f"/api/invoices/{uuid.uuid4()}/email", json={"to": "x@y.z"})
    assert r.status_code == 403 and r.json()["detail"] == "disabled in demo"


def test_normal_user_not_demo_blocked(client):
    # `client` is a normal registered user — not 403 (banks 503 since GoCardless is unset)
    assert client.get("/api/banks/institutions").status_code == 503
    r = client.post(f"/api/invoices/{uuid.uuid4()}/email", json={"to": "x@y.z"})
    assert r.status_code != 403


def test_register_gated_off_but_demo_stays_public(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "registration_enabled", False)
    r = client.post("/api/auth/register", json={"email": "nope@x.com", "password": "password123"})
    assert r.status_code == 403
    assert client.post("/api/auth/demo").status_code == 201  # demo unaffected


def test_cleanup_removes_aged_demo_users_and_their_rows(db_session):
    old = repository.create_user(
        db_session, email="demo+old@demo.invalid", password_hash=hash_password("x"), is_demo=True
    )
    old.created_at = datetime.now(timezone.utc) - timedelta(hours=get_settings().demo_ttl_hours + 1)
    db_session.flush()
    seed_demo_for_user(db_session, old.id)
    fresh = repository.create_user(
        db_session, email="demo+new@demo.invalid", password_hash=hash_password("x"), is_demo=True
    )
    seed_demo_for_user(db_session, fresh.id)
    db_session.commit()
    old_id = old.id

    removed = cleanup_demos.run(session=db_session)
    db_session.commit()
    assert removed == 1
    assert repository.get_user(db_session, old_id) is None
    assert repository.get_user(db_session, fresh.id) is not None
    # the aged user's child rows are gone too
    left = db_session.execute(
        select(func.count()).select_from(Transaction).where(Transaction.user_id == old_id)
    ).scalar_one()
    assert left == 0


def test_manually_created_user_can_log_in(client, db_session):
    # mirrors `python -m backend.create_user`: a hand-made user logs in even with registration off.
    repository.create_user(
        db_session, email="hand@made.com", password_hash=hash_password("password123")
    )
    db_session.commit()
    r = client.post("/api/auth/login", json={"email": "hand@made.com", "password": "password123"})
    assert r.status_code == 200 and r.json()["user"]["is_demo"] is False


def test_rate_limiter_blocks_excess():
    rl = RateLimiter(max_events=2, window_seconds=60)
    assert rl.allow("ip") is True
    assert rl.allow("ip") is True
    assert rl.allow("ip") is False  # 3rd within window
    assert rl.allow("other") is True  # different key unaffected


def test_demo_capacity_503(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_max_users", 0)
    assert client.post("/api/auth/demo").status_code == 503
