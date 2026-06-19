"""BankConnector — GoCardless implementation of the §4.1 AccountConnector.

Read methods fetch live from GoCardless and normalize the provider's response shapes into
the connector-domain dataclasses. Persistence happens in the sync engine, which calls these
methods and upserts the results — net worth then reads the synced values from the DB (so a
dashboard load never triggers a rate-limited provider call).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.connectors.base import Account, Balance, Transaction
from backend.connectors.gocardless.client import GoCardlessClient
from backend.persistence import repository
from backend.persistence.models import Account as AccountModel

# Preference order when an account reports multiple balance types.
_BALANCE_PRIORITY = (
    "interimAvailable",
    "closingBooked",
    "expected",
    "interimBooked",
    "openingBooked",
)


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _select_balance(balances: list[dict]) -> dict | None:
    by_type = {b.get("balanceType"): b for b in balances}
    for balance_type in _BALANCE_PRIORITY:
        if balance_type in by_type:
            return by_type[balance_type]
    return balances[0] if balances else None


class BankConnector:
    name = "gocardless"

    def __init__(self, session: Session, user_id: uuid.UUID, client: GoCardlessClient) -> None:
        self.session = session
        self.user_id = user_id
        self.client = client

    def _account(self, account_id: str | uuid.UUID) -> AccountModel:
        aid = account_id if isinstance(account_id, uuid.UUID) else uuid.UUID(str(account_id))
        account = repository.get_account(self.session, aid, self.user_id)
        if account is None or account.external_id is None:
            raise KeyError(f"no GoCardless account for id {aid}")
        return account

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
        account = self._account(account_id)
        payload = self.client.get_account_balances(account.external_id)
        selected = _select_balance(payload.get("balances", []))
        if selected is None:
            return Balance(
                account_id=account.id,
                amount=Decimal("0"),
                currency=account.currency,
                ts=datetime.now(timezone.utc),
            )
        amount_obj = selected.get("balanceAmount", {})
        return Balance(
            account_id=account.id,
            amount=Decimal(str(amount_obj.get("amount", "0"))),
            currency=amount_obj.get("currency", account.currency),
            ts=_parse_date(selected.get("referenceDate")),
        )

    def get_transactions(
        self, account_id: str | uuid.UUID, since: date | None = None
    ) -> list[Transaction]:
        account = self._account(account_id)
        date_from = since.isoformat() if since else None
        payload = self.client.get_account_transactions(
            account.external_id, date_from=date_from
        )
        booked = payload.get("transactions", {}).get("booked", [])
        result: list[Transaction] = []
        for raw in booked:
            amount_obj = raw.get("transactionAmount", {})
            amount = Decimal(str(amount_obj.get("amount", "0")))
            currency = amount_obj.get("currency", account.currency)
            ts = _parse_date(raw.get("bookingDate") or raw.get("valueDate"))
            payee = raw.get("creditorName") or raw.get("debtorName")
            description = raw.get("remittanceInformationUnstructured")
            external_id = raw.get("transactionId") or raw.get("internalTransactionId")
            txn_hash = external_id or hashlib.sha256(
                f"{account.external_id}|{ts.isoformat()}|{amount}|{description or ''}".encode()
            ).hexdigest()
            result.append(
                Transaction(
                    account_id=account.id,
                    ts=ts,
                    amount=amount,
                    currency=currency,
                    hash=txn_hash,
                    raw_payee=payee,
                    description=description,
                    external_id=external_id,
                )
            )
        return result
