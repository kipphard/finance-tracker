from decimal import Decimal


def _client(client, **extra):
    body = {"name": "GreatIdea UAB", "hourly_rate": "45"}
    body.update(extra)
    return client.post("/api/clients", json=body).json()


def test_client_crud_and_summary(client):
    c = _client(client, address="J. Jasinskio g. 14B\n01112 Vilnius", budget_hours="40")
    cid = c["id"]
    assert c["name"] == "GreatIdea UAB"
    assert Decimal(str(c["hourly_rate"])) == Decimal("45")
    assert Decimal(str(c["budget_hours"])) == Decimal("40")
    assert Decimal(str(c["tracked_hours"])) == Decimal("0")

    # add 90 + 30 minutes of unbilled time
    for mins in (90, 30):
        client.post("/api/time-entries", json={
            "client_id": cid, "started_at": "2026-06-01T09:00:00Z", "minutes": mins})

    c = next(x for x in client.get("/api/clients").json() if x["id"] == cid)
    assert Decimal(str(c["tracked_hours"])) == Decimal("2.00")
    assert Decimal(str(c["unbilled_hours"])) == Decimal("2.00")
    assert Decimal(str(c["unbilled_amount"])) == Decimal("90.00")  # 2h * 45

    client.patch(f"/api/clients/{cid}", json={"hourly_rate": "50"})
    assert Decimal(str(client.get(f"/api/clients/{cid}").json()["hourly_rate"])) == Decimal("50")

    assert client.delete(f"/api/clients/{cid}").status_code == 204
    assert client.get("/api/clients").json() == []
    assert client.get("/api/time-entries").json() == []  # cascade removed its entries


def test_client_isolation(client, second_client):
    cid = _client(client)["id"]
    assert second_client.get(f"/api/clients/{cid}").status_code == 404
    assert second_client.get("/api/clients").json() == []
