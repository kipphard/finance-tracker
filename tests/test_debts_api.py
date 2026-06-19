def test_debt_lifecycle(client):
    created = client.post("/api/debts", json={"name": "Car repair", "amount": "900", "due_date": "2026-07-01"})
    assert created.status_code == 201
    debt_id = created.json()["id"]

    listed = client.get("/api/debts").json()
    assert len(listed) == 1
    assert listed[0]["name"] == "Car repair"
    assert listed[0]["paid"] is False

    # Mark paid -> drops out of the unpaid list.
    client.patch(f"/api/debts/{debt_id}", json={"paid": True})
    assert client.get("/api/debts", params={"unpaid_only": True}).json() == []

    assert client.delete(f"/api/debts/{debt_id}").status_code == 204
    assert client.get("/api/debts").json() == []


def test_debt_amount_must_be_positive(client):
    assert client.post("/api/debts", json={"name": "x", "amount": "0"}).status_code == 422


def test_debts_isolated_between_users(client, second_client):
    client.post("/api/debts", json={"name": "A debt", "amount": "100"})
    assert len(client.get("/api/debts").json()) == 1
    assert second_client.get("/api/debts").json() == []
