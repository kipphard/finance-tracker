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


def test_edit_can_move_transaction_to_another_account(client):
    a = client.post("/api/accounts", json={"type": "cash", "name": "A"}).json()["id"]
    b = client.post("/api/accounts", json={"type": "cash", "name": "B"}).json()["id"]
    tid = client.post(f"/api/accounts/{a}/transactions",
                      json={"ts": "2020-01-01T00:00:00Z", "amount": "100", "raw_payee": "x"}).json()["id"]
    # before: A holds the balance
    bal = {x["name"]: x["latest_balance"] for x in client.get("/api/accounts").json()}
    assert Decimal(str(bal["A"])) == Decimal("100") and Decimal(str(bal["B"])) == Decimal("0")

    moved = client.patch(f"/api/transactions/{tid}", json={"account_id": b})
    assert moved.status_code == 200 and moved.json()["account_id"] == b

    bal = {x["name"]: x["latest_balance"] for x in client.get("/api/accounts").json()}
    assert Decimal(str(bal["A"])) == Decimal("0") and Decimal(str(bal["B"])) == Decimal("100")


def test_transaction_tags_normalized_and_editable(client):
    acc = client.post("/api/accounts", json={"type": "cash", "name": "X"}).json()["id"]
    tid = client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2026-06-01T00:00:00Z", "amount": "-50", "raw_payee": "Claude",
        "tags": [" Freelance ", "SOFTWARE", "freelance", ""],
    }).json()["id"]
    t = client.get(f"/api/transactions/{tid}").json()
    assert t["tags"] == ["freelance", "software"]  # trimmed, lowercased, deduped, blanks dropped

    client.patch(f"/api/transactions/{tid}", json={"tags": ["Freelance"]})
    assert client.get(f"/api/transactions/{tid}").json()["tags"] == ["freelance"]


def test_backfill_series_creates_one_per_month(client):
    acc = client.post("/api/accounts", json={"type": "cash", "name": "X"}).json()["id"]
    r = client.post(f"/api/accounts/{acc}/transactions/series", json={
        "start": "2026-01-01", "end": "2026-05-01", "cadence": "monthly",
        "amount": "500", "raw_payee": "Freelance retainer", "excluded": True, "tags": ["Freelance"],
    })
    assert r.status_code == 201
    assert r.json()["created"] == 5  # Jan, Feb, Mar, Apr, May (inclusive)

    series = [t for t in client.get("/api/transactions").json() if t["raw_payee"] == "Freelance retainer"]
    assert len(series) == 5
    assert all(t["excluded"] and t["tags"] == ["freelance"] for t in series)
    assert sorted(t["ts"][:10] for t in series) == [
        "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01"]

    main = next(a for a in client.get("/api/accounts").json() if a["id"] == acc)
    assert Decimal(str(main["latest_balance"])) == Decimal("0")  # excluded → off balance


def test_backfill_series_rejects_reversed_range(client):
    acc = client.post("/api/accounts", json={"type": "cash", "name": "X"}).json()["id"]
    r = client.post(f"/api/accounts/{acc}/transactions/series", json={
        "start": "2026-05-01", "end": "2026-01-01", "cadence": "monthly", "amount": "10"})
    assert r.status_code == 400


def test_delete_transaction(client):
    tid = _txn(client)
    assert client.delete(f"/api/transactions/{tid}").status_code == 204
    assert client.get(f"/api/transactions/{tid}").status_code == 404
