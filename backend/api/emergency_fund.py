"""Emergency-fund endpoints: target (N× fixed costs or custom) + saved-so-far, with progress."""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter

from backend.api.deps import CurrentUser, SessionDep
from backend.cashflow.service import compute_summary
from backend.persistence import repository
from backend.persistence.models import EmergencyFund
from backend.schemas import EmergencyFundOut, EmergencyFundUpdate

router = APIRouter(prefix="/emergency-fund", tags=["emergency-fund"])


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fund_out(session, user_id: uuid.UUID, fund: EmergencyFund) -> EmergencyFundOut:
    monthly_fixed = compute_summary(session, user_id).monthly_outflow
    target = (
        fund.target_amount
        if fund.target_amount is not None
        else Decimal(fund.target_months) * monthly_fixed
    )
    gap = target - fund.current_amount
    if gap < 0:
        gap = Decimal(0)
    funded = (fund.current_amount / target * 100) if target > 0 else Decimal(0)
    if funded > 100:
        funded = Decimal(100)
    return EmergencyFundOut(
        target_months=fund.target_months,
        target_amount=fund.target_amount,
        current_amount=fund.current_amount,
        monthly_fixed=_q(monthly_fixed),
        target=_q(target),
        gap=_q(gap),
        funded_pct=_q(funded),
    )


@router.get("", response_model=EmergencyFundOut)
def get_fund(session: SessionDep, user: CurrentUser) -> EmergencyFundOut:
    fund = repository.get_emergency_fund(session, user.id)
    session.commit()  # persist the default row if it was just created
    return _fund_out(session, user.id, fund)


@router.patch("", response_model=EmergencyFundOut)
def update_fund(
    payload: EmergencyFundUpdate, session: SessionDep, user: CurrentUser
) -> EmergencyFundOut:
    fund = repository.get_emergency_fund(session, user.id)
    repository.update_emergency_fund(session, fund, **payload.model_dump(exclude_unset=True))
    session.commit()
    return _fund_out(session, user.id, fund)
