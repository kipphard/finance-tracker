PDF = b"%PDF-1.4 fake invoice bytes"


def _txn(client):
    acc = client.post("/api/accounts", json={"type": "cash", "name": "X"}).json()["id"]
    return client.post(
        f"/api/accounts/{acc}/transactions",
        json={"ts": "2026-06-01T00:00:00Z", "amount": "-50", "raw_payee": "Shop"},
    ).json()["id"]


def test_attachment_lifecycle(client):
    txn = _txn(client)
    up = client.post(
        f"/api/transactions/{txn}/attachments",
        files={"file": ("invoice.pdf", PDF, "application/pdf")},
    )
    assert up.status_code == 201
    aid = up.json()["id"]
    assert up.json()["filename"] == "invoice.pdf"
    assert up.json()["size"] == len(PDF)

    assert len(client.get(f"/api/transactions/{txn}/attachments").json()) == 1

    dl = client.get(f"/api/attachments/{aid}")
    assert dl.status_code == 200
    assert dl.content == PDF
    assert "application/pdf" in dl.headers["content-type"]

    assert client.delete(f"/api/attachments/{aid}").status_code == 204
    assert client.get(f"/api/transactions/{txn}/attachments").json() == []


def test_attachment_download_handles_non_ascii_filename(client):
    txn = _txn(client)
    # macOS sends decomposed accents: "André" = "Andre" + combining acute (U+0301).
    name = "Invoice_André.pdf"
    aid = client.post(
        f"/api/transactions/{txn}/attachments",
        files={"file": (name, PDF, "application/pdf")},
    ).json()["id"]
    dl = client.get(f"/api/attachments/{aid}")
    assert dl.status_code == 200  # no UnicodeEncodeError on the Content-Disposition header
    assert dl.content == PDF


def test_attachment_rejects_disallowed_type(client):
    txn = _txn(client)
    bad = client.post(
        f"/api/transactions/{txn}/attachments",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert bad.status_code == 415


def test_attachment_isolation(client, second_client):
    txn = _txn(client)
    aid = client.post(
        f"/api/transactions/{txn}/attachments",
        files={"file": ("inv.pdf", PDF, "application/pdf")},
    ).json()["id"]
    # A different user can't download it or list this transaction's files.
    assert second_client.get(f"/api/attachments/{aid}").status_code == 404
    assert second_client.get(f"/api/transactions/{txn}/attachments").status_code == 404
