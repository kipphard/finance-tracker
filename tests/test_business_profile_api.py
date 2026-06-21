from decimal import Decimal


def test_business_profile_default_then_update(client):
    p = client.get("/api/business-profile").json()
    assert p["next_invoice_number"] == 100001
    # The §19 note + intro now default at the (language-aware) PDF layer, so the profile
    # starts blank; the small-business flag defaults on, and German is the default language.
    assert p["vat_note"] == ""
    assert p["intro_text"] == ""
    assert p["is_kleinunternehmer"] is True
    assert p["default_language"] == "de"

    client.patch("/api/business-profile", json={
        "name": "André Kipphard", "company_name": "Kipphard Studio", "phone": "+49 151 000",
        "email": "andre@kipphard.com", "iban": "DE06 1001 0178 5405 8344 16",
        "tax_number": "339/2311/4033", "is_kleinunternehmer": False, "default_language": "en",
        "default_hourly_rate": "45", "next_invoice_number": 100077})
    p = client.get("/api/business-profile").json()
    assert p["name"] == "André Kipphard"
    assert p["company_name"] == "Kipphard Studio"
    assert p["phone"] == "+49 151 000"
    assert p["email"] == "andre@kipphard.com"
    assert p["is_kleinunternehmer"] is False
    assert p["default_language"] == "en"
    assert p["next_invoice_number"] == 100077
    assert Decimal(str(p["default_hourly_rate"])) == Decimal("45")


def test_digest_test_endpoint(client, monkeypatch):
    import backend.api.business_profile as bp

    class FakeSettings:
        smtp_configured = True
        smtp_host = "h"; smtp_port = 1; smtp_user = "u"; smtp_password = "p"; smtp_from = "f@x.de"

    sent = {}
    monkeypatch.setattr(bp, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(bp, "send_text_email", lambda settings, **kw: sent.update(kw))

    client.patch("/api/business-profile", json={"email": "me@x.de", "digest_cadence": "weekly"})
    r = client.post("/api/business-profile/digest-test")
    assert r.status_code == 200
    assert r.json()["to"] == "me@x.de"
    assert sent["to"] == "me@x.de"
    assert "bersicht" in sent["subject"]  # "Uebersicht"
