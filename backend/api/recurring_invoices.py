"""Recurring (retainer) invoice templates that auto-draft an invoice each period."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.invoicing.recurring import materialize_recurring_invoices
from backend.persistence import repository
from backend.schemas import (
    RecurringInvoiceCreate,
    RecurringInvoiceOut,
    RecurringInvoiceUpdate,
)

router = APIRouter(prefix="/recurring-invoices", tags=["freelance"])


def _out(session, user_id: uuid.UUID, rec) -> RecurringInvoiceOut:
    out = RecurringInvoiceOut.model_validate(rec)
    client = repository.get_client(session, rec.client_id, user_id)
    out.client_name = client.name if client else None
    if rec.project_id is not None:
        project = repository.get_project(session, rec.project_id, user_id)
        out.project_name = project.name if project else None
    return out


def _ensure_client(session, user, client_id: uuid.UUID) -> None:
    if repository.get_client(session, client_id, user.id) is None:
        raise HTTPException(status_code=400, detail="unknown client")


@router.get("", response_model=list[RecurringInvoiceOut])
def list_recurring(session: SessionDep, user: CurrentUser) -> list[RecurringInvoiceOut]:
    return [_out(session, user.id, r) for r in repository.list_recurring_invoices(session, user.id)]


@router.post("", response_model=RecurringInvoiceOut, status_code=201)
def create_recurring(payload: RecurringInvoiceCreate, session: SessionDep, user: CurrentUser) -> RecurringInvoiceOut:
    _ensure_client(session, user, payload.client_id)
    data = payload.model_dump()
    if not data.get("language"):
        data["language"] = repository.get_business_profile(session, user.id).default_language
    rec = repository.create_recurring_invoice(session, user_id=user.id, **data)
    session.commit()
    return _out(session, user.id, rec)


@router.patch("/{rec_id}", response_model=RecurringInvoiceOut)
def update_recurring(
    rec_id: uuid.UUID, payload: RecurringInvoiceUpdate, session: SessionDep, user: CurrentUser
) -> RecurringInvoiceOut:
    rec = repository.get_recurring_invoice(session, rec_id, user.id)
    if rec is None:
        raise HTTPException(status_code=404, detail="recurring invoice not found")
    repository.update_recurring_invoice(session, rec, **payload.model_dump(exclude_unset=True))
    session.commit()
    return _out(session, user.id, rec)


@router.delete("/{rec_id}", status_code=204)
def delete_recurring(rec_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_recurring_invoice(session, rec_id, user.id):
        raise HTTPException(status_code=404, detail="recurring invoice not found")
    session.commit()
    return Response(status_code=204)


@router.post("/run")
def run_recurring(session: SessionDep, user: CurrentUser) -> dict:
    """Generate any due retainer drafts (catch-up + advance). Called on the Invoices tab load."""
    generated = materialize_recurring_invoices(session, user.id)
    if generated:
        session.commit()
    return {"generated": generated}
