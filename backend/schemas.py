"""Pydantic request/response DTOs for the REST API."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    type: str
    name: str
    currency: str = "EUR"
    institution: str | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connector: str
    type: str
    name: str
    currency: str
    institution: str | None = None
    created_at: datetime
    latest_balance: Decimal | None = None


class BalanceCreate(BaseModel):
    amount: Decimal
    ts: datetime | None = None


class BalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    amount: Decimal
    ts: datetime


class BreakdownItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: uuid.UUID
    name: str
    connector: str
    currency: str
    amount: Decimal


class NetWorthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    base_currency: str
    total: Decimal
    by_currency: dict[str, Decimal]
    breakdown: list[BreakdownItem]


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ts: datetime
    total: Decimal
    breakdown_json: dict
