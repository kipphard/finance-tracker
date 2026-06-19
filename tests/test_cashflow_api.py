from decimal import Decimal


def test_add_items_and_summary(client):
    r = client.post(
        "/cashflow",
        json={"direction": "inflow", "name": "Salary", "amount": "3000", "cadence": "monthly"},
    )
    assert r.status_code == 201
    assert Decimal(str(r.json()["monthly_amount"])) == Decimal("3000.00")

    client.post(
        "/cashflow",
        json={"direction": "outflow", "name": "Rent", "amount": "1200", "cadence": "monthly"},
    )
    client.post(
        "/cashflow",
        json={"direction": "outflow", "name": "Insurance", "amount": "1200", "cadence": "yearly"},
    )

    summary = client.get("/cashflow/summary").json()
    assert Decimal(str(summary["monthly_inflow"])) == Decimal("3000.00")
    assert Decimal(str(summary["monthly_outflow"])) == Decimal("1300.00")  # 1200 + 100
    assert Decimal(str(summary["monthly_net"])) == Decimal("1700.00")
    assert summary["item_count"] == 3


def test_list_filter_patch_delete(client):
    inflow_id = client.post(
        "/cashflow",
        json={"direction": "inflow", "name": "Salary", "amount": "2000", "cadence": "monthly"},
    ).json()["id"]
    client.post(
        "/cashflow",
        json={"direction": "outflow", "name": "Rent", "amount": "800", "cadence": "monthly"},
    )

    inflows = client.get("/cashflow", params={"direction": "inflow"}).json()
    assert len(inflows) == 1
    assert inflows[0]["name"] == "Salary"

    # Deactivate the salary -> drops out of the summary.
    client.patch(f"/cashflow/{inflow_id}", json={"active": False})
    assert client.get("/cashflow/summary").json()["monthly_inflow"] == "0.00"

    assert client.delete(f"/cashflow/{inflow_id}").status_code == 204
    assert client.get(f"/cashflow/{inflow_id}").status_code == 404


def test_amount_must_be_positive(client):
    r = client.post(
        "/cashflow",
        json={"direction": "outflow", "name": "Bad", "amount": "0", "cadence": "monthly"},
    )
    assert r.status_code == 422
