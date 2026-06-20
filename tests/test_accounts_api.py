from decimal import Decimal


def test_account_edit_and_delete(client):
    acc = client.post(
        "/api/accounts", json={"type": "cash", "name": "Old", "currency": "EUR"}
    ).json()["id"]
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": "2026-06-01T00:00:00Z", "amount": "100", "raw_payee": "x"})

    patched = client.patch(f"/api/accounts/{acc}", json={"name": "New Name", "type": "checking"})
    assert patched.status_code == 200
    assert patched.json()["name"] == "New Name"
    assert patched.json()["type"] == "checking"
    assert Decimal(str(patched.json()["latest_balance"])) == Decimal("100")  # from transactions

    # Deleting the account removes its transactions too.
    assert client.delete(f"/api/accounts/{acc}").status_code == 204
    assert client.get("/api/accounts").json() == []
    assert client.get("/api/transactions").json() == []
