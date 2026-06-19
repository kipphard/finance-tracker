"""Net-worth forecast from recurring cashflow (§5 polish)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api.deps import SessionDep
from backend.insights.service import build_forecast
from backend.schemas import ForecastOut, ForecastPointOut

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("", response_model=ForecastOut)
def forecast(session: SessionDep, months: int = Query(default=6, ge=1, le=36)) -> ForecastOut:
    result = build_forecast(session, months=months)
    return ForecastOut(
        base_currency=result.base_currency,
        current_total=result.current_total,
        monthly_net=result.monthly_net,
        points=[ForecastPointOut(month=p.month, projected=p.projected) for p in result.points],
    )
