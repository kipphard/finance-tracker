"""Budget endpoints: per-category monthly limits + current-month tracking (§6)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.insights.service import budget_status
from backend.persistence import repository
from backend.schemas import BudgetCreate, BudgetOut, BudgetStatusOut, BudgetUpdate

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.post("", response_model=BudgetOut, status_code=201)
def create_budget(payload: BudgetCreate, session: SessionDep, user: CurrentUser) -> BudgetOut:
    if repository.get_category(session, payload.category_id, user.id) is None:
        raise HTTPException(status_code=400, detail="unknown category")
    if repository.get_budget_by_category(session, user.id, payload.category_id) is not None:
        raise HTTPException(status_code=409, detail="budget already exists for this category")
    budget = repository.create_budget(
        session, user_id=user.id, category_id=payload.category_id, monthly_limit=payload.monthly_limit
    )
    session.commit()
    return BudgetOut.model_validate(budget)


@router.get("", response_model=list[BudgetOut])
def list_budgets(session: SessionDep, user: CurrentUser) -> list[BudgetOut]:
    return [BudgetOut.model_validate(b) for b in repository.list_budgets(session, user.id)]


@router.get("/status", response_model=list[BudgetStatusOut])
def status(session: SessionDep, user: CurrentUser) -> list[BudgetStatusOut]:
    return [BudgetStatusOut(**vars(s)) for s in budget_status(session, user.id)]


@router.patch("/{budget_id}", response_model=BudgetOut)
def update_budget(
    budget_id: uuid.UUID, payload: BudgetUpdate, session: SessionDep, user: CurrentUser
) -> BudgetOut:
    budget = repository.get_budget(session, budget_id, user.id)
    if budget is None:
        raise HTTPException(status_code=404, detail="budget not found")
    repository.update_budget(session, budget, **payload.model_dump(exclude_unset=True))
    session.commit()
    return BudgetOut.model_validate(budget)


@router.delete("/{budget_id}", status_code=204)
def delete_budget(budget_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_budget(session, budget_id, user.id):
        raise HTTPException(status_code=404, detail="budget not found")
    session.commit()
    return Response(status_code=204)
