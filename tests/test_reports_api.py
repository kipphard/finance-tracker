from datetime import datetime, timezone
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


def test_post_recurring_to_transactions(client):
    acc = _account(client)
    client.post("/api/cashflow", json={
        "direction": "inflow", "name": "Salary", "amount": "3000", "cadence": "monthly",
        "account_id": acc,
    })
    posted = client.post("/api/cashflow/post").json()
    assert posted["posted"] == 1
    # Idempotent for the same month.
    assert client.post("/api/cashflow/post").json()["posted"] == 0

    txns = client.get("/api/transactions").json()
    assert any(t["raw_payee"] == "Salary" and Decimal(str(t["amount"])) == Decimal("3000") for t in txns)
