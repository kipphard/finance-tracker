"""Taxes: §32a tariff, EÜR computation (service-level) and the /api/tax endpoints."""
from datetime import datetime, timezone
from decimal import Decimal

from backend.persistence import repository
from backend.persistence.models import Account, Category, CategoryKind, Transaction
from backend.tax.eur import compute_eur
from backend.tax.tariff import income_tax


def test_tariff_known_points():
    # Below the Grundfreibetrag → no tax.
    assert income_tax(Decimal(10000), 2025) == Decimal(0)
    assert income_tax(Decimal(12096), 2025) == Decimal(0)
    # 2025 Grundtabelle reference points (statutory §32a formula, floored to euros).
    assert income_tax(Decimal(30000), 2025) == Decimal(4303)
    # 42% zone: 0.42*100000 - 10911.92 = 31088.08 → 31088.
    assert income_tax(Decimal(100000), 2025) == Decimal(31088)
    # Unknown year falls back to the newest available table (no crash).
    assert income_tax(Decimal(30000), 2099) > 0


def _seed_eur_data(db_session, user):
    acc = Account(user_id=user.id, connector="manual", type="checking", name="Giro", currency="EUR")
    db_session.add(acc)
    db_session.flush()
    inc = Category(user_id=user.id, name="Business income", kind=CategoryKind.income)
    soft = Category(user_id=user.id, name="Software", kind=CategoryKind.expense)
    net = Category(user_id=user.id, name="Internet", kind=CategoryKind.expense)
    db_session.add_all([inc, soft, net])
    db_session.flush()

    def txn(month, day, amount, payee, cat, is_business=False, excluded=False):
        db_session.add(Transaction(
            user_id=user.id, account_id=acc.id,
            ts=datetime(2025, month, day, tzinfo=timezone.utc), amount=Decimal(str(amount)),
            raw_payee=payee, category_id=cat.id, is_business=is_business, excluded=excluded,
            hash=f"{payee}{month}{day}{amount}",
        ))

    txn(3, 20, 12000, "Client A", inc, is_business=True)
    txn(9, 20, 12500, "Client B", inc, is_business=True)
    txn(2, 7, -800, "Laptop", soft, is_business=True)
    txn(4, 7, -240, "Adobe", soft, is_business=True, excluded=True)  # off-balance tax record
    for mth in range(1, 13):
        txn(mth, 3, -50, "Telekom", net)  # mixed-use, NOT business-flagged → 600 gross

    tp = repository.get_tax_profile(db_session, user.id)
    tp.mixed_use_rates = {str(net.id): 50}
    tp.home_office_mode = "flat"
    yi = repository.get_tax_year_input(db_session, user.id, 2025)
    yi.home_office_days = 120
    yi.business_km = Decimal(1500)
    yi.other_taxable_income = Decimal(54000)
    db_session.flush()
    return acc, net


def test_compute_eur_service(db_session, user):
    _seed_eur_data(db_session, user)
    eur = compute_eur(db_session, user.id, 2025)

    assert eur.income == Decimal("24500.00")
    # Software 800 + 240 (excluded counted) + Internet 600*50%=300 + HO 120*6=720 + 1500*0.30=450
    assert eur.expense_total == Decimal("2510.00")
    assert eur.profit == Decimal("21990.00")
    # marginal §32a estimate: tax(54000+21990) - tax(54000)
    expected = income_tax(Decimal(54000) + eur.profit, 2025) - income_tax(Decimal(54000), 2025)
    assert eur.tax_estimate == expected
    assert eur.tax_estimate > 0
    keys = {l.key for l in eur.expense_lines}
    assert keys == {"direct", "mixed", "home_office", "travel"}


