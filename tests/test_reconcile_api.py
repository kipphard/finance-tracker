"""Balance reconciliation: preview, commit (is_transfer adjusting entry), history, guards."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
TS = f"{datetime.now(timezone.utc).strftime('%Y-%m-01')}T00:00:00Z"


def _account(client, type_="checking"):
    return client.post("/api/accounts", json={"type": type_, "name": "Giro"}).json()["id"]


def _seed(client, acc, amount, **extra):
    client.post(f"/api/accounts/{acc}/transactions",
                json={"ts": TS, "amount": amount, "raw_payee": "x", **extra})


def test_preview_reports_delta(client):
    acc = _account(client)
    _seed(client, acc, "100")
    b = client.post(f"/api/accounts/{acc}/reconcile/preview",
                    json={"asserted_balance": "120", "as_of": TODAY}).json()
    assert Decimal(str(b["computed_balance"])) == Decimal("100")
    assert Decimal(str(b["delta"])) == Decimal("20")


def test_commit_books_transfer_and_fixes_balance(client):
    acc = _account(client)
    _seed(client, acc, "100")
    r = client.post(f"/api/accounts/{acc}/reconcile",
                    json={"asserted_balance": "120", "as_of": TODAY}).json()
    assert r["adjusted"] is True and r["transaction_id"]

    out = client.get(f"/api/accounts/{acc}").json()
    assert Decimal(str(out["latest_balance"])) == Decimal("120.00")

    adj = [t for t in client.get("/api/transactions").json()
           if t["raw_payee"] == "Balance reconciliation"]
    assert len(adj) == 1
    assert adj[0]["is_transfer"] is True
    assert Decimal(str(adj[0]["amount"])) == Decimal("20")


def test_adjustment_excluded_from_income_expense_and_eur(client):
    acc = _account(client)
    _seed(client, acc, "1000", raw_payee="Client", is_business=True)
    ie_before = client.get("/api/reports/income-expense").json()
    eur_before = client.get("/api/tax/eur").json()

    client.post(f"/api/accounts/{acc}/reconcile",
                json={"asserted_balance": "1500", "as_of": TODAY})

    ie_after = client.get("/api/reports/income-expense").json()
    eur_after = client.get("/api/tax/eur").json()
    assert ie_after["income"] == ie_before["income"]
    assert ie_after["expense"] == ie_before["expense"]
    assert eur_after["income"] == eur_before["income"]
    assert eur_after["expense_total"] == eur_before["expense_total"]


def test_noop_when_already_matching(client):
    acc = _account(client)
    _seed(client, acc, "100")
    r = client.post(f"/api/accounts/{acc}/reconcile",
                    json={"asserted_balance": "100", "as_of": TODAY}).json()
    assert r["adjusted"] is False and r["transaction_id"] is None
    assert client.get(f"/api/accounts/{acc}/reconcile/history").json() == []


def test_history_recorded(client):
    acc = _account(client)
    _seed(client, acc, "100")
    client.post(f"/api/accounts/{acc}/reconcile",
                json={"asserted_balance": "175", "as_of": TODAY})
    hist = client.get(f"/api/accounts/{acc}/reconcile/history").json()
    assert len(hist) == 1
    assert Decimal(str(hist[0]["asserted_balance"])) == Decimal("175")
    assert Decimal(str(hist[0]["delta"])) == Decimal("75")


def test_unknown_account_404(client):
    r = client.post(f"/api/accounts/{uuid.uuid4()}/reconcile/preview",
                    json={"asserted_balance": "1", "as_of": TODAY})
    assert r.status_code == 404
