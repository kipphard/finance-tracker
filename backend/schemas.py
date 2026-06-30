"""Pydantic request/response DTOs for the REST API."""
from __future__ import annotations

import datetime as _dt
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
    email: str  # output-only; real emails are validated on input (RegisterIn). Demo users use
    is_demo: bool = False  # the reserved demo+<id>@demo.invalid domain which EmailStr would reject.
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
    expected_return: Decimal = Field(default=Decimal(0), ge=-100, le=1000)


class AccountUpdate(BaseModel):
    type: str | None = None
    name: str | None = None
    currency: str | None = None
    institution: str | None = None
    expected_return: Decimal | None = Field(default=None, ge=-100, le=1000)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connector: str
    type: str
    name: str
    currency: str
    institution: str | None = None
    expected_return: Decimal = Decimal(0)
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


# --- reconciliation (assert the real balance, fix computed drift) --------


class ReconcileIn(BaseModel):
    asserted_balance: Decimal
    as_of: date


class ReconcilePreviewOut(BaseModel):
    account_id: uuid.UUID
    as_of: date
    computed_balance: Decimal     # sum of transactions up to as_of
    asserted_balance: Decimal     # the real balance the user entered
    delta: Decimal                # asserted − computed (the adjusting entry amount)
    currency: str


class ReconcileOut(ReconcilePreviewOut):
    adjusted: bool                # False when |delta| was ~0 (no entry booked)
    transaction_id: uuid.UUID | None = None


class ReconciliationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    as_of: date
    asserted_balance: Decimal
    computed_balance: Decimal
    delta: Decimal
    transaction_id: uuid.UUID | None = None
    created_at: datetime


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
    deductible_pct: Decimal | None = Field(default=None, ge=0, le=100)
    excluded: bool = False  # record-only: don't affect balances / net worth
    is_business: bool = False  # counts as business income/expense in the EÜR
    tags: list[str] = []


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
    deductible_pct: Decimal | None = None
    excluded: bool = False
    is_business: bool = False
    tags: list[str] = []
    is_transfer: bool = False
    series_id: uuid.UUID | None = None


class TransactionUpdate(BaseModel):
    ts: datetime | None = None
    amount: Decimal | None = None
    raw_payee: str | None = None
    description: str | None = None
    counterparty: str | None = None
    invoice_number: str | None = None
    vat_rate: Decimal | None = None
    deductible_pct: Decimal | None = Field(default=None, ge=0, le=100)
    category_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None  # move the transaction to another account
    excluded: bool | None = None
    is_business: bool | None = None
    tags: list[str] | None = None
    # If true, remember this payee -> category as a high-priority rule.
    remember: bool = False


