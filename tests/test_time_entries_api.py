def _client(client, name="Acme"):
    return client.post("/api/clients", json={"name": name, "hourly_rate": "45"}).json()["id"]


def test_manual_entry_minutes_from_range(client):
    cid = _client(client)
    e = client.post("/api/time-entries", json={
        "client_id": cid, "started_at": "2026-06-01T09:00:00Z",
        "ended_at": "2026-06-01T11:30:00Z", "description": "Website"}).json()
    assert e["minutes"] == 150
    assert e["invoice_id"] is None


def test_timer_start_stop_autostop(client):
    a = _client(client, "A")
    b = _client(client, "B")
    e1 = client.post("/api/time-entries/start", json={"client_id": a}).json()
    assert e1["ended_at"] is None
    assert client.get("/api/time-entries/running").json()["id"] == e1["id"]

    # starting a second timer auto-stops the first
    e2 = client.post("/api/time-entries/start", json={"client_id": b}).json()
    assert client.get("/api/time-entries/running").json()["id"] == e2["id"]
    e1_after = next(x for x in client.get("/api/time-entries").json() if x["id"] == e1["id"])
    assert e1_after["ended_at"] is not None

    stopped = client.post(f"/api/time-entries/{e2['id']}/stop").json()
    assert stopped["ended_at"] is not None
    assert client.get("/api/time-entries/running").json() is None


def test_entry_edit_filter_delete_isolation(client, second_client):
    cid = _client(client)
    eid = client.post("/api/time-entries", json={
        "client_id": cid, "started_at": "2026-06-02T10:00:00Z", "minutes": 60}).json()["id"]

    client.patch(f"/api/time-entries/{eid}", json={"minutes": 75, "description": "edited"})
    got = next(x for x in client.get("/api/time-entries").json() if x["id"] == eid)
    assert got["minutes"] == 75 and got["description"] == "edited"

    assert len(client.get("/api/time-entries", params={"client_id": cid}).json()) == 1
    assert len(client.get("/api/time-entries", params={"unbilled": "true"}).json()) == 1

    assert second_client.get("/api/time-entries").json() == []
    assert second_client.patch(f"/api/time-entries/{eid}", json={"minutes": 1}).status_code == 404

    assert client.delete(f"/api/time-entries/{eid}").status_code == 204
    assert client.get("/api/time-entries").json() == []
