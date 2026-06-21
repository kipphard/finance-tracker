"""Planned purchases (wishlist): project when each item becomes affordable.

The monthly "free to save" is your leftover (income − fixed) minus what you've allocated to
debt, emergency fund and investing in the distribute-leftover buckets.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.cashflow.service import _add_months_date, compute_summary
from backend.persistence import repository
from backend.schemas import (
    PlannedPurchaseCreate,
    PlannedPurchaseOut,
    PlannedPurchaseUpdate,
    PlannedPurchasesOut,
)

router = APIRouter(prefix="/planned-purchases", tags=["planning"])

# allocation buckets that are NOT free for purchases (matched by name, case-insensitive)
COMMITTED = ("debt", "schuld", "emergency", "notgroschen", "notfall", "rücklage", "ruecklage",
             "invest", "etf", "rente", "aktien", "depot")


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _budget(session, user_id: uuid.UUID) -> tuple[Decimal, str]:
    summary = compute_summary(session, user_id)
    leftover = Decimal(summary.monthly_net)
    if leftover <= 0:
        return Decimal("0.00"), summary.currency
    committed = Decimal(0)
    for a in repository.list_allocations(session, user_id):
        if any(k in a.name.lower() for k in COMMITTED):
            committed += leftover * a.percent / Decimal(100)
    return _q(max(Decimal(0), leftover - committed)), summary.currency


def _item_out(item, budget: Decimal, today) -> PlannedPurchaseOut:
    out = PlannedPurchaseOut.model_validate(item)
    price = Decimal(item.price)
    if budget > 0 and price <= budget:
        out.affordable_now, out.months, out.target_month = True, 0, today
    elif budget > 0:
        out.months = math.ceil(price / budget)
        out.target_month = _add_months_date(today, out.months)
    return out


@router.get("", response_model=PlannedPurchasesOut)
def list_purchases(session: SessionDep, user: CurrentUser) -> PlannedPurchasesOut:
    budget, currency = _budget(session, user.id)
    today = datetime.now(timezone.utc).date()
    items = [_item_out(i, budget, today) for i in repository.list_planned_purchases(session, user.id)]
    items.sort(key=lambda i: (i.months is None, i.months or 0))  # soonest first; unreachable last
    return PlannedPurchasesOut(currency=currency, monthly_budget=budget, items=items)


@router.post("", response_model=PlannedPurchaseOut, status_code=201)
def create_purchase(payload: PlannedPurchaseCreate, session: SessionDep, user: CurrentUser) -> PlannedPurchaseOut:
    item = repository.create_planned_purchase(session, user_id=user.id, **payload.model_dump())
    session.commit()
    budget, _ = _budget(session, user.id)
    return _item_out(item, budget, datetime.now(timezone.utc).date())


@router.patch("/{item_id}", response_model=PlannedPurchaseOut)
def update_purchase(
    item_id: uuid.UUID, payload: PlannedPurchaseUpdate, session: SessionDep, user: CurrentUser
) -> PlannedPurchaseOut:
    item = repository.get_planned_purchase(session, item_id, user.id)
    if item is None:
        raise HTTPException(status_code=404, detail="planned purchase not found")
    repository.update_planned_purchase(session, item, **payload.model_dump(exclude_unset=True))
    session.commit()
    budget, _ = _budget(session, user.id)
    return _item_out(item, budget, datetime.now(timezone.utc).date())


@router.delete("/{item_id}", status_code=204)
def delete_purchase(item_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_planned_purchase(session, item_id, user.id):
        raise HTTPException(status_code=404, detail="planned purchase not found")
    session.commit()
    return Response(status_code=204)
