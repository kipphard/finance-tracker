from decimal import Decimal


def _setup(client, rate="45"):
    client.patch("/api/business-profile", json={"name": "André Kipphard", "next_invoice_number": 100077})
    cid = client.post("/api/clients", json={"name": "GreatIdea UAB", "hourly_rate": rate}).json()["id"]
    for mins, desc in [(90, "Website"), (30, "Blog template")]:
        client.post("/api/time-entries", json={
            "client_id": cid, "started_at": "2026-06-01T09:00:00Z", "minutes": mins, "description": desc})
    return cid


def test_create_invoice_from_unbilled(client):
    cid = _setup(client)
    inv = client.post("/api/invoices", json={"client_id": cid}).json()
    assert inv["number"] == "100077"  # from the business profile, then increments
    assert inv["client_name"] == "GreatIdea UAB"
    assert len(inv["items"]) == 2
    assert Decimal(str(inv["total"])) == Decimal("90.00")  # 1.5h + 0.5h @ 45

    # the time entries are now billed → a second invoice has nothing to bill
    assert client.post("/api/invoices", json={"client_id": cid}).status_code == 400
    # and the profile's number advanced
    assert client.get("/api/business-profile").json()["next_invoice_number"] == 100078


def test_edit_items_recomputes_total_and_pdf(client):
    cid = _setup(client)
    inv = client.post("/api/invoices", json={"client_id": cid}).json()
    iid = inv["id"]

    updated = client.put(f"/api/invoices/{iid}/items", json=[
        {"description": "Creating new Blog Post Template", "hours": "3", "rate": "45"},
        {"description": "Updating Blog Posts section", "hours": "0.5", "rate": "45"},
    ]).json()
    assert Decimal(str(updated["total"])) == Decimal("157.50")  # 135 + 22.50

    pdf = client.get(f"/api/invoices/{iid}/pdf")
    assert pdf.status_code == 200
    assert "application/pdf" in pdf.headers["content-type"]
    assert pdf.content[:4] == b"%PDF"


def test_invoice_language_defaults_and_override(client):
    cid = _setup(client)
    # profile default language is German → intro defaults to the German text
    de = client.post("/api/invoices", json={"client_id": cid}).json()
    assert de["language"] == "de"
    assert "Sehr geehrte" in de["intro_text"]
    assert client.get(f"/api/invoices/{de['id']}/pdf").status_code == 200

    cid2 = client.post("/api/clients", json={"name": "Acme Ltd", "hourly_rate": "45"}).json()["id"]
    client.post("/api/time-entries", json={
        "client_id": cid2, "started_at": "2026-06-01T09:00:00Z", "minutes": 60, "description": "Work"})
    en = client.post("/api/invoices", json={"client_id": cid2, "language": "en"}).json()
    assert en["language"] == "en"
    assert "Dear" in en["intro_text"]


def test_vat_applied_when_not_kleinunternehmer(client):
    client.patch("/api/business-profile", json={"is_kleinunternehmer": False})
    cid = client.post("/api/clients", json={"name": "VAT GmbH", "hourly_rate": "100"}).json()["id"]
    client.post("/api/time-entries", json={
        "client_id": cid, "started_at": "2026-06-01T09:00:00Z", "minutes": 60, "description": "Work"})
    inv = client.post("/api/invoices", json={"client_id": cid}).json()
    assert Decimal(str(inv["vat_rate"])) == Decimal("19")
    assert Decimal(str(inv["total"])) == Decimal("119.00")  # 100 net + 19% VAT
    assert client.get(f"/api/invoices/{inv['id']}/pdf").status_code == 200


def test_invoice_line_descriptions_are_flattened(client):
    cid = client.post("/api/clients", json={"name": "Flat GmbH", "hourly_rate": "45"}).json()["id"]
    client.post("/api/time-entries", json={
        "client_id": cid, "started_at": "2026-06-01T09:00:00Z", "minutes": 60,
        "description": "Kurse erstellen\nRebranding"})
    inv = client.post("/api/invoices", json={"client_id": cid}).json()
    assert inv["items"][0]["description"] == "Kurse erstellen, Rebranding"


def test_email_requires_smtp_config(client):
    cid = client.post("/api/clients", json={"name": "Mail GmbH", "hourly_rate": "45"}).json()["id"]
    client.post("/api/time-entries", json={
        "client_id": cid, "started_at": "2026-06-01T09:00:00Z", "minutes": 60, "description": "x"})
    iid = client.post("/api/invoices", json={"client_id": cid}).json()["id"]
    # SMTP isn't configured in tests → 400
    r = client.post(f"/api/invoices/{iid}/email", json={"to": "a@b.de", "subject": "s", "body": "b"})
    assert r.status_code == 400


def test_invoice_place_defaults_to_profile_city(client):
    client.patch("/api/business-profile", json={"city": "Köln"})
    cid = client.post("/api/clients", json={"name": "City GmbH", "hourly_rate": "45"}).json()["id"]
    client.post("/api/time-entries", json={
        "client_id": cid, "started_at": "2026-06-01T09:00:00Z", "minutes": 60, "description": "x"})
    inv = client.post("/api/invoices", json={"client_id": cid}).json()
    assert inv["place"] == "Köln"


