from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Day 01 of the current month: always <= today, so it falls inside the default
# income/expense range (year-start .. today) and the current monthly bucket.
DAY = datetime.now(timezone.utc).strftime("%Y-%m-01")
TS = f"{DAY}T00:00:00Z"


def _account(client):
    return client.post(
        "/api/accounts", json={"type": "checking", "name": "Biz", "currency": "EUR"}
    ).json()["id"]


def test_monthly_cashflow_and_income_expense(client):
    acc = _account(client)
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": TS, "amount": "1000.00", "raw_payee": "Client", "invoice_number": "INV-1"})
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": TS, "amount": "-200.00", "raw_payee": "Supplies"})

    monthly = client.get("/api/reports/monthly-cashflow", params={"months": 3}).json()
    assert len(monthly) == 3
    current = monthly[-1]
    assert Decimal(str(current["inflow"])) == Decimal("1000.00")
    assert Decimal(str(current["outflow"])) == Decimal("200.00")
    assert Decimal(str(current["net"])) == Decimal("800.00")

    ie = client.get("/api/reports/income-expense").json()
    assert Decimal(str(ie["income"])) == Decimal("1000.00")
    assert Decimal(str(ie["expense"])) == Decimal("200.00")
    assert Decimal(str(ie["net"])) == Decimal("800.00")


def test_csv_export(client):
    acc = _account(client)
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": TS, "amount": "500.00", "raw_payee": "Client",
                      "invoice_number": "INV-9", "counterparty": "ACME GmbH"})
    r = client.get("/api/reports/transactions.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "INV-9" in r.text and "ACME GmbH" in r.text


def test_run_recurring_to_transactions(client):
    acc = _account(client)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    client.post("/api/cashflow", json={
        "direction": "inflow", "name": "Salary", "amount": "3000", "cadence": "monthly",
        "account_id": acc, "next_due": today,
    })
    ran = client.post("/api/cashflow/run").json()
    assert ran["posted"] == 1
    # Idempotent — next_due advanced to next month.
    assert client.post("/api/cashflow/run").json()["posted"] == 0

    txns = client.get("/api/transactions").json()
    assert any(t["raw_payee"] == "Salary" and Decimal(str(t["amount"])) == Decimal("3000") for t in txns)


def test_cash_runway(client):
    from decimal import Decimal
    acc = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": "2026-06-01T00:00:00Z", "amount": "5000", "raw_payee": "x"})
    bro = client.post("/api/accounts", json={"type": "brokerage", "name": "Depot"}).json()["id"]
    client.post(f"/api/accounts/{bro}/transactions",
                json={"ts": "2026-06-01T00:00:00Z", "amount": "9000", "raw_payee": "y"})
    r = client.get("/api/reports/runway").json()
    assert Decimal(str(r["liquid"])) == Decimal("5000.00")  # brokerage excluded
    assert "monthly_net" in r and "runway_months" in r


def test_freelance_insights(client):
    from decimal import Decimal
    cid = client.post("/api/clients", json={"name": "Co", "hourly_rate": "50"}).json()["id"]
    client.post("/api/time-entries",
                json={"client_id": cid, "started_at": "2026-06-01T09:00:00Z", "minutes": 120})
    client.post("/api/invoices", json={"client_id": cid})  # bills 2h @ 50 = 100
    ins = client.get("/api/reports/freelance-insights").json()
    co = next(c for c in ins["clients"] if c["client_id"] == cid)
    assert Decimal(str(co["tracked_hours"])) == Decimal("2.00")
    assert Decimal(str(co["invoiced_total"])) == Decimal("100.00")
    assert Decimal(str(co["effective_rate"])) == Decimal("50.00")

    proj = client.post("/api/projects", json={"client_id": cid, "name": "P", "budget_hours": "1"}).json()["id"]
    client.post("/api/time-entries",
                json={"client_id": cid, "project_id": proj, "started_at": "2026-06-02T09:00:00Z", "minutes": 120})
    ins = client.get("/api/reports/freelance-insights").json()
    pb = next(p for p in ins["projects"] if p["project_id"] == proj)
    assert Decimal(str(pb["tracked_hours"])) == Decimal("2.00")
    assert pb["over_budget"] is True


def test_paycheck_zero_when_nothing_earned(client):
    client.post("/api/accounts", json={"type": "checking", "name": "Giro"})
    p = client.get("/api/reports/paycheck").json()
    assert Decimal(str(p["sustainable_pay"])) == Decimal("0.00")


def test_paycheck_liquid_matches_runway(client):
    acc = _account(client)
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": TS, "amount": "4000", "raw_payee": "Client"})
    p = client.get("/api/reports/paycheck").json()
    r = client.get("/api/reports/runway").json()
    # Shared _liquid_balance helper → the two endpoints must report the same liquid figure.
    assert Decimal(str(p["liquid"])) == Decimal(str(r["liquid"]))


def test_paycheck_capped_by_liquid(client):
    # Income last month → high trailing net; move most of it to a brokerage (illiquid) so the
    # spendable liquid balance is low and binds the recommendation.
    giro = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    depot = client.post("/api/accounts", json={"type": "brokerage", "name": "Depot"}).json()["id"]
    last_month = (datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)).strftime("%Y-%m-15")
    client.post(f"/api/accounts/{giro}/transactions",
                json={"ts": f"{last_month}T00:00:00Z", "amount": "6000", "raw_payee": "Client"})
    client.post("/api/transfers",
                json={"from_account_id": giro, "to_account_id": depot, "amount": "5000"})
    p = client.get("/api/reports/paycheck").json()
    assert p["capped_by_liquid"] is True
    assert Decimal(str(p["sustainable_pay"])) == Decimal(str(p["liquid"]))
    assert Decimal(str(p["sustainable_pay"])) <= Decimal(str(p["trailing_net"]))
