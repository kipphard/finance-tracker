import uuid
from datetime import datetime, timezone
from decimal import Decimal

from backend.connectors.manual import ManualConnector
from backend.networth.aggregator import compute_net_worth
from backend.persistence import repository

TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _txn(db_session, user, account_id, amount, currency="EUR"):
    repository.upsert_transaction(
        db_session, user_id=user.id, account_id=account_id, ts=TS,
        amount=Decimal(amount), currency=currency, hash=uuid.uuid4().hex,
    )


def test_total_sums_transactions_per_account(db_session, user):
    connector = ManualConnector(db_session, user.id)
    a1 = connector.add_account(type="checking", name="A", currency="EUR")
    a2 = connector.add_account(type="cash", name="B", currency="EUR")
    db_session.commit()

    _txn(db_session, user, a1.id, "100")
    _txn(db_session, user, a1.id, "50")  # a1 = 150
    _txn(db_session, user, a2.id, "50")
    db_session.commit()

    net_worth = compute_net_worth(db_session, user.id)
    assert net_worth.total == Decimal("200")  # 150 + 50
    assert net_worth.by_currency["EUR"] == Decimal("200")
    assert len(net_worth.breakdown) == 2


def test_non_base_currency_excluded_from_total(db_session, user):
    connector = ManualConnector(db_session, user.id)
    eur = connector.add_account(type="checking", name="EUR acct", currency="EUR")
    usd = connector.add_account(type="brokerage", name="USD acct", currency="USD")
    db_session.commit()

    _txn(db_session, user, eur.id, "100", currency="EUR")
    _txn(db_session, user, usd.id, "80", currency="USD")
    db_session.commit()

    net_worth = compute_net_worth(db_session, user.id)
    assert net_worth.total == Decimal("100")  # base = EUR; USD not summed in
    assert net_worth.by_currency["USD"] == Decimal("80")
    assert net_worth.by_currency["EUR"] == Decimal("100")
