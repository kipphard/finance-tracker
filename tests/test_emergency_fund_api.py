from decimal import Decimal


def test_default_target_is_3x_fixed_costs(client):
    # recurring fixed costs of 1000/mo
    client.post("/api/cashflow",
                json={"direction": "outflow", "name": "Rent", "amount": "1000", "cadence": "monthly"})

    f = client.get("/api/emergency-fund").json()
    assert f["target_months"] == 3
    assert Decimal(str(f["monthly_fixed"])) == Decimal("1000.00")
    assert Decimal(str(f["target"])) == Decimal("3000.00")
    assert Decimal(str(f["gap"])) == Decimal("3000.00")
    assert Decimal(str(f["funded_pct"])) == Decimal("0.00")


def test_saving_progress_and_six_times(client):
    client.post("/api/cashflow",
                json={"direction": "outflow", "name": "Rent", "amount": "1000", "cadence": "monthly"})

    client.patch("/api/emergency-fund", json={"current_amount": "1500"})
    f = client.get("/api/emergency-fund").json()
    assert Decimal(str(f["gap"])) == Decimal("1500.00")
    assert Decimal(str(f["funded_pct"])) == Decimal("50.00")

    client.patch("/api/emergency-fund", json={"target_months": 6})
    f = client.get("/api/emergency-fund").json()
    assert Decimal(str(f["target"])) == Decimal("6000.00")
    assert Decimal(str(f["gap"])) == Decimal("4500.00")


def test_custom_target_overrides_and_clears(client):
    client.post("/api/cashflow",
                json={"direction": "outflow", "name": "Rent", "amount": "1000", "cadence": "monthly"})

    client.patch("/api/emergency-fund", json={"target_amount": "5000"})
    f = client.get("/api/emergency-fund").json()
    assert Decimal(str(f["target"])) == Decimal("5000.00")  # custom overrides the multiplier

    # clearing the custom amount falls back to N× fixed
    client.patch("/api/emergency-fund", json={"target_amount": None})
    f = client.get("/api/emergency-fund").json()
    assert f["target_amount"] is None
    assert Decimal(str(f["target"])) == Decimal("3000.00")


def test_overfunded_caps_at_100(client):
    client.post("/api/cashflow",
                json={"direction": "outflow", "name": "Rent", "amount": "100", "cadence": "monthly"})
    client.patch("/api/emergency-fund", json={"current_amount": "10000"})
    f = client.get("/api/emergency-fund").json()
    assert Decimal(str(f["gap"])) == Decimal("0.00")
    assert Decimal(str(f["funded_pct"])) == Decimal("100.00")
