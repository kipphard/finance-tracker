from decimal import Decimal


def test_planned_purchase_affordability(client):
    # leftover = 3000 in − 1000 out = 2000/month
    client.post("/api/cashflow", json={"direction": "inflow", "name": "Salary", "amount": "3000", "cadence": "monthly"})
    client.post("/api/cashflow", json={"direction": "outflow", "name": "Rent", "amount": "1000", "cadence": "monthly"})
    # allocate 50% to Invest (committed) → free-to-save = 2000 − 1000 = 1000/month
    client.post("/api/allocations", json={"name": "Invest", "percent": "50"})

    client.post("/api/planned-purchases", json={"name": "Switch", "price": "499"})
    client.post("/api/planned-purchases", json={"name": "Vacation", "price": "3000"})

    r = client.get("/api/planned-purchases").json()
    assert Decimal(str(r["monthly_budget"])) == Decimal("1000.00")
    by = {i["name"]: i for i in r["items"]}
    assert by["Switch"]["affordable_now"] is True and by["Switch"]["months"] == 0
    assert by["Vacation"]["affordable_now"] is False
    assert by["Vacation"]["months"] == 3        # ceil(3000 / 1000)
    assert by["Vacation"]["target_month"] is not None


def test_planned_purchase_no_budget(client):
    # no income → leftover 0 → no free cash → months is None
    client.post("/api/planned-purchases", json={"name": "TV", "price": "800"})
    r = client.get("/api/planned-purchases").json()
    assert Decimal(str(r["monthly_budget"])) == Decimal("0.00")
    assert r["items"][0]["months"] is None
    assert r["items"][0]["affordable_now"] is False


def test_planned_purchase_isolation(client, second_client):
    iid = client.post("/api/planned-purchases", json={"name": "X", "price": "10"}).json()["id"]
    assert second_client.get("/api/planned-purchases").json()["items"] == []
    assert second_client.delete(f"/api/planned-purchases/{iid}").status_code == 404
