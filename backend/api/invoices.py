"""Freelance invoices: build from unbilled time entries, edit line items, render a PDF."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from backend.api.deps import CurrentUser, SessionDep
from backend.config import get_settings
from backend.invoicing.email import send_invoice_email
from backend.invoicing.i18n import texts
from backend.invoicing.pdf import render_invoice
from backend.invoicing.text import flatten
from backend.persistence import repository
from backend.persistence.models import InvoiceItem
from backend.schemas import (
    InvoiceCreate,
    InvoiceEmail,
    InvoiceItemIn,
    InvoiceOut,
    InvoicePaymentOut,
    InvoiceUpdate,
)

router = APIRouter(prefix="/invoices", tags=["freelance"])


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _hours(minutes: int) -> Decimal:
    return _q(Decimal(minutes) / Decimal(60))


def _gross(net: Decimal, vat_rate: Decimal) -> Decimal:
    return _q(net * (Decimal(1) + (vat_rate / Decimal(100))))


def _invoice_out(session, user_id: uuid.UUID, invoice) -> InvoiceOut:
    out = InvoiceOut.model_validate(invoice)
    client = repository.get_client(session, invoice.client_id, user_id)
    out.client_name = client.name if client else None
    if invoice.project_id is not None:
        project = repository.get_project(session, invoice.project_id, user_id)
        out.project_name = project.name if project else None
    out.paid_amount = repository.invoice_paid_amount(session, user_id, invoice.number)
    out.overdue = (
        invoice.status != "paid"
        and invoice.due_date is not None
        and invoice.due_date < datetime.now(timezone.utc).date()
    )
    return out


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    session: SessionDep, user: CurrentUser, client_id: uuid.UUID | None = None
) -> list[InvoiceOut]:
    if repository.reconcile_invoice_payments(session, user.id):  # auto-mark paid from transactions
        session.commit()
    return [
        _invoice_out(session, user.id, inv)
        for inv in repository.list_invoices(session, user.id, client_id=client_id)
    ]


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(payload: InvoiceCreate, session: SessionDep, user: CurrentUser) -> InvoiceOut:
    client = repository.get_client(session, payload.client_id, user.id)
    if client is None:
        raise HTTPException(status_code=400, detail="unknown client")
    profile = repository.get_business_profile(session, user.id)

    # optional project scope must belong to this client
    project = None
    if payload.project_id is not None:
        project = repository.get_project(session, payload.project_id, user.id)
        if project is None or project.client_id != client.id:
            raise HTTPException(status_code=400, detail="unknown project for this client")

    language = (payload.language or profile.default_language or "de").lower()
    if language not in ("de", "en"):
        language = "de"
    intro = profile.intro_text or texts(language)["intro_default"]
    vat_rate = Decimal(0) if profile.is_kleinunternehmer else Decimal("19")
    issue = datetime.now(timezone.utc).date()
    due = issue + timedelta(days=profile.payment_terms_days)

    # Blank invoice: skip time entries entirely (flat-fee billing) — start empty, fill lines later.
    if payload.blank:
        number = str(profile.next_invoice_number)
        profile.next_invoice_number += 1
        invoice = repository.create_invoice(
            session, user_id=user.id, client_id=client.id, project_id=payload.project_id,
            number=number, issue_date=issue, due_date=due,
            place=(profile.city or ""), language=language, intro_text=intro,
            status="draft", vat_rate=vat_rate, total=Decimal(0),
        )
        session.commit()
        return _invoice_out(session, user.id, invoice)

    if payload.entry_ids:
        entries = []
        for eid in payload.entry_ids:
            e = repository.get_time_entry(session, eid, user.id)
            if e is None or e.client_id != client.id or e.invoice_id is not None:
                raise HTTPException(status_code=400, detail="invalid or already-billed time entry")
            entries.append(e)
    else:
        start = (
            datetime.combine(payload.from_date, time(0, 0), tzinfo=timezone.utc)
            if payload.from_date else None
        )
        end = (
            datetime.combine(payload.to_date, time(0, 0), tzinfo=timezone.utc) + timedelta(days=1)
            if payload.to_date else None
        )
        entries = repository.list_time_entries(
            session, user.id, client_id=client.id, project_id=payload.project_id,
            unbilled=True, start=start, end=end,
        )
    if not entries:
        raise HTTPException(status_code=400, detail="no unbilled time entries for this selection")

    # each entry bills at its project's rate override, falling back to the client's rate
    rate_cache: dict[uuid.UUID, Decimal] = {}

    def _rate_for(entry) -> Decimal:
        if entry.project_id is None:
            return client.hourly_rate
        if entry.project_id not in rate_cache:
            proj = repository.get_project(session, entry.project_id, user.id)
            rate_cache[entry.project_id] = (
                proj.hourly_rate if proj and proj.hourly_rate is not None else client.hourly_rate
            )
        return rate_cache[entry.project_id]

    entries.sort(key=lambda e: e.started_at)
    items: list[InvoiceItem] = []
    net = Decimal(0)
    for i, e in enumerate(entries):
        hrs = _hours(e.minutes)
        rate = _rate_for(e)
        amount = _q(hrs * rate)
        net += amount
        items.append(InvoiceItem(
            description=flatten(e.description) or "Service", hours=hrs,
            rate=rate, amount=amount, position=i,
        ))

    number = str(profile.next_invoice_number)
    profile.next_invoice_number += 1
    invoice = repository.create_invoice(
        session, user_id=user.id, client_id=client.id,
        project_id=payload.project_id, number=number,
        issue_date=issue, due_date=due, place=(profile.city or ""),
        language=language, intro_text=intro, status="draft", vat_rate=vat_rate,
        total=_gross(net, vat_rate),
    )
    invoice.items = items
    for e in entries:
        e.invoice_id = invoice.id
    session.commit()
    return _invoice_out(session, user.id, invoice)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> InvoiceOut:
    invoice = repository.get_invoice(session, invoice_id, user.id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    if repository.reconcile_invoice_payments(session, user.id):  # auto-mark paid from transactions
        session.commit()
    out = _invoice_out(session, user.id, invoice)
    txns = repository.list_invoice_transactions(session, user.id, invoice.number)
    if txns:
        accounts = {a.id: a.name for a in repository.list_accounts(session, user.id)}
        out.payments = [
            InvoicePaymentOut(id=t.id, ts=t.ts, amount=t.amount,
                              account_name=accounts.get(t.account_id), payee=t.raw_payee)
            for t in txns
        ]
    return out


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: uuid.UUID, payload: InvoiceUpdate, session: SessionDep, user: CurrentUser
) -> InvoiceOut:
    invoice = repository.get_invoice(session, invoice_id, user.id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    repository.update_invoice(session, invoice, **payload.model_dump(exclude_unset=True))
    session.commit()
    return _invoice_out(session, user.id, invoice)


@router.put("/{invoice_id}/items", response_model=InvoiceOut)
def replace_items(
    invoice_id: uuid.UUID, payload: list[InvoiceItemIn], session: SessionDep, user: CurrentUser
) -> InvoiceOut:
    invoice = repository.get_invoice(session, invoice_id, user.id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    invoice.items.clear()  # delete-orphan removes the old rows
    net = Decimal(0)
    for i, item in enumerate(payload):
        # flat/Pauschal lines send an explicit amount; hourly lines compute hours × rate
        amount = _q(item.amount if item.amount is not None else item.hours * item.rate)
        net += amount
        invoice.items.append(InvoiceItem(
            description=flatten(item.description), hours=item.hours, rate=item.rate,
            amount=amount, position=i,
        ))
    invoice.total = _gross(net, invoice.vat_rate)  # gross = net + VAT (0 for Kleinunternehmer)
    session.commit()
    return _invoice_out(session, user.id, invoice)


@router.get("/{invoice_id}/pdf")
def invoice_pdf(invoice_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    invoice = repository.get_invoice(session, invoice_id, user.id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    client = repository.get_client(session, invoice.client_id, user.id)
    profile = repository.get_business_profile(session, user.id)
    project = (
        repository.get_project(session, invoice.project_id, user.id)
        if invoice.project_id is not None else None
    )
    pdf = render_invoice(profile, client, invoice, project=project)

    fname = f"Rechnung{invoice.number}_{(profile.name or 'invoice')}.pdf".replace(" ", "_")
    ascii_name = fname.encode("ascii", "ignore").decode("ascii").strip() or "invoice.pdf"
    disposition = f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(fname)}"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": disposition})


@router.post("/{invoice_id}/email")
def email_invoice(
    invoice_id: uuid.UUID, payload: InvoiceEmail, session: SessionDep, user: CurrentUser
) -> dict:
    settings = get_settings()
    if not settings.smtp_configured:
        raise HTTPException(status_code=400, detail="email sending is not configured on the server")
    invoice = repository.get_invoice(session, invoice_id, user.id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    if not payload.to.strip():
        raise HTTPException(status_code=400, detail="a recipient email is required")
    client = repository.get_client(session, invoice.client_id, user.id)
    profile = repository.get_business_profile(session, user.id)
    project = (
        repository.get_project(session, invoice.project_id, user.id)
        if invoice.project_id is not None else None
    )
    pdf = render_invoice(profile, client, invoice, project=project)
    from_addr = payload.from_ or profile.email or settings.smtp_from or settings.smtp_user
    try:
        send_invoice_email(
            settings, to=payload.to.strip(), subject=payload.subject, body=payload.body,
            pdf=pdf, filename=f"Rechnung{invoice.number}.pdf", from_addr=from_addr,
        )
    except Exception as exc:  # noqa: BLE001 - surface the SMTP error to the user
        raise HTTPException(status_code=502, detail=f"failed to send email: {exc}")
    changed = False
    if payload.reminder:  # a Zahlungserinnerung/Mahnung → bump the Mahnstufe
        invoice.reminder_level = (invoice.reminder_level or 0) + 1
        invoice.last_reminder_at = datetime.now(timezone.utc)
        changed = True
    if invoice.status not in ("paid", "sent"):  # first send marks it sent (don't downgrade paid)
        invoice.status = "sent"
        changed = True
    if changed:
        session.commit()
    return {"ok": True, "status": invoice.status, "reminder_level": invoice.reminder_level}


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    if not repository.delete_invoice(session, invoice_id, user.id):
        raise HTTPException(status_code=404, detail="invoice not found")
    session.commit()
    return Response(status_code=204)
