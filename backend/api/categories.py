"""Category taxonomy endpoints (§4.3)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.persistence.models import CategoryKind
from backend.schemas import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])

DEFAULT_CATEGORIES = [
    ("Salary", CategoryKind.income, True),
    ("Other Income", CategoryKind.income, False),
    ("Rent", CategoryKind.expense, True),
    ("Utilities", CategoryKind.expense, True),
    ("Internet", CategoryKind.expense, True),
    ("Mobile", CategoryKind.expense, True),
    ("Insurance", CategoryKind.expense, True),
    ("Subscriptions", CategoryKind.expense, True),
    ("Groceries", CategoryKind.expense, False),
    ("Dining", CategoryKind.expense, False),
    ("Transport", CategoryKind.expense, False),
    ("Shopping", CategoryKind.expense, False),
    ("Health", CategoryKind.expense, False),
    ("Leisure", CategoryKind.expense, False),
    ("Other", CategoryKind.expense, False),
]


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate, session: SessionDep, user: CurrentUser
) -> CategoryOut:
    if repository.get_category_by_name(session, user.id, payload.name) is not None:
        raise HTTPException(status_code=409, detail="category name already exists")
    category = repository.create_category(
        session, user_id=user.id, name=payload.name, kind=payload.kind, is_fixed=payload.is_fixed
    )
    session.commit()
    return CategoryOut.model_validate(category)


@router.post("/seed", response_model=list[CategoryOut], status_code=201)
def seed_defaults(session: SessionDep, user: CurrentUser) -> list[CategoryOut]:
    created = []
    for name, kind, is_fixed in DEFAULT_CATEGORIES:
        if repository.get_category_by_name(session, user.id, name) is None:
            created.append(
                repository.create_category(
                    session, user_id=user.id, name=name, kind=kind, is_fixed=is_fixed
                )
            )
    session.commit()
    return [CategoryOut.model_validate(c) for c in created]


@router.get("", response_model=list[CategoryOut])
def list_categories(session: SessionDep, user: CurrentUser) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in repository.list_categories(session, user.id)]


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> CategoryOut:
    category = repository.get_category(session, category_id, user.id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")
    return CategoryOut.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID, payload: CategoryUpdate, session: SessionDep, user: CurrentUser
) -> CategoryOut:
    category = repository.get_category(session, category_id, user.id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")
    if payload.name and payload.name != category.name:
        if repository.get_category_by_name(session, user.id, payload.name) is not None:
            raise HTTPException(status_code=409, detail="category name already exists")
    repository.update_category(session, category, **payload.model_dump(exclude_unset=True))
    session.commit()
    return CategoryOut.model_validate(category)


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_category(session, category_id, user.id):
        raise HTTPException(status_code=404, detail="category not found")
    session.commit()
    return Response(status_code=204)
