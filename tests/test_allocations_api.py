from decimal import Decimal


def test_plan_distributes_leftover(client):
    # Income 3000, fixed 1500 -> leftover 1500.
    client.post(
        "/api/cashflow",
        json={"direction": "inflow", "name": "Salary", "amount": "3000", "cadence": "monthly"},
    )
    client.post(
        "/api/cashflow",
        json={"direction": "outflow", "name": "Rent", "amount": "1500", "cadence": "monthly"},
    )

    assert client.post("/api/allocations", json={"name": "Savings", "percent": "50"}).status_code == 201
    client.post("/api/allocations", json={"name": "Invest", "percent": "20"})

    plan = client.get("/api/allocations/plan").json()
    assert Decimal(str(plan["monthly_income"])) == Decimal("3000.00")
    assert Decimal(str(plan["monthly_fixed"])) == Decimal("1500.00")
    assert Decimal(str(plan["leftover"])) == Decimal("1500.00")

    buckets = {b["name"]: b for b in plan["buckets"]}
    assert Decimal(str(buckets["Savings"]["amount"])) == Decimal("750.00")
    assert Decimal(str(buckets["Invest"]["amount"])) == Decimal("300.00")
    assert Decimal(str(plan["allocated_percent"])) == Decimal("70")
    assert Decimal(str(plan["unallocated_percent"])) == Decimal("30")
    assert Decimal(str(plan["unallocated_amount"])) == Decimal("450.00")


def test_patch_and_delete_allocation(client):
    aid = client.post("/api/allocations", json={"name": "Savings", "percent": "50"}).json()["id"]
    r = client.patch(f"/api/allocations/{aid}", json={"percent": "60"})
    assert r.status_code == 200
    assert Decimal(str(r.json()["percent"])) == Decimal("60")

    assert client.delete(f"/api/allocations/{aid}").status_code == 204
    assert client.get("/api/allocations").json() == []


def test_no_leftover_means_zero_amounts(client):
    # No income -> leftover <= 0 -> bucket amounts are 0.
    client.post("/api/allocations", json={"name": "Savings", "percent": "50"})
    plan = client.get("/api/allocations/plan").json()
    assert Decimal(str(plan["leftover"])) <= 0
    assert Decimal(str(plan["buckets"][0]["amount"])) == Decimal("0.00")


def test_percent_must_be_in_range(client):
    assert client.post("/api/allocations", json={"name": "X", "percent": "0"}).status_code == 422
    assert client.post("/api/allocations", json={"name": "X", "percent": "150"}).status_code == 422


def test_allocation_account_link_set_and_clear(client):
    acc = client.post("/api/accounts", json={"type": "savings", "name": "Tagesgeld"}).json()["id"]
    aid = client.post("/api/allocations",
                      json={"name": "Invest", "percent": "20", "account_id": acc}).json()["id"]
    assert client.get("/api/allocations").json()[0]["account_id"] == acc
    # the plan echoes the linked account on each bucket
    bucket = client.get("/api/allocations/plan").json()["buckets"][0]
    assert bucket["account_id"] == acc
    # clearing the link (null) actually unlinks it
    client.patch(f"/api/allocations/{aid}", json={"account_id": None})
    assert client.get("/api/allocations").json()[0]["account_id"] is None


