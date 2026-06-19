"""'To pay off' endpoints: one-off obligations the user needs to clear."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import DebtCreate, DebtOut, DebtUpdate

router = APIRouter(prefix="/debts", tags=["debts"])


@router.post("", response_model=DebtOut, status_code=201)
def create_debt(payload: DebtCreate, session: SessionDep, user: CurrentUser) -> DebtOut:
    debt = repository.create_debt(
        session, user_id=user.id, name=payload.name, amount=payload.amount, due_date=payload.due_date
    )
    session.commit()
    return DebtOut.model_validate(debt)


@router.get("", response_model=list[DebtOut])
def list_debts(
    session: SessionDep, user: CurrentUser, unpaid_only: bool = False
) -> list[DebtOut]:
    return [
        DebtOut.model_validate(d)
        for d in repository.list_debts(session, user.id, unpaid_only=unpaid_only)
    ]


@router.patch("/{debt_id}", response_model=DebtOut)
def update_debt(
    debt_id: uuid.UUID, payload: DebtUpdate, session: SessionDep, user: CurrentUser
) -> DebtOut:
    debt = repository.get_debt(session, debt_id, user.id)
    if debt is None:
        raise HTTPException(status_code=404, detail="debt not found")
    repository.update_debt(session, debt, **payload.model_dump(exclude_unset=True))
    session.commit()
    return DebtOut.model_validate(debt)


@router.delete("/{debt_id}", status_code=204)
def delete_debt(debt_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_debt(session, debt_id, user.id):
        raise HTTPException(status_code=404, detail="debt not found")
    session.commit()
    return Response(status_code=204)
