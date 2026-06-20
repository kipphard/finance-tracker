"""Net-worth forecast from recurring cashflow (§5 polish)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api.deps import CurrentUser, SessionDep
from backend.insights.service import build_forecast
from backend.schemas import ForecastOut, ForecastPointOut, ForecastSeriesOut

router = APIRouter(prefix="/forecast", tags=["forecast"])


def _points(points) -> list[ForecastPointOut]:
    return [ForecastPointOut(month=p.month, projected=p.projected) for p in points]


@router.get("", response_model=ForecastOut)
def forecast(
    session: SessionDep, user: CurrentUser, months: int = Query(default=6, ge=1, le=36)
) -> ForecastOut:
    result = build_forecast(session, user.id, months=months)
    return ForecastOut(
        base_currency=result.base_currency,
        current_total=result.current_total,
        monthly_net=result.monthly_net,
        points=_points(result.points),
        series=[
            ForecastSeriesOut(key=s.key, label=s.label, points=_points(s.points))
            for s in result.series
        ],
    )
