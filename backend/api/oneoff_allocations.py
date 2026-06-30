"""One-off allocation buckets: the windfall splitter's OWN set of percentage buckets, kept separate
from the monthly `allocations` so a bonus/gift/refund can be split however the user likes. Applying a
windfall reuses POST /allocations/distribute-oneoff (these endpoints are just CRUD for the buckets)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import (
    OneoffAllocationCreate,
    OneoffAllocationOut,
    OneoffAllocationUpdate,
)

router = APIRouter(prefix="/oneoff-allocations", tags=["oneoff-allocations"])


@router.get("", response_model=list[OneoffAllocationOut])
def list_oneoff_allocations(session: SessionDep, user: CurrentUser) -> list[OneoffAllocationOut]:
    return [
        OneoffAllocationOut.model_validate(b)
        for b in repository.list_oneoff_allocations(session, user.id)
    ]


@router.post("", response_model=OneoffAllocationOut, status_code=201)
def create_oneoff_allocation(
    payload: OneoffAllocationCreate, session: SessionDep, user: CurrentUser
) -> OneoffAllocationOut:
    if payload.account_id is not None and \
            repository.get_account(session, payload.account_id, user.id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    bucket = repository.create_oneoff_allocation(
        session, user_id=user.id, name=payload.name, percent=payload.percent,
        account_id=payload.account_id,
    )
    session.commit()
    return OneoffAllocationOut.model_validate(bucket)


@router.patch("/{bucket_id}", response_model=OneoffAllocationOut)
def update_oneoff_allocation(
    bucket_id: uuid.UUID, payload: OneoffAllocationUpdate, session: SessionDep, user: CurrentUser
) -> OneoffAllocationOut:
    bucket = repository.get_oneoff_allocation(session, bucket_id, user.id)
    if bucket is None:
        raise HTTPException(status_code=404, detail="bucket not found")
    data = payload.model_dump(exclude_unset=True)
    # account_id is handled explicitly so it can be cleared (set to null), which the generic
    # updater skips; validate it when given.
    if "account_id" in data:
        account_id = data.pop("account_id")
        if account_id is not None and repository.get_account(session, account_id, user.id) is None:
            raise HTTPException(status_code=404, detail="account not found")
        bucket.account_id = account_id
    repository.update_oneoff_allocation(session, bucket, **data)
    session.commit()
    return OneoffAllocationOut.model_validate(bucket)


@router.delete("/{bucket_id}", status_code=204)
def delete_oneoff_allocation(
    bucket_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    if not repository.delete_oneoff_allocation(session, bucket_id, user.id):
        raise HTTPException(status_code=404, detail="bucket not found")
    session.commit()
    return Response(status_code=204)
