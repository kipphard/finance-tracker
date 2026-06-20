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
