from datetime import date
from decimal import Decimal


def test_recurring_flat_generates_draft_and_is_idempotent(client):
    cid = client.post("/api/clients", json={"name": "Retainer GmbH", "hourly_rate": "0"}).json()["id"]
    rec = client.post("/api/recurring-invoices", json={
        "client_id": cid, "cadence": "monthly", "mode": "flat", "amount": "200",
        "description": "Monatliche Webseiten-Pflege Pauschal", "next_run": date.today().isoformat(),
    }).json()
    assert rec["mode"] == "flat" and rec["active"] is True

    r = client.post("/api/recurring-invoices/run").json()
    assert r["generated"] == 1  # due today → exactly one

    invs = [i for i in client.get("/api/invoices").json() if i["client_id"] == cid]
    assert len(invs) == 1
    assert invs[0]["status"] == "draft"
    assert Decimal(str(invs[0]["total"])) == Decimal("200.00")
    assert invs[0]["items"][0]["description"] == "Monatliche Webseiten-Pflege Pauschal"

    # next_run advanced a month → running again generates nothing
    assert client.post("/api/recurring-invoices/run").json()["generated"] == 0
    assert len([i for i in client.get("/api/invoices").json() if i["client_id"] == cid]) == 1


def test_recurring_time_mode_bills_unbilled_entries(client):
    cid = client.post("/api/clients", json={"name": "Time Retainer", "hourly_rate": "50"}).json()["id"]
    client.post("/api/time-entries", json={
        "client_id": cid, "started_at": "2026-06-01T09:00:00Z", "minutes": 120, "description": "Pflege"})
    client.post("/api/recurring-invoices", json={
        "client_id": cid, "cadence": "monthly", "mode": "time", "next_run": date.today().isoformat()})
    assert client.post("/api/recurring-invoices/run").json()["generated"] == 1
    inv = [i for i in client.get("/api/invoices").json() if i["client_id"] == cid][0]
    assert Decimal(str(inv["total"])) == Decimal("100.00")  # 2h * 50
    # those entries are now billed → no unbilled time, so next time it would skip
    assert client.get(f"/api/time-entries?client_id={cid}&unbilled=true").json() == []


def test_recurring_isolation(client, second_client):
    cid = client.post("/api/clients", json={"name": "X", "hourly_rate": "0"}).json()["id"]
    client.post("/api/recurring-invoices", json={
        "client_id": cid, "mode": "flat", "amount": "10", "next_run": date.today().isoformat()})
    assert second_client.get("/api/recurring-invoices").json() == []
