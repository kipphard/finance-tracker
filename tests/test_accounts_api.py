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


def test_account_expected_return_roundtrip(client):
    aid = client.post(
        "/api/accounts", json={"type": "brokerage", "name": "B", "expected_return": "7.5"}
    ).json()["id"]
    a = next(x for x in client.get("/api/accounts").json() if x["id"] == aid)
    assert Decimal(str(a["expected_return"])) == Decimal("7.5")

    client.patch(f"/api/accounts/{aid}", json={"expected_return": "5"})
    a = next(x for x in client.get("/api/accounts").json() if x["id"] == aid)
    assert Decimal(str(a["expected_return"])) == Decimal("5")


def test_forecast_grows_with_expected_return(client):
    aid = client.post(
        "/api/accounts", json={"type": "brokerage", "name": "Broker", "expected_return": "10"}
    ).json()["id"]
    client.post(f"/api/accounts/{aid}/transactions",
                json={"ts": "2020-01-01T00:00:00Z", "amount": "1200", "raw_payee": "seed"})

    fc = client.get("/api/forecast").json()
    current = Decimal(str(fc["current_total"]))
    net = Decimal(str(fc["monthly_net"]))
    months = len(fc["points"]) - 1
    flat = current + net * months
    last = Decimal(str(fc["points"][-1]["projected"]))

    assert current == Decimal("1200.00")  # m=0 is unaffected by growth
    assert last > flat  # expected return compounds on top of the flat projection


def test_future_dated_transactions_excluded_from_balance(client):
    aid = client.post(
        "/api/accounts", json={"type": "cash", "name": "Main", "currency": "EUR"}
    ).json()["id"]
    # realized (past) inflow
    client.post(f"/api/accounts/{aid}/transactions",
                json={"ts": "2020-01-01T00:00:00Z", "amount": "100", "raw_payee": "past"})
    # planned (far-future) inflow — should NOT count toward today's balance
    client.post(f"/api/accounts/{aid}/transactions",
                json={"ts": "2999-01-01T00:00:00Z", "amount": "50", "raw_payee": "future"})

    main = next(a for a in client.get("/api/accounts").json() if a["id"] == aid)
    assert Decimal(str(main["latest_balance"])) == Decimal("100")  # future 50 excluded

    nw = client.get("/api/networth").json()
    assert Decimal(str(nw["total"])) == Decimal("100")
