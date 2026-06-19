"""The core abstraction from §4.1.

Everything that has a balance or transactions implements `AccountConnector`. The dataclasses
below are the connector-domain types the protocol returns — deliberately separate from the
SQLAlchemy models (persistence) and the Pydantic schemas (API surface).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Account:
    id: uuid.UUID
    connector: str
    type: str
    name: str
    currency: str
    institution: str | None = None


@dataclass(frozen=True)
class Balance:
    account_id: uuid.UUID
    amount: Decimal
    currency: str
    ts: datetime


@dataclass(frozen=True)
class Transaction:
    account_id: uuid.UUID
    ts: datetime
    amount: Decimal
    currency: str
    # Stable dedupe key (§4.2). Provider transaction id when available, else a content hash.
    hash: str
    raw_payee: str | None = None
    description: str | None = None
    external_id: str | None = None


@runtime_checkable
class AccountConnector(Protocol):
    """§4.1 — the one interface every account source implements."""

    name: str

    def list_accounts(self) -> list[Account]: ...

    def get_balance(self, account_id: str) -> Balance: ...

    def get_transactions(self, account_id: str, since: date) -> list[Transaction]: ...
