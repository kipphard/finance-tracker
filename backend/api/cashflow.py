"""Manual cashflow endpoints: add/list/edit/delete recurring inflows & outflows + summary."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.cashflow.service import compute_summary, monthly_amount
from backend.config import get_settings
from backend.persistence import repository
from backend.persistence.models import Cadence, CashflowDirection, CashflowItem
from backend.schemas import (
    CashflowItemCreate,
    CashflowItemOut,
    CashflowItemUpdate,
    CashflowSummaryOut,
    PostResultOut,
)

router = APIRouter(prefix="/cashflow", tags=["cashflow"])


def _item_out(item: CashflowItem) -> CashflowItemOut:
    out = CashflowItemOut.model_validate(item)
    out.monthly_amount = monthly_amount(item).quantize(Decimal("0.01"))
    return out


@router.post("", response_model=CashflowItemOut, status_code=201)
def add_item(
    payload: CashflowItemCreate, session: SessionDep, user: CurrentUser
) -> CashflowItemOut:
    item = repository.create_cashflow_item(
        session,
        user_id=user.id,
        direction=payload.direction,
        name=payload.name,
        amount=payload.amount,
        cadence=payload.cadence,
        currency=payload.currency or get_settings().app_base_currency,
        category_id=payload.category_id,
        account_id=payload.account_id,
        next_due=payload.next_due,
    )
    session.commit()
    return _item_out(item)


@router.post("/post", response_model=PostResultOut)
def post_recurring(session: SessionDep, user: CurrentUser) -> PostResultOut:
    """Materialize active recurring items (that have a target account) as transactions for the
    current month. Idempotent — re-running the same month won't duplicate."""
    now = datetime.now(timezone.utc)
    period = f"{now.year:04d}-{now.month:02d}"
    period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    posted = skipped = 0
    for item in repository.list_cashflow_items(session, user.id, active_only=True):
        if item.account_id is None or item.cadence == Cadence.one_off:
            skipped += 1
            continue
        if repository.get_account(session, item.account_id, user.id) is None:
            skipped += 1
            continue
        amount = item.amount if item.direction == CashflowDirection.inflow else -item.amount
        _, created = repository.upsert_transaction(
            session,
            user_id=user.id,
            account_id=item.account_id,
            ts=period_start,
            amount=amount,
            currency=item.currency,
            hash=f"cf:{item.id}:{period}",
            raw_payee=item.name,
        )
        posted += 1 if created else 0
        skipped += 0 if created else 1
    session.commit()
    return PostResultOut(posted=posted, skipped=skipped)


@router.get("", response_model=list[CashflowItemOut])
def list_items(
    session: SessionDep, user: CurrentUser, direction: CashflowDirection | None = None
) -> list[CashflowItemOut]:
    return [
        _item_out(i)
        for i in repository.list_cashflow_items(session, user.id, direction=direction)
    ]


@router.get("/summary", response_model=CashflowSummaryOut)
def summary(session: SessionDep, user: CurrentUser) -> CashflowSummaryOut:
    result = compute_summary(session, user.id)
    return CashflowSummaryOut(
        currency=result.currency,
        monthly_inflow=result.monthly_inflow,
        monthly_outflow=result.monthly_outflow,
        monthly_net=result.monthly_net,
        item_count=result.item_count,
    )


@router.get("/{item_id}", response_model=CashflowItemOut)
def get_item(item_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> CashflowItemOut:
    item = repository.get_cashflow_item(session, item_id, user.id)
    if item is None:
        raise HTTPException(status_code=404, detail="cashflow item not found")
    return _item_out(item)


@router.patch("/{item_id}", response_model=CashflowItemOut)
def update_item(
    item_id: uuid.UUID, payload: CashflowItemUpdate, session: SessionDep, user: CurrentUser
) -> CashflowItemOut:
    item = repository.get_cashflow_item(session, item_id, user.id)
    if item is None:
        raise HTTPException(status_code=404, detail="cashflow item not found")
    repository.update_cashflow_item(session, item, **payload.model_dump(exclude_unset=True))
    session.commit()
    return _item_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_cashflow_item(session, item_id, user.id):
        raise HTTPException(status_code=404, detail="cashflow item not found")
    session.commit()
    return Response(status_code=204)
