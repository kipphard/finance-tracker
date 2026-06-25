"""Rate advisor + what-if baseline bundle.

One read-only snapshot the frontend uses to (a) suggest an hourly rate that nets a desired
take-home after costs and tax, and (b) run instant "what-if" scenarios (raise rates, lose a
client, a one-off purchase) against cash runway, profit and tax — all client-side, so no
round-trip per slider tick.

Everything here reuses existing engines: the paycheck bundle (trailing net/income, fixed costs,
tax set-aside, liquid), the §32a EÜR (profit + tax), and the tariff (for a marginal rate on the
next euro of freelance profit). Deterministic; a planning aid, not tax advice.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from backend.insights.paycheck import compute_paycheck
from backend.persistence import repository
from backend.tax.eur import compute_eur
from backend.tax.tariff import income_tax

_TRAILING_DAYS = 365
_MONTHS = Decimal(12)
_MARGINAL_BUMP = Decimal(1000)  # probe the tariff this far above current zvE for a marginal rate


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


@dataclass
class AdvisorClient:
    id: str
    name: str
    monthly_income: Decimal  # trailing avg of invoices issued in the last 12 months / 12


@dataclass
class AdvisorResult:
    currency: str
    liquid: Decimal
    monthly_net: Decimal           # trailing avg monthly net (drives runway)
    monthly_income: Decimal        # trailing avg monthly income
    monthly_fixed: Decimal         # modeled fixed costs / month
    tax_setaside: Decimal          # recommended monthly tax reserve
    sustainable_pay: Decimal       # default "desired take-home" for the advisor
    default_hourly_rate: Decimal   # your current rate (business profile)
    billable_hours_month: Decimal  # trailing avg billable hours / month
    marginal_tax_rate: Decimal     # 0..1 on the next euro of freelance profit
    annual_profit: Decimal         # current-year EÜR profit
    annual_tax: Decimal            # current-year §32a estimate on that profit
    clients: list[AdvisorClient] = field(default_factory=list)


def _marginal_tax_rate(other_income: Decimal, profit: Decimal, tariff_year: int) -> Decimal:
    """Effective tax on the next slice of freelance profit, stacked on the user's other income."""
    base = other_income + profit
    if base < 0:
        base = Decimal(0)
    delta = income_tax(base + _MARGINAL_BUMP, tariff_year) - income_tax(base, tariff_year)
    rate = delta / _MARGINAL_BUMP
    return min(max(rate, Decimal(0)), Decimal(1))


def compute_advisor(
    session: Session, user_id: uuid.UUID, now: datetime | None = None
) -> AdvisorResult:
    now = now or datetime.now(timezone.utc)
    pay = compute_paycheck(session, user_id, now)
    eur = compute_eur(session, user_id, now.year)
    profile = repository.get_business_profile(session, user_id)

    # Trailing billable hours / month (all clients).
    start = now - timedelta(days=_TRAILING_DAYS)
    minutes = sum(
        e.minutes for e in repository.list_time_entries(session, user_id, start=start, end=now)
    )
    billable_hours_month = _q(Decimal(minutes) / Decimal(60) / _MONTHS)

    # Trailing monthly income per client, from invoices issued in the window.
    names = {c.id: c.name for c in repository.list_clients(session, user_id)}
    per_client: dict[uuid.UUID, Decimal] = {}
    for inv in repository.list_invoices(session, user_id):
        if inv.issue_date and inv.issue_date >= start.date():
            per_client[inv.client_id] = per_client.get(inv.client_id, Decimal(0)) + Decimal(inv.total)
    clients = [
        AdvisorClient(id=str(cid), name=names.get(cid, "—"), monthly_income=_q(total / _MONTHS))
        for cid, total in per_client.items()
    ]
    clients.sort(key=lambda c: c.monthly_income, reverse=True)

    return AdvisorResult(
        currency=pay.currency,
        liquid=_q(pay.liquid),
        monthly_net=_q(pay.trailing_net),
        monthly_income=_q(pay.trailing_income),
        monthly_fixed=_q(pay.monthly_fixed),
        tax_setaside=_q(pay.tax_setaside),
        sustainable_pay=_q(pay.sustainable_pay),
        default_hourly_rate=_q(Decimal(profile.default_hourly_rate)),
        billable_hours_month=billable_hours_month,
        marginal_tax_rate=_q4(_marginal_tax_rate(
            Decimal(eur.other_income), Decimal(eur.profit), eur.tariff_year
        )),
        annual_profit=_q(Decimal(eur.profit)),
        annual_tax=_q(Decimal(eur.tax_estimate)),
        clients=clients,
    )
