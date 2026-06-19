"""Per-user data isolation: one user must never see or touch another's data."""
from decimal import Decimal


def test_accounts_and_networth_isolated(client, second_client):
    # user-a creates an account + balance
    a = client.post("/api/accounts", json={"type": "cash", "name": "A-wallet", "currency": "EUR"})
    a_id = a.json()["id"]
    client.post(f"/api/accounts/{a_id}/balances", json={"amount": "500.00"})

    # user-b creates their own
    b = second_client.post("/api/accounts", json={"type": "cash", "name": "B-wallet"})
    b_id = b.json()["id"]
    second_client.post(f"/api/accounts/{b_id}/balances", json={"amount": "999.00"})

    # Each sees only their own account / net worth.
    a_accounts = client.get("/api/accounts").json()
    assert [x["name"] for x in a_accounts] == ["A-wallet"]
    assert Decimal(str(client.get("/api/networth").json()["total"])) == Decimal("500.00")

    b_accounts = second_client.get("/api/accounts").json()
    assert [x["name"] for x in b_accounts] == ["B-wallet"]
    assert Decimal(str(second_client.get("/api/networth").json()["total"])) == Decimal("999.00")


def test_cannot_access_others_account(client, second_client):
    a_id = client.post("/api/accounts", json={"type": "cash", "name": "secret"}).json()["id"]
    # user-b must not be able to fetch or post to user-a's account.
    assert second_client.get(f"/api/accounts/{a_id}").status_code == 404
    assert second_client.post(f"/api/accounts/{a_id}/balances", json={"amount": "1"}).status_code == 404


def test_same_category_name_allowed_across_users(client, second_client):
    assert client.post("/api/categories", json={"name": "Rent", "kind": "expense"}).status_code == 201
    # Same name for a different user must be allowed (uniqueness is per-user).
    assert second_client.post("/api/categories", json={"name": "Rent", "kind": "expense"}).status_code == 201


def test_gdpr_export_and_delete(client):
    acc = client.post("/api/accounts", json={"type": "cash", "name": "X"}).json()["id"]
    client.post(f"/api/accounts/{acc}/balances", json={"amount": "10.00"})

    export = client.get("/api/me/export").json()
    assert export["user"]["email"] == "user-a@example.com"
    assert len(export["accounts"]) == 1
    assert len(export["balances"]) == 1

    # Right to erasure: delete the account, then the token's user is gone -> 401.
    assert client.delete("/api/me").status_code == 204
    assert client.get("/api/accounts").status_code == 401
