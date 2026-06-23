"""Emergency-fund endpoints: target (N× fixed costs or custom) + saved-so-far, with progress."""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, HTTPException

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
    # When an account is linked, "saved so far" is its live balance (like the Steuerrücklage);
    # otherwise it's the manually-tracked notional amount.
    account = (
        repository.get_account(session, fund.account_id, user_id)
        if fund.account_id is not None else None
    )
    current = Decimal(repository.account_balance(session, account)) if account is not None \
        else Decimal(fund.current_amount)
    target = (
        fund.target_amount
        if fund.target_amount is not None
        else Decimal(fund.target_months) * monthly_fixed
    )
    gap = target - current
    if gap < 0:
        gap = Decimal(0)
    funded = (current / target * 100) if target > 0 else Decimal(0)
    if funded > 100:
        funded = Decimal(100)
    return EmergencyFundOut(
        target_months=fund.target_months,
        target_amount=fund.target_amount,
        current_amount=_q(current),
        monthly_fixed=_q(monthly_fixed),
        target=_q(target),
        gap=_q(gap),
        funded_pct=_q(funded),
        account_id=fund.account_id if account is not None else None,
        account_name=account.name if account is not None else None,
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
    fields = payload.model_dump(exclude_unset=True)
    if fields.get("account_id") is not None and \
            repository.get_account(session, fields["account_id"], user.id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    repository.update_emergency_fund(session, fund, **fields)
    session.commit()
    return _fund_out(session, user.id, fund)
