"""Build the periodic notification digest (plain-text email) for a user."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backend.insights.service import build_forecast
from backend.networth.aggregator import compute_net_worth
from backend.persistence import repository

ILLIQUID_TYPES = {"brokerage", "investment", "property", "crypto", "retirement", "pension"}


def _eur(v: Decimal) -> str:
    return f"{Decimal(v):.2f} EUR"


def build_digest(session, user, profile) -> tuple[str, str]:
    """Return (subject, plain-text body) for the user's digest, honouring the section toggles."""
    uid = user.id
    today = datetime.now(timezone.utc).date()
    sections: list[str] = []

    if profile.digest_invoices:
        unpaid = unpaid_sum = overdue = Decimal(0)
        overdue_sum = Decimal(0)
        for inv in repository.list_invoices(session, uid):
            if inv.status == "paid":
                continue
            unpaid += 1
            unpaid_sum += Decimal(inv.total)
            if inv.due_date and inv.due_date < today:
                overdue += 1
                overdue_sum += Decimal(inv.total)
        sections.append(
            "Rechnungen:\n"
            f"  - Offen: {int(unpaid)} ({_eur(unpaid_sum)})\n"
            f"  - Ueberfaellig: {int(overdue)} ({_eur(overdue_sum)})"
        )

    if profile.digest_time:
        unbilled_h = Decimal(0)
        unbilled_eur = Decimal(0)
        for c in repository.list_clients(session, uid):
            _, unbilled_min = repository.client_minutes(session, uid, c.id)
            h = Decimal(unbilled_min) / Decimal(60)
            unbilled_h += h
            unbilled_eur += h * Decimal(c.hourly_rate)
        sections.append(
            "Zeit:\n"
            f"  - Unfakturiert: {unbilled_h:.2f} h (~{_eur(unbilled_eur)})"
        )

    if profile.digest_finance:
        nw = compute_net_worth(session, uid)
        fc = build_forecast(session, uid, months=1)
        liquid = sum(
            (repository.account_balance(session, a) for a in repository.list_accounts(session, uid)
             if (a.type or "").lower() not in ILLIQUID_TYPES),
            Decimal(0),
        )
        net = Decimal(fc.monthly_net)
        runway = (
            f"{liquid / -net:.1f} Monate" if (net < 0 and liquid > 0) else "unbegrenzt (positiv)"
        )
        sections.append(
            "Finanzen:\n"
            f"  - Nettovermoegen: {_eur(nw.total)}\n"
            f"  - Monatlicher Saldo: {_eur(net)}\n"
            f"  - Runway: {runway}"
        )

    subject = "Finance Tracker — deine Uebersicht"
    body = "Hallo,\n\nhier ist deine aktuelle Uebersicht:\n\n" + "\n\n".join(sections) + \
        "\n\nViele Gruesse\nFinance Tracker"
    return subject, body
