"""Allocation endpoints: split the monthly leftover (income − fixed costs) into % buckets."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.cashflow.service import compute_summary
from backend.persistence import repository
from backend.schemas import (
    AllocationBucketOut,
    AllocationCreate,
    AllocationOut,
    AllocationPlanOut,
    AllocationUpdate,
    ApplyAllocationRequest,
    ApplyAllocationResult,
)

router = APIRouter(prefix="/allocations", tags=["allocations"])


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _plan(session, user_id: uuid.UUID) -> AllocationPlanOut:
    summary = compute_summary(session, user_id)
    leftover = summary.monthly_net
    base = leftover if leftover > 0 else Decimal(0)  # don't distribute a deficit

    buckets: list[AllocationBucketOut] = []
    allocated = Decimal(0)
    for a in repository.list_allocations(session, user_id):
        allocated += a.percent
        buckets.append(
            AllocationBucketOut(
                id=a.id,
                name=a.name,
                percent=a.percent,
                amount=_q(base * a.percent / Decimal(100)),
                account_id=a.account_id,
                earmarked=a.earmarked,
            )
        )

    unallocated_pct = Decimal(100) - allocated
    unallocated_amount = (
        _q(base * unallocated_pct / Decimal(100)) if unallocated_pct > 0 else Decimal("0.00")
    )
    return AllocationPlanOut(
        currency=summary.currency,
        monthly_income=summary.monthly_inflow,
        monthly_fixed=summary.monthly_outflow,
        leftover=_q(leftover),
        allocated_percent=_q(allocated),
        unallocated_percent=_q(unallocated_pct),
        unallocated_amount=unallocated_amount,
        buckets=buckets,
        last_applied_at=repository.last_allocation_apply(session, user_id),
    )


@router.get("/plan", response_model=AllocationPlanOut)
def get_plan(session: SessionDep, user: CurrentUser) -> AllocationPlanOut:
    return _plan(session, user.id)


@router.get("", response_model=list[AllocationOut])
def list_allocations(session: SessionDep, user: CurrentUser) -> list[AllocationOut]:
    return [AllocationOut.model_validate(a) for a in repository.list_allocations(session, user.id)]


@router.post("", response_model=AllocationOut, status_code=201)
def create_allocation(
    payload: AllocationCreate, session: SessionDep, user: CurrentUser
) -> AllocationOut:
    if payload.account_id is not None and \
            repository.get_account(session, payload.account_id, user.id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    allocation = repository.create_allocation(
        session, user_id=user.id, name=payload.name, percent=payload.percent,
        account_id=payload.account_id, earmarked=payload.earmarked,
    )
    session.commit()
    return AllocationOut.model_validate(allocation)


@router.patch("/{allocation_id}", response_model=AllocationOut)
def update_allocation(
    allocation_id: uuid.UUID, payload: AllocationUpdate, session: SessionDep, user: CurrentUser
) -> AllocationOut:
    allocation = repository.get_allocation(session, allocation_id, user.id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="allocation not found")
    data = payload.model_dump(exclude_unset=True)
    # account_id is handled explicitly so it can be cleared (set to null), which the generic
    # updater skips; validate it when given.
    if "account_id" in data:
        account_id = data.pop("account_id")
        if account_id is not None and repository.get_account(session, account_id, user.id) is None:
            raise HTTPException(status_code=404, detail="account not found")
        allocation.account_id = account_id
    repository.update_allocation(session, allocation, **data)
    session.commit()
    return AllocationOut.model_validate(allocation)


@router.post("/apply", response_model=ApplyAllocationResult)
def apply_allocation(
    payload: ApplyAllocationRequest, session: SessionDep, user: CurrentUser
) -> ApplyAllocationResult:
    """Book this month's distribution in one atomic step: transfer each linked bucket's share from
    the source account into it, and pay each ticked debt as an expense out of the source (reducing
    or clearing the debt). Amounts are computed client-side from the plan."""
    source = repository.get_account(session, payload.source_account_id, user.id)
    if source is None:
        raise HTTPException(status_code=404, detail="source account not found")

    ts = payload.ts or datetime.now(timezone.utc)
    total = Decimal(0)

    # Savings-type moves → transfers (out of source, into the bucket account).
    for t in payload.transfers:
        if t.to_account_id == source.id:
            raise HTTPException(status_code=400, detail="bucket account equals the source account")
        dst = repository.get_account(session, t.to_account_id, user.id)
        if dst is None:
            raise HTTPException(status_code=404, detail="bucket account not found")
        repository.upsert_transaction(
            session, user_id=user.id, account_id=source.id, ts=ts, amount=-t.amount,
            currency=source.currency, hash=uuid.uuid4().hex,
            raw_payee=f"Transfer to {dst.name}", description=t.label, is_transfer=True,
        )
        repository.upsert_transaction(
            session, user_id=user.id, account_id=dst.id, ts=ts, amount=t.amount,
            currency=dst.currency, hash=uuid.uuid4().hex,
            raw_payee=f"Transfer from {source.name}", description=t.label, is_transfer=True,
        )
        total += t.amount

    # Debt payments → real expenses out of the source; reduce or clear the debt.
    debts_paid = 0
    for p in payload.debt_payments:
        debt = repository.get_debt(session, p.debt_id, user.id)
        if debt is None:
            raise HTTPException(status_code=404, detail="debt not found")
        repository.upsert_transaction(
            session, user_id=user.id, account_id=source.id, ts=ts, amount=-p.amount,
            currency=source.currency, hash=uuid.uuid4().hex,
            raw_payee=f"Schuld: {debt.name}", description="Debt payment",
        )
        if p.amount >= Decimal(debt.amount):
            debt.paid = True
        else:
            debt.amount = Decimal(debt.amount) - p.amount
        debts_paid += 1
        total += p.amount

    repository.create_allocation_apply(session, user_id=user.id, applied_at=ts, total_moved=_q(total))
    session.commit()
    return ApplyAllocationResult(
        transfers_made=len(payload.transfers), debts_paid=debts_paid, total_moved=_q(total),
    )


@router.delete("/{allocation_id}", status_code=204)
def delete_allocation(
    allocation_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    if not repository.delete_allocation(session, allocation_id, user.id):
        raise HTTPException(status_code=404, detail="allocation not found")
    session.commit()
    return Response(status_code=204)
