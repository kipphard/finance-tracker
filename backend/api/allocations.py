"""Allocation endpoints: split the monthly leftover (income − fixed costs) into % buckets."""
from __future__ import annotations

import uuid
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
    allocation = repository.create_allocation(
        session, user_id=user.id, name=payload.name, percent=payload.percent
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
    repository.update_allocation(session, allocation, **payload.model_dump(exclude_unset=True))
    session.commit()
    return AllocationOut.model_validate(allocation)


@router.delete("/{allocation_id}", status_code=204)
def delete_allocation(
    allocation_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    if not repository.delete_allocation(session, allocation_id, user.id):
        raise HTTPException(status_code=404, detail="allocation not found")
    session.commit()
    return Response(status_code=204)
