from datetime import datetime, timezone
from decimal import Decimal

YEAR = datetime.now(timezone.utc).year


def test_default_reserve_is_empty(client):
    r = client.get("/api/tax-reserve").json()
    assert r["has_account"] is False
    assert Decimal(str(r["reserve"])) == Decimal("0.00")
    assert Decimal(str(r["owed_ytd"])) == Decimal("0.00")
    assert Decimal(str(r["current_amount"])) == Decimal("0.00")
    assert r["reserve_account_id"] is None
    assert r["year"] == YEAR


def test_notional_amount_is_used_without_an_account(client):
    client.patch("/api/tax-reserve", json={"current_amount": "500"})
    r = client.get("/api/tax-reserve").json()
    assert r["has_account"] is False
    assert Decimal(str(r["reserve"])) == Decimal("500.00")
    assert Decimal(str(r["current_amount"])) == Decimal("500.00")


def test_invalid_account_is_rejected(client):
    import uuid
    resp = client.patch("/api/tax-reserve",
                        json={"reserve_account_id": str(uuid.uuid4())})
    assert resp.status_code == 404


def test_linked_account_balance_is_the_reserve_and_is_earmarked_from_runway(client):
    acc = client.post("/api/accounts",
                      json={"type": "savings", "name": "Steuerrücklage"}).json()["id"]
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": "2020-01-01T00:00:00Z", "amount": "1000", "raw_payee": "Set aside"})

    # before linking: the savings balance is part of the runway liquid pool
    before = client.get("/api/reports/runway").json()
    assert Decimal(str(before["liquid"])) == Decimal("1000.00")
    assert Decimal(str(before["earmarked"])) == Decimal("0.00")

    client.patch("/api/tax-reserve", json={"reserve_account_id": acc})
    r = client.get("/api/tax-reserve").json()
    assert r["has_account"] is True
    assert r["reserve_account_id"] == acc
    assert r["reserve_account_name"] == "Steuerrücklage"
    assert Decimal(str(r["reserve"])) == Decimal("1000.00")

    # after linking: the account is earmarked → excluded from liquid runway
    after = client.get("/api/reports/runway").json()
    assert Decimal(str(after["liquid"])) == Decimal("0.00")
    assert Decimal(str(after["earmarked"])) == Decimal("1000.00")


def test_unlinking_falls_back_to_notional_amount(client):
    acc = client.post("/api/accounts",
                      json={"type": "savings", "name": "Reserve"}).json()["id"]
    client.patch("/api/tax-reserve", json={"current_amount": "250", "reserve_account_id": acc})
    assert client.get("/api/tax-reserve").json()["has_account"] is True

    client.patch("/api/tax-reserve", json={"reserve_account_id": None})
    r = client.get("/api/tax-reserve").json()
    assert r["has_account"] is False
    assert Decimal(str(r["reserve"])) == Decimal("250.00")  # the notional amount is kept


def test_owed_comes_from_the_freelance_profit_estimate(client):
    # Other income well above the Grundfreibetrag, so any freelance profit is taxed at the margin.
    client.patch(f"/api/tax/year/{YEAR}", json={"other_taxable_income": "60000"})
    acc = client.post("/api/accounts",
                      json={"type": "checking", "name": "Giro"}).json()["id"]
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": f"{YEAR}-01-01T12:00:00Z", "amount": "20000",
                      "raw_payee": "Freelance project", "tags": ["freelance"]})

    r = client.get("/api/tax-reserve").json()
    assert Decimal(str(r["income_ytd"])) == Decimal("20000.00")
    assert Decimal(str(r["owed_ytd"])) > Decimal("0")
    assert Decimal(str(r["effective_rate"])) > Decimal("0")
    # nothing set aside yet → the full owed amount is the gap
    assert Decimal(str(r["gap"])) == Decimal(str(r["owed_ytd"]))
    assert Decimal(str(r["recommended_monthly"])) >= Decimal("0")
