"""Generate draft invoices from recurring (retainer) templates — flat fee or tracked time.

Mirrors the cashflow materializer: catches up missed periods and advances next_run, so it's
safe to run on every Invoices-tab load. Generated invoices are plain drafts to review + send.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from backend.cashflow.service import _advance
from backend.invoicing.grouping import build_items
from backend.invoicing.i18n import texts
from backend.invoicing.text import flatten
from backend.persistence import repository
from backend.persistence.models import Cadence, InvoiceItem


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _gross(net: Decimal, vat_rate: Decimal) -> Decimal:
    return _q(net * (Decimal(1) + vat_rate / Decimal(100)))


def _cadence(value: str) -> Cadence:
    try:
        return Cadence(value)
    except ValueError:
        return Cadence.monthly


def _build_items(session, user_id, client, rec):
    """(items, net, time_entries_to_bill) for one generated invoice, or (None, 0, []) to skip."""
    if rec.mode == "time":
        entries = repository.list_time_entries(
            session, user_id, client_id=client.id, project_id=rec.project_id, unbilled=True)
        if not entries:
            return None, Decimal(0), []  # nothing to bill this period → skip
        rate_cache: dict = {}
        name_cache: dict = {}

        def project_name(pid):
            if pid is None:
                return None
            if pid not in name_cache:
                proj = repository.get_project(session, pid, user_id)
                name_cache[pid] = proj.name if proj else None
                rate_cache[pid] = (
                    proj.hourly_rate if proj and proj.hourly_rate is not None else client.hourly_rate)
            return name_cache[pid]

        def rate_for(e):
            if e.project_id is None:
                return client.hourly_rate
            project_name(e.project_id)  # populates rate_cache
            return rate_cache[e.project_id]

        lang = rec.language if rec.language in ("de", "en") else "de"
        # retainers bill one line per entry (group_by="none"); shares the create-invoice builder
        items, net = build_items(entries, rate_for, project_name, group_by="none", lang=lang)
        return items, net, entries

    # flat fee
    amount = _q(rec.amount)
    desc = flatten(rec.description) or "Pauschale"
    return [InvoiceItem(description=desc, hours=Decimal(0), rate=Decimal(0), amount=amount, position=0)], amount, []


def materialize_recurring_invoices(session, user_id, as_of=None) -> int:
    today = (as_of or datetime.now(timezone.utc)).date()
    profile = repository.get_business_profile(session, user_id)
    generated = 0
    for rec in repository.list_recurring_invoices(session, user_id, active_only=True):
        client = repository.get_client(session, rec.client_id, user_id)
        if client is None:
            continue
        cad = _cadence(rec.cadence)
        due = rec.next_run
        guard = 0
        while due <= today and guard < 60:
            guard += 1
            items, net, entries = _build_items(session, user_id, client, rec)
            if items is not None:
                language = rec.language if rec.language in ("de", "en") else "de"
                vat_rate = Decimal(0) if profile.is_kleinunternehmer else Decimal("19")
                number = str(profile.next_invoice_number)
                profile.next_invoice_number += 1
                invoice = repository.create_invoice(
                    session, user_id=user_id, client_id=client.id, project_id=rec.project_id,
                    number=number, issue_date=due,
                    due_date=due + timedelta(days=profile.payment_terms_days),
                    place=(profile.city or ""), language=language,
                    intro_text=(profile.intro_text or texts(language)["intro_default"]),
                    status="draft", vat_rate=vat_rate, total=_gross(net, vat_rate),
                )
                invoice.items = items
                for e in entries:
                    e.invoice_id = invoice.id
                generated += 1
            due = _advance(due, cad)
        rec.next_run = due
    session.flush()
    return generated
