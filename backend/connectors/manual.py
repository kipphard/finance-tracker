"""ManualConnector — for anything with no API (cash, a friend's IOU, etc.).

Implements the read-only `AccountConnector` protocol against the database, plus manual-entry
write helpers (`add_account`, `add_balance`) that the REST endpoints use to let the user add
accounts and balances by hand.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.connectors.base import Account, Balance, Transaction
from backend.persistence import repository
from backend.persistence.models import Account as AccountModel
from backend.persistence.models import Balance as BalanceModel


def _to_uuid(account_id: str | uuid.UUID) -> uuid.UUID:
    return account_id if isinstance(account_id, uuid.UUID) else uuid.UUID(str(account_id))


class ManualConnector:
    name = "manual"

    def __init__(self, session: Session, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id

    # --- AccountConnector protocol (read) ---------------------------------

    def list_accounts(self) -> list[Account]:
        return [
            Account(
                id=a.id,
                connector=a.connector,
                type=a.type,
                name=a.name,
                currency=a.currency,
                institution=a.institution,
            )
            for a in repository.list_accounts(self.session, self.user_id, connector=self.name)
        ]

    def get_balance(self, account_id: str | uuid.UUID) -> Balance:
        aid = _to_uuid(account_id)
        account = repository.get_account(self.session, aid, self.user_id)
        if account is None:
            raise KeyError(f"account {aid} not found")
        latest = repository.latest_balance(self.session, aid)
        amount = latest.amount if latest is not None else Decimal("0")
        ts = latest.ts if latest is not None else datetime.now(timezone.utc)
        return Balance(account_id=aid, amount=amount, currency=account.currency, ts=ts)

    def get_transactions(
        self, account_id: str | uuid.UUID, since: date
    ) -> list[Transaction]:
        # Manual accounts have no transaction feed in Phase 0.
        return []

    # --- Manual entry (write) ---------------------------------------------

    def add_account(
        self,
        *,
        type: str,
        name: str,
        currency: str = "EUR",
        institution: str | None = None,
    ) -> AccountModel:
        return repository.create_account(
            self.session,
            user_id=self.user_id,
            connector=self.name,
            type_=type,
            name=name,
            currency=currency,
            institution=institution,
        )

    def add_balance(
        self,
        *,
        account_id: str | uuid.UUID,
        amount: Decimal,
        ts: datetime | None = None,
    ) -> BalanceModel:
        return repository.add_balance(
            self.session, account_id=_to_uuid(account_id), amount=amount, ts=ts
        )
