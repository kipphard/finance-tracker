"""Reporting/aggregation endpoints for the dashboard (§6)."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import CategoryBreakdownItem

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/category-breakdown", response_model=list[CategoryBreakdownItem])
def category_breakdown(session: SessionDep, user: CurrentUser) -> list[CategoryBreakdownItem]:
    """Total transaction amount per category (signed), incl. an Uncategorized bucket."""
    categories = {c.id: c for c in repository.list_categories(session, user.id)}
    items: list[CategoryBreakdownItem] = []
    for category_id, total, count in repository.spending_by_category(session, user.id):
        category = categories.get(category_id)
        items.append(
            CategoryBreakdownItem(
                category_id=category_id,
                name=category.name if category else "Uncategorized",
                kind=category.kind if category else None,
                is_fixed=category.is_fixed if category else None,
                total=Decimal(str(total)),
                count=count,
            )
        )
    items.sort(key=lambda i: abs(i.total), reverse=True)
    return items
