from decimal import Decimal


def _txn(client, **extra):
    acc = client.post("/api/accounts", json={"type": "cash", "name": "X"}).json()["id"]
    body = {"ts": "2026-06-01T00:00:00Z", "amount": "-50", "raw_payee": "Shop"}
    body.update(extra)
    return client.post(f"/api/accounts/{acc}/transactions", json=body).json()["id"]


def test_edit_transaction_fields(client):
    tid = _txn(client, description="old note")
    patched = client.patch(
        f"/api/transactions/{tid}",
        json={"amount": "-75.50", "raw_payee": "New Shop", "description": "updated note",
              "counterparty": "ACME", "invoice_number": "INV-7"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert Decimal(str(body["amount"])) == Decimal("-75.50")
    assert body["raw_payee"] == "New Shop"
    assert body["description"] == "updated note"
    assert body["counterparty"] == "ACME"
    assert body["invoice_number"] == "INV-7"


def test_edit_only_touches_provided_fields(client):
    cat = client.post("/api/categories", json={"name": "Food", "kind": "expense"}).json()["id"]
    tid = _txn(client)
    client.patch(f"/api/transactions/{tid}", json={"category_id": cat})
    client.patch(f"/api/transactions/{tid}", json={"raw_payee": "Renamed"})  # payee only
    t = client.get(f"/api/transactions/{tid}").json()
    assert t["raw_payee"] == "Renamed"
    assert t["category_id"] == cat  # category preserved


def test_delete_transaction(client):
    tid = _txn(client)
    assert client.delete(f"/api/transactions/{tid}").status_code == 204
    assert client.get(f"/api/transactions/{tid}").status_code == 404
