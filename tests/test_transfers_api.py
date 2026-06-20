from decimal import Decimal


def test_transfer_moves_balance_between_accounts(client):
    a = client.post("/api/accounts", json={"type": "cash", "name": "Main", "currency": "EUR"}).json()["id"]
    b = client.post("/api/accounts", json={"type": "brokerage", "name": "Binance", "currency": "EUR"}).json()["id"]
    # fund Main with a realized (past) inflow
    client.post(f"/api/accounts/{a}/transactions",
                json={"ts": "2020-01-01T00:00:00Z", "amount": "1955", "raw_payee": "seed"})

    r = client.post("/api/transfers", json={
        "from_account_id": a, "to_account_id": b, "amount": "1000", "ts": "2020-02-01T00:00:00Z"})
    assert r.status_code == 201

    accounts = {x["name"]: x for x in client.get("/api/accounts").json()}
    assert Decimal(str(accounts["Main"]["latest_balance"])) == Decimal("955")
    assert Decimal(str(accounts["Binance"]["latest_balance"])) == Decimal("1000")

    # net worth is unchanged by a transfer (the two legs cancel)
    assert Decimal(str(client.get("/api/networth").json()["total"])) == Decimal("1955")

    payees = {t["raw_payee"] for t in client.get("/api/transactions").json()}
    assert "Transfer to Binance" in payees
    assert "Transfer from Main" in payees


def test_transfer_same_account_rejected(client):
    a = client.post("/api/accounts", json={"type": "cash", "name": "Main", "currency": "EUR"}).json()["id"]
    r = client.post("/api/transfers", json={"from_account_id": a, "to_account_id": a, "amount": "10"})
    assert r.status_code == 400


def test_transfer_amount_must_be_positive(client):
    a = client.post("/api/accounts", json={"type": "cash", "name": "A", "currency": "EUR"}).json()["id"]
    b = client.post("/api/accounts", json={"type": "cash", "name": "B", "currency": "EUR"}).json()["id"]
    r = client.post("/api/transfers", json={"from_account_id": a, "to_account_id": b, "amount": "0"})
    assert r.status_code == 422
