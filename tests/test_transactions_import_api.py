def _account(client):
    return client.post(
        "/accounts", json={"type": "checking", "name": "Giro", "currency": "EUR"}
    ).json()["id"]


def _upload(client, account_id, content: str):
    return client.post(
        f"/accounts/{account_id}/transactions/import",
        files={"file": ("statement.csv", content.encode("utf-8"), "text/csv")},
    )


def test_csv_import_and_dedupe(client):
    account_id = _account(client)
    csv = (
        "date,amount,payee,description\n"
        "2026-03-01,-12.34,REWE,Groceries\n"
        "2026-03-02,-9.99,Spotify,Music\n"
        "bad-row,not-a-number,X,Y\n"
    )
    first = _upload(client, account_id, csv).json()
    assert first["imported"] == 2
    assert first["skipped_invalid"] == 1

    # Re-importing the same file is idempotent (content hash dedupe).
    second = _upload(client, account_id, csv).json()
    assert second["imported"] == 0
    assert second["skipped_duplicates"] == 2

    assert len(client.get("/transactions", params={"account_id": account_id}).json()) == 2


def test_csv_import_german_format(client):
    account_id = _account(client)
    csv = (
        "Datum;Betrag;Name;Verwendungszweck\n"
        "01.03.2026;-12,99;Spotify;Abo\n"
        "02.03.2026;-1.234,56;Moebel Haus;Sofa\n"
    )
    result = _upload(client, account_id, csv).json()
    assert result["imported"] == 2

    txns = client.get("/transactions", params={"account_id": account_id}).json()
    amounts = sorted(t["amount"] for t in txns)
    # -1234.56 and -12.99 (string compare avoided by mapping to Decimal-like sort)
    assert any("1234.56" in a for a in amounts)


def test_import_autocategorizes_with_rules(client):
    account_id = _account(client)
    client.post("/categories/seed")
    groceries = next(
        c for c in client.get("/categories").json() if c["name"] == "Groceries"
    )["id"]
    client.post("/rules", json={"match_pattern": "rewe", "category_id": groceries})

    csv = "date,amount,payee\n2026-03-01,-50.00,REWE City\n2026-03-02,-5.00,Unknown Shop\n"
    result = _upload(client, account_id, csv).json()
    assert result["imported"] == 2
    assert result["categorized"] == 1

    uncategorized = client.get("/transactions", params={"uncategorized": True}).json()
    assert len(uncategorized) == 1
    assert uncategorized[0]["raw_payee"] == "Unknown Shop"


def test_recurring_detection_via_api(client):
    account_id = _account(client)
    for month in (1, 2, 3):
        client.post(
            f"/accounts/{account_id}/transactions",
            json={
                "ts": f"2026-0{month}-15T00:00:00Z",
                "amount": "-12.99",
                "raw_payee": "Netflix",
            },
        )

    detected = client.post("/recurring/detect").json()
    assert detected["detected"] == 1
    assert detected["items"][0]["cadence"] == "monthly"

    listing = client.get("/recurring").json()
    assert len(listing) == 1
    assert listing[0]["payee"] == "Netflix"