class TransferCreate(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    ts: datetime | None = None
    note: str | None = None
    tags: list[str] = []


class TransferOut(BaseModel):
    from_transaction_id: uuid.UUID
    to_transaction_id: uuid.UUID
    amount: Decimal


class TransactionSeriesCreate(BaseModel):
    """Backfill one transaction per period between start and end (e.g. past freelancing months)."""

    start: date
    end: date
    cadence: Cadence
    amount: Decimal
    raw_payee: str | None = None
    description: str | None = None
    currency: str | None = None
    counterparty: str | None = None
    invoice_number: str | None = None
    vat_rate: Decimal | None = None
    deductible_pct: Decimal | None = Field(default=None, ge=0, le=100)
    excluded: bool = False
    is_business: bool = False
    tags: list[str] = []


class TransactionSeriesResult(BaseModel):
    created: int


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


class AllocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    percent: Decimal = Field(gt=0, le=100)
    account_id: uuid.UUID | None = None  # optional destination account for "Apply this month"
    earmarked: bool = False  # exclude the linked account from cash runway


class AllocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    percent: Decimal | None = Field(default=None, gt=0, le=100)
    account_id: uuid.UUID | None = None  # null clears the link
    earmarked: bool | None = None


class AllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    percent: Decimal
    account_id: uuid.UUID | None = None
    earmarked: bool = False
    created_at: datetime


class AllocationBucketOut(BaseModel):
    id: uuid.UUID
    name: str
    percent: Decimal
    amount: Decimal
    account_id: uuid.UUID | None = None
    earmarked: bool = False


class AllocationPlanOut(BaseModel):
    currency: str
    monthly_income: Decimal
    monthly_fixed: Decimal
    leftover: Decimal
    allocated_percent: Decimal
    unallocated_percent: Decimal
    unallocated_amount: Decimal
    buckets: list[AllocationBucketOut]
    last_applied_at: datetime | None = None  # most recent "Apply this month", for the re-run guard


class ApplyTransferItem(BaseModel):
    to_account_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    label: str = Field(min_length=1, max_length=200)


class ApplyDebtPayment(BaseModel):
    debt_id: uuid.UUID
    amount: Decimal = Field(gt=0)


class ApplyAllocationRequest(BaseModel):
    """Book this month's distribution: transfers from a source account into the linked buckets,
    plus debt payments (expenses) out of the source. Amounts are computed client-side from the plan."""
    source_account_id: uuid.UUID
    ts: datetime | None = None
    transfers: list[ApplyTransferItem] = []
    debt_payments: list[ApplyDebtPayment] = []


class ApplyAllocationResult(BaseModel):
    transfers_made: int
    debts_paid: int
    total_moved: Decimal


class OneoffDistributeRequest(BaseModel):
    """Distribute a one-off amount (a bonus, gift, refund — any windfall) across buckets/targets
    immediately. `amount` is the windfall the user typed and is informational only; the server books
    exactly the per-line transfer/debt amounts below, so the user can deliberately under- or
    over-allocate. Unlike "Apply this month" this never writes the monthly apply-log and has no
    once-a-month guard."""
    source_account_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    ts: datetime | None = None
    transfers: list[ApplyTransferItem] = []
    debt_payments: list[ApplyDebtPayment] = []


class OneoffDistributeResult(BaseModel):
    transfers_made: int
    debts_paid: int
    total_moved: Decimal


class EmergencyFundUpdate(BaseModel):
    target_months: int | None = Field(default=None, ge=0, le=120)
    target_amount: Decimal | None = Field(default=None, ge=0)  # custom override; null = N× fixed
    current_amount: Decimal | None = Field(default=None, ge=0)
    account_id: uuid.UUID | None = None  # account holding the fund; null tracks notionally
    account_priority: int | None = Field(default=None, ge=0)  # fill order on a shared account
    earmarked: bool | None = None  # exclude the linked account from cash runway


class EmergencyFundOut(BaseModel):
    target_months: int
    target_amount: Decimal | None
    current_amount: Decimal
    monthly_fixed: Decimal
    target: Decimal
    gap: Decimal
    funded_pct: Decimal
    account_id: uuid.UUID | None = None
    account_name: str | None = None
    account_priority: int = 100
    shared_with: str | None = None  # the other goal sharing the linked account, if any
    earmarked: bool = True


class TaxReserveUpdate(BaseModel):
    # null clears the link → fall back to the notional current_amount
    reserve_account_id: uuid.UUID | None = None
    current_amount: Decimal | None = Field(default=None, ge=0)
    account_priority: int | None = Field(default=None, ge=0)  # fill order on a shared account


class TaxReserveOut(BaseModel):
    year: int
    tariff_year: int
    income_ytd: Decimal
    profit_ytd: Decimal
    owed_ytd: Decimal
    reserve: Decimal
    gap: Decimal
    surplus: Decimal
    funded_pct: Decimal
    effective_rate: Decimal
    projected_annual_owed: Decimal
    recommended_monthly: Decimal
    reserve_account_id: uuid.UUID | None
    reserve_account_name: str | None
    current_amount: Decimal
    has_account: bool
    account_priority: int
    shared_with: str | None = None  # the other goal sharing the linked account, if any


class AlertOut(BaseModel):
    level: str
    kind: str
    message: str


class ForecastPointOut(BaseModel):
    month: str
    projected: Decimal


class ForecastSeriesOut(BaseModel):
    key: str
    label: str
    points: list[ForecastPointOut]


class ForecastOut(BaseModel):
    base_currency: str
    current_total: Decimal
    monthly_net: Decimal
    points: list[ForecastPointOut]
    series: list[ForecastSeriesOut] = []


# --- debts / to pay off ---------------------------------------------------


class PlannedPurchaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(gt=0)
    monthly_save: Decimal = Field(default=Decimal(0), ge=0)
    account_id: uuid.UUID | None = None
    earmarked: bool = False


class PlannedPurchaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    price: Decimal | None = Field(default=None, gt=0)
    monthly_save: Decimal | None = Field(default=None, ge=0)
    account_id: uuid.UUID | None = None
    earmarked: bool | None = None


class PlannedPurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    price: Decimal
    monthly_save: Decimal
    account_id: uuid.UUID | None = None
    earmarked: bool = False
    created_at: datetime
    # computed from monthly_save: how long until you've saved up for it
    months: int | None = None       # None = no monthly amount set yet
    target_month: date | None = None  # ~ when you'll have saved enough


class PlannedPurchasesOut(BaseModel):
    currency: str
    monthly_leftover: Decimal       # income − fixed costs (rough ceiling, before debt/emergency)
    planned_fund: Decimal           # Σ monthly_save — the "Planned purchases fund" pot
    items: list[PlannedPurchaseOut] = []


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


# --- trips (Fahrtenbuch) --------------------------------------------------


class TripCreate(BaseModel):
    # `_dt.date` (not `date`) so the field name `date` can't shadow the type at annotation-eval.
    date: _dt.date
    km: Decimal = Field(gt=0)
    from_place: str = ""
    to_place: str = ""
    purpose: str = ""
    client_id: uuid.UUID | None = None


class TripUpdate(BaseModel):
    date: _dt.date | None = None
    km: Decimal | None = Field(default=None, gt=0)
    from_place: str | None = None
    to_place: str | None = None
    purpose: str | None = None
    client_id: uuid.UUID | None = None


class TripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: _dt.date
    km: Decimal
    from_place: str
    to_place: str
    purpose: str
    client_id: uuid.UUID | None = None
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


# --- freelance: business profile, clients, time, invoices ----------------


class BusinessProfileUpdate(BaseModel):
    name: str | None = None
    company_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    iban: str | None = None
    bic: str | None = None
    tax_number: str | None = None
    is_kleinunternehmer: bool | None = None
    vat_note: str | None = None
    intro_text: str | None = None
    payment_terms_days: int | None = Field(default=None, ge=0)
    payment_info: str | None = None
    default_language: str | None = None
    digest_cadence: str | None = None
    digest_invoices: bool | None = None
    digest_time: bool | None = None
    digest_finance: bool | None = None
    default_hourly_rate: Decimal | None = Field(default=None, ge=0)
    next_invoice_number: int | None = Field(default=None, ge=0)


class BusinessProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    company_name: str
    phone: str
    email: str
    address: str
    postal_code: str
    city: str
    iban: str
    bic: str
    tax_number: str
    is_kleinunternehmer: bool
    vat_note: str
    intro_text: str
    payment_terms_days: int
    payment_info: str
    default_language: str
    digest_cadence: str
    digest_invoices: bool
    digest_time: bool
    digest_finance: bool
    default_hourly_rate: Decimal
    next_invoice_number: int


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = None
    address: str = ""
    hourly_rate: Decimal = Field(default=Decimal(0), ge=0)
    budget_hours: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = None
    address: str | None = None
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    budget_hours: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    archived: bool | None = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str | None = None
    address: str
    hourly_rate: Decimal
    budget_hours: Decimal | None = None
    notes: str | None = None
    archived: bool
    created_at: datetime
    # computed
    tracked_hours: Decimal = Decimal(0)
    unbilled_hours: Decimal = Decimal(0)
    unbilled_amount: Decimal = Decimal(0)


class ProjectCreate(BaseModel):
    client_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    hourly_rate: Decimal | None = Field(default=None, ge=0)  # None = inherit client's
    budget_hours: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    hourly_rate: Decimal | None = Field(default=None, ge=0)
    budget_hours: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    archived: bool | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    hourly_rate: Decimal | None = None
    budget_hours: Decimal | None = None
    notes: str | None = None
    archived: bool
    created_at: datetime
    # computed
    effective_rate: Decimal = Decimal(0)  # project rate, or the client's if not overridden
    tracked_hours: Decimal = Decimal(0)
    unbilled_hours: Decimal = Decimal(0)
    unbilled_amount: Decimal = Decimal(0)


class TimeEntryCreate(BaseModel):
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    started_at: datetime
    ended_at: datetime | None = None
    minutes: int | None = Field(default=None, ge=0)  # if omitted, derived from ended_at
    description: str | None = None


class TimeEntryStart(BaseModel):
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    description: str | None = None


class TimeEntryUpdate(BaseModel):
    client_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    minutes: int | None = Field(default=None, ge=0)
    description: str | None = None


class TimeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    started_at: datetime
    ended_at: datetime | None = None
    minutes: int
    description: str | None = None
    invoice_id: uuid.UUID | None = None
    created_at: datetime


class InvoiceCreate(BaseModel):
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None  # scope the invoice to one project's unbilled time
    language: str | None = None  # "de"/"en"; defaults to the business profile's default_language
    blank: bool = False  # create an empty draft (flat-fee billing) instead of from time entries
    from_date: date | None = None
    to_date: date | None = None
    entry_ids: list[uuid.UUID] | None = None  # explicit selection; else all unbilled (in range)
    # bundle entries into combined lines: "none" (one line per entry) | "project" | "week" | "month"
    group_by: str = "none"


class InvoiceItemIn(BaseModel):
    description: str = ""
    hours: Decimal = Field(default=Decimal(0), ge=0)
    rate: Decimal = Field(default=Decimal(0), ge=0)
    # explicit line total for flat/Pauschal lines; if omitted, amount = hours × rate
    amount: Decimal | None = Field(default=None, ge=0)


class InvoiceUpdate(BaseModel):
    number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    place: str | None = None
    language: str | None = None
    intro_text: str | None = None
    status: str | None = None
    vat_rate: Decimal | None = Field(default=None, ge=0)


class InvoiceEmail(BaseModel):
    to: str = Field(min_length=1)
    subject: str = ""
    body: str = ""
    from_: str | None = Field(default=None, alias="from")
    reminder: bool = False  # a payment reminder/Mahnung → bumps the Mahnstufe

    model_config = ConfigDict(populate_by_name=True)


class InvoicePaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ts: datetime
    amount: Decimal
    account_name: str | None = None
    payee: str | None = None


class InvoiceItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str
    hours: Decimal
    rate: Decimal
    amount: Decimal
    position: int


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    client_name: str | None = None
    project_id: uuid.UUID | None = None
    project_name: str | None = None
    number: str
    issue_date: date
    due_date: date | None = None
    place: str
    language: str
    intro_text: str
    status: str
    overdue: bool = False  # computed: sent/unpaid and past the due date
    reminder_level: int = 0  # Mahnstufe: 0 none, 1 Zahlungserinnerung, 2 = 1. Mahnung, …
    last_reminder_at: datetime | None = None
    vat_rate: Decimal
    total: Decimal
    paid_amount: Decimal = Decimal(0)  # signed sum of transactions tagged with this number
    created_at: datetime
    items: list[InvoiceItemOut] = []
    payments: list[InvoicePaymentOut] = []  # matched transactions (filled on the detail view)


class RecurringInvoiceCreate(BaseModel):
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    cadence: str = "monthly"
    mode: str = "flat"  # flat | time
    amount: Decimal = Field(default=Decimal(0), ge=0)
    description: str = ""
    language: str | None = None
    next_run: date
    active: bool = True


class RecurringInvoiceUpdate(BaseModel):
    project_id: uuid.UUID | None = None
    cadence: str | None = None
    mode: str | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    description: str | None = None
    language: str | None = None
    next_run: date | None = None
    active: bool | None = None


class RecurringInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    client_name: str | None = None
    project_id: uuid.UUID | None = None
    project_name: str | None = None
    cadence: str
    mode: str
    amount: Decimal
    description: str
    language: str
    next_run: date
    active: bool
    created_at: datetime


# ===== Analytics (cash runway, freelance profitability + project burn-down) =====


class RunwayOut(BaseModel):
    currency: str
    liquid: Decimal           # sum of liquid (non-investment) account balances
    monthly_net: Decimal      # average monthly net (negative = burning)
    runway_months: Decimal | None = None  # None when net-positive (no burn)
    earmarked: Decimal = Decimal(0)  # balance of earmarked accounts (e.g. tax reserve), excluded


# --- cashflow calendar (dated liquidity timeline) ------------------------


class CashEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    amount: Decimal           # signed: inflow > 0, outflow < 0
    direction: str            # "inflow" | "outflow"
    kind: str                 # cashflow_item | recurring_txn | invoice | planned_save | debt | tax
    label: str
    source_id: str | None = None


class CashflowDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    inflow: Decimal
    outflow: Decimal
    net: Decimal
    balance: Decimal          # projected running liquid balance at end of day
    events: list[CashEventOut] = []


class CashflowCalendarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    start_balance: Decimal
    days: list[CashflowDayOut]
    min_balance: Decimal              # the tightest projected balance in the window
    min_balance_date: date | None = None
    first_negative_date: date | None = None
    total_inflow: Decimal
    total_outflow: Decimal


# --- freelancer paycheck (safe-to-spend) ---------------------------------


class PaycheckLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    amount: Decimal


class PaycheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    sustainable_pay: Decimal
    trailing_net: Decimal
    trailing_income: Decimal
    monthly_fixed: Decimal
    tax_setaside: Decimal
    goal_setaside: Decimal
    liquid: Decimal
    capped_by_liquid: bool
    breakdown: list[PaycheckLineOut] = []


# --- rate advisor + what-if baseline --------------------------------------


class AdvisorClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    monthly_income: Decimal


class AdvisorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    liquid: Decimal
    monthly_net: Decimal
    monthly_income: Decimal
    monthly_fixed: Decimal
    tax_setaside: Decimal
    sustainable_pay: Decimal
    default_hourly_rate: Decimal
    billable_hours_month: Decimal
    marginal_tax_rate: Decimal
    annual_profit: Decimal
    annual_tax: Decimal
    clients: list[AdvisorClientOut] = []


# --- money wrapped (year in review) ---------------------------------------


class WrappedCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    amount: Decimal


class WrappedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    currency: str
    has_data: bool
    total_income: Decimal
    total_expense: Decimal
    net: Decimal
    top_categories: list[WrappedCategoryOut] = []
    biggest_expense_payee: str | None = None
    biggest_expense_amount: Decimal
    priciest_month: str | None = None
    priciest_month_amount: Decimal
    hours_worked: Decimal
    invoices_count: int
    invoiced_total: Decimal
    best_client_name: str | None = None
    best_client_rate: Decimal
    net_worth_delta: Decimal | None = None


# --- tax deadline calendar -----------------------------------------------


class TaxDeadlineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    kind: str                 # est_vorauszahlung | ust_voranmeldung | est_erklaerung
    label: str
    amount: Decimal | None = None
    note: str | None = None


class TaxCalendarOut(BaseModel):
    year: int
    is_kleinunternehmer: bool
    deadlines: list[TaxDeadlineOut]


class ClientProfitOut(BaseModel):
    client_id: uuid.UUID
    name: str
    tracked_hours: Decimal
    billed_hours: Decimal
    unbilled_hours: Decimal
    invoiced_total: Decimal
    paid_total: Decimal
    effective_rate: Decimal   # invoiced_total / tracked_hours


class ProjectBurnOut(BaseModel):
    project_id: uuid.UUID
    name: str
    client_name: str | None = None
    budget_hours: Decimal
    tracked_hours: Decimal
    remaining_hours: Decimal
    pct: Decimal              # tracked / budget * 100
    over_budget: bool


class FreelanceInsightsOut(BaseModel):
    clients: list[ClientProfitOut] = []
    projects: list[ProjectBurnOut] = []   # only projects that have a budget


# --- taxes: EÜR ----------------------------------------------------------


class TaxProfileUpdate(BaseModel):
    business_type: str | None = None          # freiberufler | gewerbe
    mixed_use_rates: dict[str, float] | None = None  # {category_id: percent}
    km_rate: Decimal | None = Field(default=None, ge=0)
    home_office_mode: str | None = None       # none | flat | room
    room_use_pauschale: bool | None = None
    room_sqm: Decimal | None = Field(default=None, ge=0)
    home_total_sqm: Decimal | None = Field(default=None, ge=0)
    home_annual_cost: Decimal | None = Field(default=None, ge=0)


class TaxProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_type: str
    mixed_use_rates: dict[str, float] = {}
    km_rate: Decimal
    home_office_mode: str
    room_use_pauschale: bool
    room_sqm: Decimal | None = None
    home_total_sqm: Decimal | None = None
    home_annual_cost: Decimal


class TaxYearInputUpdate(BaseModel):
    other_taxable_income: Decimal | None = Field(default=None, ge=0)
    withheld_lohnsteuer: Decimal | None = Field(default=None, ge=0)
    income_tax_prepaid: Decimal | None = Field(default=None, ge=0)
    home_office_days: int | None = Field(default=None, ge=0, le=365)
    business_km: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class TaxYearInputOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    other_taxable_income: Decimal
    withheld_lohnsteuer: Decimal
    income_tax_prepaid: Decimal
    home_office_days: int
    business_km: Decimal
    notes: str


class ExpenseLineOut(BaseModel):
    key: str                       # direct | mixed | home_office | travel
    label: str
    amount: Decimal
    gross: Decimal | None = None
    percent: Decimal | None = None
    count: int = 0


class TaxLineItemOut(BaseModel):
    date: str
    payee: str
    category: str | None = None
    bucket: str                    # income | direct | mixed
    amount: Decimal
    deductible: Decimal
    percent: Decimal | None = None  # business share applied (mixed bucket only)
    tags: list[str] = []


class EurReportOut(BaseModel):
    year: int
    business_type: str
    is_kleinunternehmer: bool
    income: Decimal
    expense_total: Decimal
    profit: Decimal
    expense_lines: list[ExpenseLineOut] = []
    line_items: list[TaxLineItemOut] = []
    other_income: Decimal
    tariff_year: int
    tax_with: Decimal
    tax_without: Decimal
    tax_estimate: Decimal
    # Full-year Erstattung/Nachzahlung: total income tax on (other income + profit) minus what's
    # already been paid. refund_or_owed > 0 = Nachzahlung owed; < 0 = Erstattung (refund).
    withheld_lohnsteuer: Decimal
    income_tax_prepaid: Decimal
    refund_or_owed: Decimal
    home_office_mode: str
    home_office_days: int
    business_km: Decimal
    km_rate: Decimal


class ElsterPromptOut(BaseModel):
    year: int
    prompt: str
