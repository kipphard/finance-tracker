def _seed_and_account(client):
    client.post("/api/categories/seed")
    account_id = client.post(
        "/api/accounts", json={"type": "cash", "name": "Wallet", "currency": "EUR"}
    ).json()["id"]
    return account_id


def test_seed_and_category_crud(client):
    seeded = client.post("/api/categories/seed").json()
    assert len(seeded) == 15
    # Idempotent: a second seed creates nothing new.
    assert client.post("/api/categories/seed").json() == []

    created = client.post("/api/categories", json={"name": "Hobbies", "kind": "expense"})
    assert created.status_code == 201
    # Duplicate name rejected.
    assert client.post("/api/categories", json={"name": "Hobbies", "kind": "expense"}).status_code == 409

    assert len(client.get("/api/categories").json()) == 16


def test_rule_requires_existing_category(client):
    import uuid

    bad = client.post(
        "/api/rules", json={"match_pattern": "x", "category_id": str(uuid.uuid4())}
    )
    assert bad.status_code == 400


def test_manual_transaction_autocategorized(client):
    account_id = _seed_and_account(client)
    groceries = next(
        c for c in client.get("/api/categories").json() if c["name"] == "Groceries"
    )["id"]
    client.post("/api/rules", json={"match_pattern": "rewe", "category_id": groceries})

    txn = client.post(
        f"/api/accounts/{account_id}/transactions",
        json={"ts": "2026-03-01T00:00:00Z", "amount": "-23.50", "raw_payee": "REWE Markt"},
    )
    assert txn.status_code == 201
    assert txn.json()["category_id"] == groceries


def test_reclassify_and_remember_creates_rule(client):
    account_id = _seed_and_account(client)
    dining = next(c for c in client.get("/api/categories").json() if c["name"] == "Dining")["id"]

    txn_id = client.post(
        f"/api/accounts/{account_id}/transactions",
        json={"ts": "2026-03-01T00:00:00Z", "amount": "-30.00", "raw_payee": "Pizza Place"},
    ).json()["id"]
    assert client.get(f"/api/transactions/{txn_id}").json()["category_id"] is None

    patched = client.patch(
        f"/api/transactions/{txn_id}", json={"category_id": dining, "remember": True}
    )
    assert patched.json()["category_id"] == dining

    # The remembered rule now exists and auto-categorizes the next "Pizza Place".
    rules = client.get("/api/rules").json()
    assert any(r["match_pattern"] == "Pizza Place" for r in rules)
    again = client.post(
        f"/api/accounts/{account_id}/transactions",
        json={"ts": "2026-04-01T00:00:00Z", "amount": "-28.00", "raw_payee": "Pizza Place"},
    )
    assert again.json()["category_id"] == dining


def test_category_breakdown_report(client):
    from decimal import Decimal

    account_id = _seed_and_account(client)
    groceries = next(
        c for c in client.get("/api/categories").json() if c["name"] == "Groceries"
    )["id"]
    client.post("/api/rules", json={"match_pattern": "rewe", "category_id": groceries})

    client.post(f"/api/accounts/{account_id}/transactions",
                json={"ts": "2026-03-01T00:00:00Z", "amount": "-10.00", "raw_payee": "REWE"})
    client.post(f"/api/accounts/{account_id}/transactions",
                json={"ts": "2026-03-02T00:00:00Z", "amount": "-20.00", "raw_payee": "REWE"})
    client.post(f"/api/accounts/{account_id}/transactions",
                json={"ts": "2026-03-03T00:00:00Z", "amount": "-5.00", "raw_payee": "Mystery"})

    breakdown = client.get("/api/reports/category-breakdown").json()
    by_name = {b["name"]: b for b in breakdown}
    assert Decimal(str(by_name["Groceries"]["total"])) == Decimal("-30.00")
    assert by_name["Groceries"]["count"] == 2
    assert by_name["Groceries"]["is_fixed"] is False
    assert Decimal(str(by_name["Uncategorized"]["total"])) == Decimal("-5.00")
