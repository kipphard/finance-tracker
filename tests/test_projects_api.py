from decimal import Decimal


def _client(client, rate="45"):
    return client.post("/api/clients", json={"name": "Agency GmbH", "hourly_rate": rate}).json()["id"]


def test_project_crud_and_summary(client):
    cid = _client(client)
    # project with no rate override inherits the client's rate
    p = client.post("/api/projects", json={"client_id": cid, "name": "Website", "budget_hours": "10"}).json()
    pid = p["id"]
    assert p["hourly_rate"] is None
    assert Decimal(str(p["effective_rate"])) == Decimal("45")

    # an override wins
    p2 = client.post("/api/projects", json={"client_id": cid, "name": "Campaign", "hourly_rate": "60"}).json()
    assert Decimal(str(p2["effective_rate"])) == Decimal("60")

    # 90 min on the project → 1.5h tracked, unbilled € at the inherited rate
    client.post("/api/time-entries", json={
        "client_id": cid, "project_id": pid, "started_at": "2026-06-01T09:00:00Z", "minutes": 90})
    p = client.get(f"/api/projects/{pid}").json()
    assert Decimal(str(p["tracked_hours"])) == Decimal("1.50")
    assert Decimal(str(p["unbilled_hours"])) == Decimal("1.50")
    assert Decimal(str(p["unbilled_amount"])) == Decimal("67.50")  # 1.5h * 45

    # list scoped by client
    assert len(client.get(f"/api/projects?client_id={cid}").json()) == 2

    client.patch(f"/api/projects/{pid}", json={"hourly_rate": "50"})
    assert Decimal(str(client.get(f"/api/projects/{pid}").json()["effective_rate"])) == Decimal("50")


def test_project_must_belong_to_client(client):
    c1 = _client(client)
    c2 = _client(client)
    p1 = client.post("/api/projects", json={"client_id": c1, "name": "P1"}).json()["id"]
    # time entry for client c2 referencing c1's project is rejected
    r = client.post("/api/time-entries", json={
        "client_id": c2, "project_id": p1, "started_at": "2026-06-01T09:00:00Z", "minutes": 60})
    assert r.status_code == 400


def test_delete_project_keeps_unprojected_entries(client):
    cid = _client(client)
    pid = client.post("/api/projects", json={"client_id": cid, "name": "Website"}).json()["id"]
    eid = client.post("/api/time-entries", json={
        "client_id": cid, "project_id": pid, "started_at": "2026-06-01T09:00:00Z", "minutes": 60}).json()["id"]

    assert client.delete(f"/api/projects/{pid}").status_code == 204
    entry = next(e for e in client.get("/api/time-entries").json() if e["id"] == eid)
    assert entry["project_id"] is None  # entry survived, just un-projected


def test_invoice_scoped_to_project_and_per_project_rate(client):
    cid = _client(client, rate="45")
    pid = client.post("/api/projects", json={"client_id": cid, "name": "Campaign", "hourly_rate": "60"}).json()["id"]
    # one entry on the project (60€/h) and one with no project (client 45€/h)
    client.post("/api/time-entries", json={
        "client_id": cid, "project_id": pid, "started_at": "2026-06-01T09:00:00Z", "minutes": 60})
    client.post("/api/time-entries", json={
        "client_id": cid, "started_at": "2026-06-02T09:00:00Z", "minutes": 60})

    inv = client.post("/api/invoices", json={"client_id": cid, "project_id": pid}).json()
    assert inv["project_name"] == "Campaign"
    assert len(inv["items"]) == 1
    assert Decimal(str(inv["items"][0]["rate"])) == Decimal("60")
    assert Decimal(str(inv["total"])) == Decimal("60.00")

    # the non-project entry is still unbilled → a whole-client invoice bills it at 45
    inv2 = client.post("/api/invoices", json={"client_id": cid}).json()
    assert Decimal(str(inv2["total"])) == Decimal("45.00")


def test_project_isolation(client, second_client):
    cid = _client(client)
    pid = client.post("/api/projects", json={"client_id": cid, "name": "Secret"}).json()["id"]
    assert second_client.get(f"/api/projects/{pid}").status_code == 404
    assert second_client.get("/api/projects").json() == []
