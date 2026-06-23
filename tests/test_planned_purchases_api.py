from decimal import Decimal


def test_planned_purchase_timeline_from_monthly_save(client):
    # No monthly_save → no timeline yet (None)
    client.post("/api/planned-purchases", json={"name": "Switch", "price": "499"})
    # With a monthly_save → months = ceil(price / save), plus a target month
    client.post("/api/planned-purchases", json={"name": "Vacation", "price": "3000", "monthly_save": "500"})

    r = client.get("/api/planned-purchases").json()
    by = {i["name"]: i for i in r["items"]}
    assert by["Switch"]["months"] is None
    assert by["Switch"]["target_month"] is None
    assert by["Vacation"]["months"] == 6        # ceil(3000 / 500)
    assert by["Vacation"]["target_month"] is not None
    # fund = sum of monthly_save across items
    assert Decimal(str(r["planned_fund"])) == Decimal("500.00")
    # items are sorted soonest-first; the unplanned one sinks to the bottom
    assert r["items"][0]["name"] == "Vacation"
    assert r["items"][-1]["name"] == "Switch"


def test_planned_purchase_save_covers_price_in_one_month(client):
    # monthly_save >= price → 1 month (never 0)
    client.post("/api/planned-purchases", json={"name": "Shoes", "price": "80", "monthly_save": "200"})
    item = client.get("/api/planned-purchases").json()["items"][0]
    assert item["months"] == 1


def test_planned_purchase_update_monthly_save(client):
    iid = client.post("/api/planned-purchases", json={"name": "Bike", "price": "1200"}).json()["id"]
    assert client.get("/api/planned-purchases").json()["items"][0]["months"] is None
    client.patch(f"/api/planned-purchases/{iid}", json={"monthly_save": "100"})
    r = client.get("/api/planned-purchases").json()
    assert r["items"][0]["months"] == 12        # ceil(1200 / 100)
    assert Decimal(str(r["planned_fund"])) == Decimal("100.00")


def test_planned_purchase_isolation(client, second_client):
    iid = client.post("/api/planned-purchases", json={"name": "X", "price": "10"}).json()["id"]
    assert second_client.get("/api/planned-purchases").json()["items"] == []
    assert second_client.delete(f"/api/planned-purchases/{iid}").status_code == 404


def test_account_link_and_earmark_out_of_runway(client):
    acc = client.post("/api/accounts", json={"type": "savings", "name": "Tagesgeld"}).json()["id"]
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": "2020-01-01T00:00:00Z", "amount": "1500", "raw_payee": "Savings"})
    item = client.post("/api/planned-purchases", json={
        "name": "Urlaub", "price": "1000", "monthly_save": "100",
        "account_id": acc, "earmarked": True,
    }).json()
    assert item["account_id"] == acc and item["earmarked"] is True

    # earmarked planned-purchase account → excluded from runway
    rw = client.get("/api/reports/runway").json()
    assert Decimal(str(rw["liquid"])) == Decimal("0.00")
    assert Decimal(str(rw["earmarked"])) == Decimal("1500.00")

    # clearing the link puts the balance back into runway
    client.patch(f"/api/planned-purchases/{item['id']}", json={"account_id": None})
    assert Decimal(str(client.get("/api/reports/runway").json()["liquid"])) == Decimal("1500.00")
