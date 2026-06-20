import uuid
from decimal import Decimal


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_net_worth_end_to_end(client):
    a1 = client.post(
        "/api/accounts", json={"type": "checking", "name": "Giro", "currency": "EUR"}
    )
    assert a1.status_code == 201
    a1_id = a1.json()["id"]

    a2 = client.post(
        "/api/accounts", json={"type": "cash", "name": "Wallet", "currency": "EUR"}
    )
    a2_id = a2.json()["id"]

    assert client.post(f"/api/accounts/{a1_id}/transactions", json={"ts": "2026-06-01T00:00:00Z", "amount": "1000.00", "raw_payee": "x"}).status_code == 201
    assert client.post(f"/api/accounts/{a2_id}/transactions", json={"ts": "2026-06-01T00:00:00Z", "amount": "250.50", "raw_payee": "y"}).status_code == 201

    net_worth = client.get("/api/networth").json()
    assert Decimal(str(net_worth["total"])) == Decimal("1250.50")
    assert len(net_worth["breakdown"]) == 2

    snapshot = client.post("/api/networth/snapshots")
    assert snapshot.status_code == 201

    snapshots = client.get("/api/networth/snapshots").json()
    assert len(snapshots) == 1
    assert Decimal(str(snapshots[0]["total"])) == Decimal("1250.50")


def test_list_accounts_includes_balance_from_transactions(client):
    account_id = client.post(
        "/api/accounts", json={"type": "checking", "name": "X"}
    ).json()["id"]
    client.post(f"/api/accounts/{account_id}/transactions",
                json={"ts": "2026-06-01T00:00:00Z", "amount": "42.00", "raw_payee": "x"})

    accounts = client.get("/api/accounts").json()
    assert len(accounts) == 1
    assert Decimal(str(accounts[0]["latest_balance"])) == Decimal("42.00")


def test_unknown_account_returns_404(client):
    response = client.get(f"/api/accounts/{uuid.uuid4()}")
    assert response.status_code == 404
