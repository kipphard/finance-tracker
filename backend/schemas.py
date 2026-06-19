"""Pydantic request/response DTOs for the REST API."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from backend.persistence.models import Cadence, CashflowDirection, ConnectionStatus


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


# --- bank (GoCardless, Phase 1) ------------------------------------------


class RequisitionCreate(BaseModel):
    institution_id: str


class RequisitionCreateOut(BaseModel):
    connection_id: uuid.UUID
    requisition_id: str
    # The bank-authentication URL to send the user to (SCA).
    link: str
    status: str


class FinalizeOut(BaseModel):
    connection_id: uuid.UUID
    status: ConnectionStatus
    accounts: list[AccountOut]


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connector: str
    status: ConnectionStatus
    institution_id: str | None = None
    requisition_id: str | None = None
    reference: str | None = None
    consent_expires_at: datetime | None = None
    created_at: datetime


class SyncResultOut(BaseModel):
    accounts: int
    balances_recorded: int
    new_transactions: int


# --- manual cashflow (recurring inflows/outflows) ------------------------


class CashflowItemCreate(BaseModel):
    direction: CashflowDirection
    name: str
    amount: Decimal = Field(gt=0)
    cadence: Cadence = Cadence.monthly
    currency: str | None = None  # defaults to the configured base currency
    category_id: uuid.UUID | None = None
    next_due: date | None = None


class CashflowItemUpdate(BaseModel):
    name: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    cadence: Cadence | None = None
    next_due: date | None = None
    active: bool | None = None


class CashflowItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    direction: CashflowDirection
    name: str
    amount: Decimal
    cadence: Cadence
    currency: str
    category_id: uuid.UUID | None = None
    next_due: date | None = None
    active: bool
    created_at: datetime
    # Amount normalized to a monthly-equivalent figure.
    monthly_amount: Decimal | None = None


class CashflowSummaryOut(BaseModel):
    currency: str
    monthly_inflow: Decimal
    monthly_outflow: Decimal
    monthly_net: Decimal
    item_count: int
