"""Rules-first categorization (§4.3).

A transaction's payee/description text is matched against the rules (case-insensitive
substring), highest `priority` first; the first match assigns the category. Transparent and
easy to correct — a manual override can be remembered as a new high-priority rule.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from backend.persistence import repository
from backend.persistence.models import Transaction


def _text(txn: Transaction) -> str:
    return f"{txn.raw_payee or ''} {txn.description or ''}".strip().lower()


def find_category_for_text(session: Session, user_id, text: str) -> uuid.UUID | None:
    haystack = text.lower()
    for rule in repository.list_rules(session, user_id):  # highest priority first
        if rule.match_pattern and rule.match_pattern.lower() in haystack:
            return rule.category_id
    return None


def categorize_transaction(
    session: Session, user_id, txn: Transaction, *, force: bool = False
) -> bool:
    """Set txn.category_id from the rules. Returns True if it changed."""
    if txn.category_id is not None and not force:
        return False
    category_id = find_category_for_text(session, user_id, _text(txn))
    if category_id is None or category_id == txn.category_id:
        return False
    txn.category_id = category_id
    return True


def recategorize_all(session: Session, user_id, *, only_uncategorized: bool = True) -> int:
    """Re-run the rules over existing transactions. Returns how many changed."""
    changed = 0
    for txn in repository.list_transactions(session, user_id):
        if only_uncategorized and txn.category_id is not None:
            continue
        if categorize_transaction(session, user_id, txn, force=not only_uncategorized):
            changed += 1
    session.flush()
    return changed