def test_compute_eur_per_transaction_override(db_session, user):
    acc = Account(user_id=user.id, connector="manual", type="checking", name="Giro", currency="EUR")
    db_session.add(acc)
    db_session.flush()
    shop = Category(user_id=user.id, name="Shopping", kind=CategoryKind.expense)
    net = Category(user_id=user.id, name="Internet", kind=CategoryKind.expense)
    db_session.add_all([shop, net])
    db_session.flush()

    def txn(day, amount, payee, cat, is_business=False, pct=None):
        db_session.add(Transaction(
            user_id=user.id, account_id=acc.id,
            ts=datetime(2025, 6, day, tzinfo=timezone.utc), amount=Decimal(str(amount)),
            raw_payee=payee, category_id=cat.id, is_business=is_business,
            deductible_pct=None if pct is None else Decimal(str(pct)),
            hash=f"{payee}{day}{amount}",
        ))

    txn(1, 6000, "Client", shop, is_business=True)           # income (positive + business)
    txn(5, -200, "Werkzeug", shop, pct=30)                   # override on a non-mixed category
    txn(6, -100, "Buch", shop, is_business=True, pct=50)     # override wins over the 100% flag
    txn(7, -100, "Telekom", net)                             # category rate 50%
    txn(8, -100, "Telekom privat", net, pct=0)              # explicit 0% → nothing deductible

    tp = repository.get_tax_profile(db_session, user.id)
    tp.mixed_use_rates = {str(net.id): 50}
    db_session.flush()

    eur = compute_eur(db_session, user.id, 2025)

    assert eur.income == Decimal("6000.00")
    # Shopping: 200*30% + 100*50% = 110 ; Internet: 100*50% + 100*0% = 50
    assert eur.expense_total == Decimal("160.00")
    assert eur.profit == Decimal("5840.00")

    by_payee = {i.payee: i for i in eur.line_items}
    assert by_payee["Werkzeug"].bucket == "mixed"
    assert by_payee["Werkzeug"].percent == Decimal("30")
    assert by_payee["Werkzeug"].deductible == Decimal("60.00")
    # the explicit per-transaction % beats the freelance tag's 100%
    assert by_payee["Buch"].bucket == "mixed"
    assert by_payee["Buch"].deductible == Decimal("50.00")
    # both Shopping overrides aggregate into one mixed expense line
    shop_line = next(l for l in eur.expense_lines if l.label.startswith("Shopping"))
    assert shop_line.amount == Decimal("110.00")


def test_per_transaction_override_via_api(client):
    acc = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    # create with an override, then clear it, then set it again via PATCH
    t = client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2025-04-10T00:00:00Z", "amount": "-100", "raw_payee": "Werkzeug",
        "deductible_pct": "30",
    }).json()
    assert Decimal(str(t["deductible_pct"])) == Decimal("30")

    client.patch(f"/api/transactions/{t['id']}", json={"deductible_pct": None})
    assert client.get(f"/api/transactions/{t['id']}").json()["deductible_pct"] is None

    client.patch(f"/api/transactions/{t['id']}", json={"deductible_pct": "40"})
    assert Decimal(str(client.get(f"/api/transactions/{t['id']}").json()["deductible_pct"])) == Decimal("40")

    # out-of-range is rejected
    assert client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2025-04-11T00:00:00Z", "amount": "-100", "deductible_pct": "150",
    }).status_code == 422

    eur = client.get("/api/tax/eur", params={"year": 2025}).json()
    line = next(i for i in eur["line_items"] if i["payee"] == "Werkzeug")
    assert line["bucket"] == "mixed"
    assert Decimal(str(line["percent"])) == Decimal("40")
    assert Decimal(str(line["deductible"])) == Decimal("40.00")


def test_tax_profile_and_year_endpoints(client):
    # Default profile is created on first GET.
    prof = client.get("/api/tax/profile").json()
    assert prof["business_type"] == "freiberufler"

    upd = client.patch("/api/tax/profile", json={
        "home_office_mode": "flat",
        "mixed_use_rates": {"00000000-0000-0000-0000-000000000000": 50},
    }).json()
    assert upd["home_office_mode"] == "flat"

    year = client.patch("/api/tax/year/2025", json={
        "other_taxable_income": "54000", "home_office_days": 120, "business_km": "1500",
    }).json()
    assert year["year"] == 2025
    assert Decimal(str(year["other_taxable_income"])) == Decimal("54000")
    assert year["home_office_days"] == 120


def test_eur_elster_and_csv_endpoints(client):
    acc = client.post("/api/accounts", json={"type": "checking", "name": "Giro"}).json()["id"]
    cat = client.post("/api/categories", json={"name": "Software", "kind": "expense"}).json()["id"]

    inc = client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2025-05-10T00:00:00Z", "amount": "10000", "raw_payee": "Client", "is_business": True,
    }).json()
    exp = client.post(f"/api/accounts/{acc}/transactions", json={
        "ts": "2025-05-12T00:00:00Z", "amount": "-1000", "raw_payee": "Laptop", "is_business": True,
    }).json()
    client.patch(f"/api/transactions/{exp['id']}", json={"category_id": cat})
    assert inc["is_business"] is True

    client.patch("/api/tax/year/2025", json={"other_taxable_income": "40000"})

    eur = client.get("/api/tax/eur", params={"year": 2025}).json()
    assert Decimal(str(eur["income"])) == Decimal("10000.00")
    assert Decimal(str(eur["expense_total"])) == Decimal("1000.00")
    assert Decimal(str(eur["profit"])) == Decimal("9000.00")
    assert Decimal(str(eur["tax_estimate"])) > 0
    assert eur["tariff_year"] in (2024, 2025)

    prompt = client.get("/api/tax/elster-prompt", params={"year": 2025}).json()["prompt"]
    assert "Anlage EÜR" in prompt
    assert "9000" in prompt  # the profit shows up

    csv = client.get("/api/tax/export.csv", params={"year": 2025})
    assert csv.status_code == 200
    assert "text/csv" in csv.headers["content-type"]
    assert "Laptop" in csv.text
