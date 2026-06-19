"""Net-worth aggregator (§4.5).

Sums the latest balance of every account across all registered connectors into one
net-worth figure, and can snapshot it over time for the trend chart.

FX is out of scope for Phase 0: the headline `total` is the sum of balances already in the
configured base currency. Other currencies are surfaced in `by_currency` rather than being
silently converted/mis-summed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.connectors.registry import get_connectors
from backend.persistence import repository
from backend.persistence.models import NetWorthSnapshot


@dataclass
class BreakdownEntry:
    account_id: str
    name: str
    connector: str
    currency: str
    amount: Decimal


@dataclass
class NetWorth:
    base_currency: str
    total: Decimal
    by_currency: dict[str, Decimal] = field(default_factory=dict)
    breakdown: list[BreakdownEntry] = field(default_factory=list)


def compute_net_worth(session: Session) -> NetWorth:
    settings = get_settings()
    base = settings.app_base_currency

    by_currency: dict[str, Decimal] = {}
    breakdown: list[BreakdownEntry] = []

    for connector in get_connectors(session):
        for account in connector.list_accounts():
            balance = connector.get_balance(str(account.id))
            currency = balance.currency
            amount = balance.amount
            by_currency[currency] = by_currency.get(currency, Decimal("0")) + amount
            breakdown.append(
                BreakdownEntry(
                    account_id=str(account.id),
                    name=account.name,
                    connector=account.connector,
                    currency=currency,
                    amount=amount,
                )
            )

    total = by_currency.get(base, Decimal("0"))
    return NetWorth(
        base_currency=base,
        total=total,
        by_currency=by_currency,
        breakdown=breakdown,
    )


def take_snapshot(session: Session) -> NetWorthSnapshot:
    """Compute current net worth and persist a snapshot row (commits)."""
    net_worth = compute_net_worth(session)
    breakdown_json = {
        "base_currency": net_worth.base_currency,
        "by_currency": {k: str(v) for k, v in net_worth.by_currency.items()},
        "accounts": [
            {
                "account_id": entry.account_id,
                "name": entry.name,
                "connector": entry.connector,
                "currency": entry.currency,
                "amount": str(entry.amount),
            }
            for entry in net_worth.breakdown
        ],
    }
    snapshot = repository.save_snapshot(
        session, total=net_worth.total, breakdown=breakdown_json
    )
    session.commit()
    return snapshot
