"""Pydantic request/response DTOs for the REST API."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from pydantic import EmailStr

from backend.persistence.models import (
    Cadence,
    CashflowDirection,
    CategoryKind,
    ConnectionStatus,
)


# --- auth (Phase 6) -------------------------------------------------------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


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
    account_id: uuid.UUID | None = None  # target account for auto-posting
    next_due: date | None = None


class CashflowItemUpdate(BaseModel):
    name: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    cadence: Cadence | None = None
    account_id: uuid.UUID | None = None
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
    account_id: uuid.UUID | None = None
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


# --- categorization (Phase 2) --------------------------------------------


class CategoryCreate(BaseModel):
    name: str
    kind: CategoryKind
    is_fixed: bool = False


class CategoryUpdate(BaseModel):
    name: str | None = None
    kind: CategoryKind | None = None
    is_fixed: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: CategoryKind
    is_fixed: bool


class RuleCreate(BaseModel):
    match_pattern: str
    category_id: uuid.UUID
    priority: int = 100


class RuleUpdate(BaseModel):
    match_pattern: str | None = None
    category_id: uuid.UUID | None = None
    priority: int | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    match_pattern: str
    category_id: uuid.UUID
    priority: int


class TransactionCreate(BaseModel):
    ts: datetime
    amount: Decimal
    raw_payee: str | None = None
    description: str | None = None
    currency: str | None = None  # defaults to the account currency
    counterparty: str | None = None
    invoice_number: str | None = None
    vat_rate: Decimal | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    ts: datetime
    amount: Decimal
    currency: str
    raw_payee: str | None = None
    description: str | None = None
    category_id: uuid.UUID | None = None
    is_recurring: bool
    counterparty: str | None = None
    invoice_number: str | None = None
    vat_rate: Decimal | None = None


class TransactionUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    # If true, remember this payee -> category as a high-priority rule.
    remember: bool = False


class ImportResultOut(BaseModel):
    imported: int
    skipped_duplicates: int
    skipped_invalid: int
    categorized: int


class CategorizeResultOut(BaseModel):
    categorized: int


class RecurringOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payee: str
    amount_est: Decimal
    cadence: str
    next_due: date | None = None
    account_id: uuid.UUID


class DetectResultOut(BaseModel):
    detected: int
    items: list[RecurringOut]


class CategoryBreakdownItem(BaseModel):
    category_id: uuid.UUID | None = None
    name: str
    kind: CategoryKind | None = None
    is_fixed: bool | None = None
    total: Decimal
    count: int


# --- budgets / alerts / forecast (Phase 5) --------------------------------


class BudgetCreate(BaseModel):
    category_id: uuid.UUID
    monthly_limit: Decimal = Field(gt=0)


class BudgetUpdate(BaseModel):
    monthly_limit: Decimal | None = Field(default=None, gt=0)


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    monthly_limit: Decimal
    created_at: datetime


class BudgetStatusOut(BaseModel):
    budget_id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    monthly_limit: Decimal
    spent: Decimal
    remaining: Decimal
    pct_used: Decimal
    over: bool
    period: str


class AlertOut(BaseModel):
    level: str
    kind: str
    message: str


class ForecastPointOut(BaseModel):
    month: str
    projected: Decimal


class ForecastOut(BaseModel):
    base_currency: str
    current_total: Decimal
    monthly_net: Decimal
    points: list[ForecastPointOut]


# --- debts / to pay off ---------------------------------------------------


class DebtCreate(BaseModel):
    name: str
    amount: Decimal = Field(gt=0)
    due_date: date | None = None


class DebtUpdate(BaseModel):
    name: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    due_date: date | None = None
    paid: bool | None = None


class DebtOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    amount: Decimal
    due_date: date | None = None
    paid: bool
    created_at: datetime


# --- accounting reports (freelancer) --------------------------------------


class MonthlyCashflowPoint(BaseModel):
    month: str
    inflow: Decimal
    outflow: Decimal
    net: Decimal


class CategoryTotalOut(BaseModel):
    name: str
    kind: str | None = None
    total: Decimal
    count: int


class IncomeExpenseOut(BaseModel):
    start: str
    end: str
    income: Decimal
    expense: Decimal
    net: Decimal
    by_category: list[CategoryTotalOut]


class PostResultOut(BaseModel):
    posted: int
    skipped: int


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    filename: str
    content_type: str
    size: int
    created_at: datetime
