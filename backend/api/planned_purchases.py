"""Planned purchases (wishlist): set a monthly amount to save for each item and
the app projects when you'll have saved enough.

Each item carries its own ``monthly_save`` (how much you set aside per month). The sum of those is
the "Planned purchases fund" — shown in the Distribute-leftover card as an off-the-top pot, so
committing to a purchase visibly shrinks what's left to split between Savings / Invest / Fun.
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


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _item_out(item, today) -> PlannedPurchaseOut:
    out = PlannedPurchaseOut.model_validate(item)
    save = Decimal(item.monthly_save or 0)
    if save > 0:
        out.months = max(1, math.ceil(Decimal(item.price) / save))
        out.target_month = _add_months_date(today, out.months)
    return out


@router.get("", response_model=PlannedPurchasesOut)
def list_purchases(session: SessionDep, user: CurrentUser) -> PlannedPurchasesOut:
    today = datetime.now(timezone.utc).date()
    rows = repository.list_planned_purchases(session, user.id)
    items = [_item_out(i, today) for i in rows]
    items.sort(key=lambda i: (i.months is None, i.months or 0))  # soonest first; unplanned last
    fund = _q(sum((Decimal(r.monthly_save or 0) for r in rows), Decimal(0)))
    summary = compute_summary(session, user.id)
    leftover = max(Decimal(0), Decimal(summary.monthly_net))
    return PlannedPurchasesOut(
        currency=summary.currency,
        monthly_leftover=_q(leftover),
        planned_fund=fund,
        items=items,
    )


@router.post("", response_model=PlannedPurchaseOut, status_code=201)
def create_purchase(payload: PlannedPurchaseCreate, session: SessionDep, user: CurrentUser) -> PlannedPurchaseOut:
    item = repository.create_planned_purchase(session, user_id=user.id, **payload.model_dump())
    session.commit()
    return _item_out(item, datetime.now(timezone.utc).date())


@router.patch("/{item_id}", response_model=PlannedPurchaseOut)
def update_purchase(
    item_id: uuid.UUID, payload: PlannedPurchaseUpdate, session: SessionDep, user: CurrentUser
) -> PlannedPurchaseOut:
    item = repository.get_planned_purchase(session, item_id, user.id)
    if item is None:
        raise HTTPException(status_code=404, detail="planned purchase not found")
    repository.update_planned_purchase(session, item, **payload.model_dump(exclude_unset=True))
    session.commit()
    return _item_out(item, datetime.now(timezone.utc).date())


@router.delete("/{item_id}", status_code=204)
def delete_purchase(item_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_planned_purchase(session, item_id, user.id):
        raise HTTPException(status_code=404, detail="planned purchase not found")
    session.commit()
    return Response(status_code=204)
