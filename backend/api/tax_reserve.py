"""Tax-reserve (Steuerrücklage) endpoints: how much income tax to keep aside for the freelance
profit so far this year vs. how much actually is, with a recommended monthly set-aside."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.deps import CurrentUser, SessionDep
from backend.persistence import repository
from backend.schemas import TaxReserveOut, TaxReserveUpdate
from backend.tax.reserve import compute_reserve

router = APIRouter(prefix="/tax-reserve", tags=["tax-reserve"])


def _out(result) -> TaxReserveOut:
    return TaxReserveOut(**result.__dict__)


@router.get("", response_model=TaxReserveOut)
def get_reserve(session: SessionDep, user: CurrentUser) -> TaxReserveOut:
    result = compute_reserve(session, user.id)
    session.commit()  # persist the default row if it was just created
    return _out(result)


@router.patch("", response_model=TaxReserveOut)
def update_reserve(
    payload: TaxReserveUpdate, session: SessionDep, user: CurrentUser
) -> TaxReserveOut:
    fields = payload.model_dump(exclude_unset=True)
    # Validate the designated account belongs to the user (when one is given).
    account_id = fields.get("reserve_account_id")
    if account_id is not None and repository.get_account(session, account_id, user.id) is None:
        raise HTTPException(status_code=404, detail="account not found")
    reserve = repository.get_tax_reserve(session, user.id)
    repository.update_tax_reserve(session, reserve, **fields)
    session.commit()
    return _out(compute_reserve(session, user.id))