def test_apply_books_transfers_and_debt_payments(client):
    src = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    savings = client.post("/api/accounts", json={"type": "savings", "name": "Tagesgeld"}).json()["id"]
    client.post(f"/api/accounts/{src}/transactions",
                json={"ts": "2026-06-01T00:00:00Z", "amount": "2000", "raw_payee": "Opening"})
    debt = client.post("/api/debts", json={"name": "Auto", "amount": "500"}).json()["id"]

    res = client.post("/api/allocations/apply", json={
        "source_account_id": src,
        "transfers": [{"to_account_id": savings, "amount": "300", "label": "Emergency fund"}],
        "debt_payments": [{"debt_id": debt, "amount": "200"}],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["transfers_made"] == 1 and body["debts_paid"] == 1
    assert Decimal(str(body["total_moved"])) == Decimal("500.00")

    # Giro: 2000 − 300 (transfer out) − 200 (debt expense) = 1500 ; Tagesgeld: +300
    bal = {a["name"]: a["latest_balance"] for a in client.get("/api/accounts").json()}
    assert Decimal(str(bal["Giro"])) == Decimal("1500")
    assert Decimal(str(bal["Tagesgeld"])) == Decimal("300")

    # partial payment reduced the outstanding amount, debt still unpaid
    d = client.get("/api/debts").json()[0]
    assert d["paid"] is False
    assert Decimal(str(d["amount"])) == Decimal("300")  # 500 − 200

    # paying the rest clears it
    client.post("/api/allocations/apply", json={
        "source_account_id": src, "debt_payments": [{"debt_id": debt, "amount": "300"}]})
    assert client.get("/api/debts").json()[0]["paid"] is True


def test_apply_rejects_unknown_source(client):
    import uuid
    assert client.post("/api/allocations/apply", json={
        "source_account_id": str(uuid.uuid4()), "transfers": [], "debt_payments": []}).status_code == 404


def test_apply_records_last_applied_at(client):
    src = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    sav = client.post("/api/accounts", json={"type": "savings", "name": "Tagesgeld"}).json()["id"]
    client.post(f"/api/accounts/{src}/transactions",
                json={"ts": "2026-06-01T00:00:00Z", "amount": "1000", "raw_payee": "x"})
    assert client.get("/api/allocations/plan").json()["last_applied_at"] is None
    client.post("/api/allocations/apply", json={
        "source_account_id": src,
        "transfers": [{"to_account_id": sav, "amount": "100", "label": "Savings"}],
    })
    assert client.get("/api/allocations/plan").json()["last_applied_at"] is not None


def test_distribute_oneoff_books_transfers_and_debt_payments(client):
    # A one-off windfall books the same kind of moves as "Apply this month", fed an arbitrary amount.
    src = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    savings = client.post("/api/accounts", json={"type": "savings", "name": "Tagesgeld"}).json()["id"]
    client.post(f"/api/accounts/{src}/transactions",
                json={"ts": "2026-06-01T00:00:00Z", "amount": "2000", "raw_payee": "Opening"})
    debt = client.post("/api/debts", json={"name": "Auto", "amount": "500"}).json()["id"]

    res = client.post("/api/allocations/distribute-oneoff", json={
        "source_account_id": src,
        "amount": "1000",
        "transfers": [{"to_account_id": savings, "amount": "300", "label": "Savings"}],
        "debt_payments": [{"debt_id": debt, "amount": "200"}],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["transfers_made"] == 1 and body["debts_paid"] == 1
    assert Decimal(str(body["total_moved"])) == Decimal("500.00")

    # Giro: 2000 − 300 (transfer out) − 200 (debt expense) = 1500 ; Tagesgeld: +300
    bal = {a["name"]: a["latest_balance"] for a in client.get("/api/accounts").json()}
    assert Decimal(str(bal["Giro"])) == Decimal("1500")
    assert Decimal(str(bal["Tagesgeld"])) == Decimal("300")

    # partial payment reduced the outstanding amount, debt still unpaid
    d = client.get("/api/debts").json()[0]
    assert d["paid"] is False
    assert Decimal(str(d["amount"])) == Decimal("300")  # 500 − 200


def test_distribute_oneoff_does_not_touch_monthly_apply_log(client):
    # The critical separation: a one-off must NOT register as this month's monthly distribution,
    # otherwise the "Distribute leftover" card would falsely warn "already applied this month".
    src = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    sav = client.post("/api/accounts", json={"type": "savings", "name": "Tagesgeld"}).json()["id"]
    client.post(f"/api/accounts/{src}/transactions",
                json={"ts": "2026-06-01T00:00:00Z", "amount": "1000", "raw_payee": "x"})
    assert client.get("/api/allocations/plan").json()["last_applied_at"] is None
    res = client.post("/api/allocations/distribute-oneoff", json={
        "source_account_id": src,
        "amount": "500",
        "transfers": [{"to_account_id": sav, "amount": "100", "label": "Savings"}],
    })
    assert res.status_code == 200
    assert client.get("/api/allocations/plan").json()["last_applied_at"] is None


def test_distribute_oneoff_rejects_unknown_source(client):
    import uuid
    assert client.post("/api/allocations/distribute-oneoff", json={
        "source_account_id": str(uuid.uuid4()), "amount": "100",
        "transfers": [], "debt_payments": []}).status_code == 404


def test_distribute_oneoff_has_no_monthly_guard(client):
    # One-offs can run any number of times, anytime — no once-a-month guard.
    src = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    sav = client.post("/api/accounts", json={"type": "savings", "name": "Tagesgeld"}).json()["id"]
    client.post(f"/api/accounts/{src}/transactions",
                json={"ts": "2026-06-01T00:00:00Z", "amount": "1000", "raw_payee": "x"})
    body = {"source_account_id": src, "amount": "100",
            "transfers": [{"to_account_id": sav, "amount": "50", "label": "Savings"}]}
    assert client.post("/api/allocations/distribute-oneoff", json=body).status_code == 200
    assert client.post("/api/allocations/distribute-oneoff", json=body).status_code == 200
    bal = {a["name"]: a["latest_balance"] for a in client.get("/api/accounts").json()}
    assert Decimal(str(bal["Tagesgeld"])) == Decimal("100")  # 50 booked twice, no guard


def test_distribute_oneoff_requires_positive_amount(client):
    src = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    assert client.post("/api/allocations/distribute-oneoff", json={
        "source_account_id": src, "amount": "0", "transfers": []}).status_code == 422
