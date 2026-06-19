import uuid
from datetime import datetime, timezone
from decimal import Decimal

from backend.categorize.engine import categorize_transaction, recategorize_all
from backend.categorize.recurring import detect_recurring
from backend.persistence import repository
from backend.persistence.models import CategoryKind


def _account(session, user):
    return repository.create_account(
        session, user_id=user.id, connector="manual", type_="cash", name="Wallet", currency="EUR"
    )


def _txn(session, user, account_id, *, payee, amount="-10.00", ts=None):
    txn, _ = repository.upsert_transaction(
        session,
        user_id=user.id,
        account_id=account_id,
        ts=ts or datetime(2026, 3, 1, tzinfo=timezone.utc),
        amount=Decimal(amount),
        currency="EUR",
        hash=uuid.uuid4().hex,
        raw_payee=payee,
    )
    return txn


def test_rule_matches_and_categorizes(db_session, user):
    account = _account(db_session, user)
    groceries = repository.create_category(
        db_session, user_id=user.id, name="Groceries", kind=CategoryKind.expense
    )
    repository.create_rule(
        db_session, user_id=user.id, match_pattern="rewe", category_id=groceries.id, priority=100
    )
    db_session.commit()

    txn = _txn(db_session, user, account.id, payee="REWE Markt GmbH")
    assert categorize_transaction(db_session, user.id, txn) is True
    assert txn.category_id == groceries.id


def test_priority_highest_wins(db_session, user):
    account = _account(db_session, user)
    general = repository.create_category(db_session, user_id=user.id, name="Shopping", kind=CategoryKind.expense)
    specific = repository.create_category(db_session, user_id=user.id, name="Groceries", kind=CategoryKind.expense)
    repository.create_rule(db_session, user_id=user.id, match_pattern="markt", category_id=general.id, priority=100)
    repository.create_rule(db_session, user_id=user.id, match_pattern="rewe", category_id=specific.id, priority=200)
    db_session.commit()

    txn = _txn(db_session, user, account.id, payee="REWE Markt")
    categorize_transaction(db_session, user.id, txn)
    assert txn.category_id == specific.id  # priority 200 beats 100


def test_recategorize_all_only_uncategorized(db_session, user):
    account = _account(db_session, user)
    cat = repository.create_category(db_session, user_id=user.id, name="Music", kind=CategoryKind.expense)
    _txn(db_session, user, account.id, payee="Spotify AB")
    db_session.commit()

    assert recategorize_all(db_session, user.id) == 0
    repository.create_rule(db_session, user_id=user.id, match_pattern="spotify", category_id=cat.id)
    db_session.commit()
    assert recategorize_all(db_session, user.id) == 1
    assert recategorize_all(db_session, user.id) == 0  # already categorized


def test_detect_recurring_monthly(db_session, user):
    account = _account(db_session, user)
    for month in (1, 2, 3):
        _txn(db_session, user, account.id, payee="Netflix", amount="-12.99",
             ts=datetime(2026, month, 15, tzinfo=timezone.utc))
    for month in (1, 2):
        _txn(db_session, user, account.id, payee="OneOff Shop", amount="-5.00",
             ts=datetime(2026, month, 3, tzinfo=timezone.utc))
    db_session.commit()

    detected = detect_recurring(db_session, user.id)
    assert len(detected) == 1
    rec = detected[0]
    assert rec.payee == "Netflix"
    assert rec.cadence == "monthly"
    assert rec.amount_est == Decimal("-12.99")
    assert rec.next_due is not None
