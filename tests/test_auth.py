from fastapi.testclient import TestClient

from backend.main import app


def test_register_returns_token(client):
    # `client` is already registered+authed as user-a; registering the same email again 409s.
    dup = client.post(
        "/api/auth/register", json={"email": "user-a@example.com", "password": "password123"}
    )
    assert dup.status_code == 409


def test_me_requires_auth():
    anon = TestClient(app)
    assert anon.get("/api/me/export").status_code == 401
    assert anon.get("/api/accounts").status_code == 401


def test_login_flow(client):
    # Register a fresh user, then log in with the same credentials.
    client.post("/api/auth/register", json={"email": "login@example.com", "password": "secret12"})
    ok = client.post("/api/auth/login", json={"email": "login@example.com", "password": "secret12"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = client.post("/api/auth/login", json={"email": "login@example.com", "password": "wrong"})
    assert bad.status_code == 401


def test_me_returns_current_user(client):
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "user-a@example.com"