def test_blank_invoice_with_flat_and_hourly_lines(client):
    cid = client.post("/api/clients", json={"name": "Flat Co", "hourly_rate": "45"}).json()["id"]
    # a blank invoice needs no time entries
    inv = client.post("/api/invoices", json={"client_id": cid, "blank": True}).json()
    assert inv["items"] == []
    assert Decimal(str(inv["total"])) == Decimal("0")

    updated = client.put(f"/api/invoices/{inv['id']}/items", json=[
        {"description": "Projekt-Setup Pauschal", "hours": "0", "rate": "0", "amount": "800"},
        {"description": "Beratung", "hours": "2", "rate": "45"},  # amount omitted -> hours*rate
    ]).json()
    by_desc = {it["description"]: it for it in updated["items"]}
    assert Decimal(str(by_desc["Projekt-Setup Pauschal"]["amount"])) == Decimal("800.00")
    assert Decimal(str(by_desc["Beratung"]["amount"])) == Decimal("90.00")
    assert Decimal(str(updated["total"])) == Decimal("890.00")
    assert client.get(f"/api/invoices/{inv['id']}/pdf").status_code == 200


def test_invoice_auto_paid_from_matching_transactions(client):
    cid = _setup(client)  # invoice will total 90.00 (1.5h + 0.5h @ 45)
    inv = client.post("/api/invoices", json={"client_id": cid}).json()
    num = inv["number"]
    assert inv["status"] == "draft"
    acc = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]

    # partial payment → stays unpaid but shows the received amount
    client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2026-06-10T00:00:00Z", "amount": "40.00", "raw_payee": "p", "invoice_number": num})
    got = next(i for i in client.get("/api/invoices").json() if i["number"] == num)
    assert got["status"] != "paid"
    assert Decimal(str(got["paid_amount"])) == Decimal("40.00")

    # the rest → now fully covered → auto-marked paid
    client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2026-06-11T00:00:00Z", "amount": "50.00", "raw_payee": "p", "invoice_number": num})
    got = next(i for i in client.get("/api/invoices").json() if i["number"] == num)
    assert got["status"] == "paid"


def test_invoice_detail_lists_matching_payments(client):
    cid = _setup(client)
    inv = client.post("/api/invoices", json={"client_id": cid}).json()
    num, iid = inv["number"], inv["id"]
    acc = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2026-06-10T00:00:00Z", "amount": "45.00", "raw_payee": "Kunde", "invoice_number": num})
    detail = client.get(f"/api/invoices/{iid}").json()
    assert len(detail["payments"]) == 1
    assert Decimal(str(detail["payments"][0]["amount"])) == Decimal("45.00")
    assert detail["payments"][0]["account_name"] == "Giro"


def test_invoice_not_paid_by_refund_or_wrong_amount(client):
    cid = _setup(client)  # total 90.00
    inv = client.post("/api/invoices", json={"client_id": cid}).json()
    num = inv["number"]
    acc = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    # full payment then a refund (negative) → signed sum drops below total → not paid
    client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2026-06-10T00:00:00Z", "amount": "90.00", "raw_payee": "p", "invoice_number": num})
    client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2026-06-12T00:00:00Z", "amount": "-90.00", "raw_payee": "refund", "invoice_number": num})
    got = next(i for i in client.get("/api/invoices").json() if i["number"] == num)
    assert got["status"] != "paid"
    assert Decimal(str(got["paid_amount"])) == Decimal("0.00")


def test_invoice_due_date_and_overdue(client):
    client.patch("/api/business-profile", json={"payment_terms_days": 14})
    cid = _setup(client)
    inv = client.post("/api/invoices", json={"client_id": cid}).json()
    assert inv["due_date"] is not None  # auto-set from the payment term
    assert inv["overdue"] is False
    # sent + past due → overdue
    client.patch(f"/api/invoices/{inv['id']}", json={"status": "sent", "due_date": "2020-01-01"})
    assert client.get(f"/api/invoices/{inv['id']}").json()["overdue"] is True
    # a paid invoice is never overdue
    client.patch(f"/api/invoices/{inv['id']}", json={"status": "paid"})
    assert client.get(f"/api/invoices/{inv['id']}").json()["overdue"] is False


def test_send_reminder_bumps_mahnstufe(client, monkeypatch):
    import backend.api.invoices as inv_api

    class FakeSettings:
        smtp_configured = True
        smtp_host = "h"; smtp_port = 1; smtp_user = "u"; smtp_password = "p"; smtp_from = "f@x.de"

    monkeypatch.setattr(inv_api, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(inv_api, "send_invoice_email", lambda *a, **k: None)

    cid = _setup(client)
    iid = client.post("/api/invoices", json={"client_id": cid}).json()["id"]
    r = client.post(f"/api/invoices/{iid}/email",
                    json={"to": "a@b.de", "subject": "s", "body": "b", "reminder": True})
    assert r.status_code == 200 and r.json()["reminder_level"] == 1
    got = client.get(f"/api/invoices/{iid}").json()
    assert got["reminder_level"] == 1 and got["last_reminder_at"] is not None
    client.post(f"/api/invoices/{iid}/email", json={"to": "a@b.de", "reminder": True})
    assert client.get(f"/api/invoices/{iid}").json()["reminder_level"] == 2


def test_delete_invoice_unbills_entries_and_isolation(client, second_client):
    cid = _setup(client)
    iid = client.post("/api/invoices", json={"client_id": cid}).json()["id"]
    assert second_client.get(f"/api/invoices/{iid}").status_code == 404

    assert client.delete(f"/api/invoices/{iid}").status_code == 204
    # entries are unbilled again → a new invoice can bill them
    assert client.post("/api/invoices", json={"client_id": cid}).status_code == 201
