"""Populate a demo account with rich, multi-year data exercising every card/feature.

Run on the server:  /opt/finance-tracker/.venv/bin/python -m backend.seed_demo
Wipes the demo user's existing data first, so it's safe to re-run.
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select

from backend.persistence.database import SessionLocal
from backend.persistence.models import (
    Account,
    Allocation,
    Attachment,
    Balance,
    Budget,
    Cadence,
    CashflowDirection,
    CashflowItem,
    Category,
    CategoryKind,
    Debt,
    EmergencyFund,
    NetWorthSnapshot,
    Recurring,
    Rule,
    Transaction,
    User,
)

DEMO_EMAIL = sys.argv[1] if len(sys.argv) > 1 else "akipphard@yahoo.de"
D = Decimal
TODAY = datetime.now(timezone.utc).date()


def _dt(d: date) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=timezone.utc)


def _add_month(y: int, m: int, n: int) -> tuple[int, int]:
    idx = y * 12 + (m - 1) + n
    return idx // 12, idx % 12 + 1


def wipe(session, uid):
    acct_ids = select(Account.id).where(Account.user_id == uid)
    session.execute(delete(Attachment).where(Attachment.user_id == uid))
    session.execute(delete(Transaction).where(Transaction.user_id == uid))
    session.execute(delete(Balance).where(Balance.account_id.in_(acct_ids)))
    session.execute(delete(CashflowItem).where(CashflowItem.user_id == uid))
    session.execute(delete(Recurring).where(Recurring.user_id == uid))
    session.execute(delete(Budget).where(Budget.user_id == uid))
    session.execute(delete(Debt).where(Debt.user_id == uid))
    session.execute(delete(Allocation).where(Allocation.user_id == uid))
    session.execute(delete(EmergencyFund).where(EmergencyFund.user_id == uid))
    session.execute(delete(NetWorthSnapshot).where(NetWorthSnapshot.user_id == uid))
    session.execute(delete(Rule).where(Rule.user_id == uid))
    session.execute(delete(Budget).where(Budget.user_id == uid))
    session.execute(delete(Category).where(Category.user_id == uid))
    session.execute(delete(Account).where(Account.user_id == uid))
    session.flush()


def run() -> dict:
    with SessionLocal() as session:
        user = session.execute(select(User).where(User.email == DEMO_EMAIL)).scalars().first()
        if user is None:
            raise SystemExit(f"user {DEMO_EMAIL} not found — register it first")
        uid = user.id
        wipe(session, uid)

        ledger: list[tuple[datetime, Decimal, bool]] = []  # (ts, amount, excluded) for snapshots

        def txn(acc, d: date, amount, payee, *, cat=None, tags=None, excluded=False,
                is_transfer=False, series=None, desc=None):
            t = Transaction(
                user_id=uid, account_id=acc.id, ts=_dt(d), amount=D(str(amount)), currency="EUR",
                raw_payee=payee, description=desc, category_id=cat, tags=list(tags or []),
                excluded=excluded, is_transfer=is_transfer, series_id=series, hash=uuid.uuid4().hex,
            )
            session.add(t)
            ledger.append((t.ts, t.amount, excluded))
            return t

        def transfer(src, dst, amount, d: date, tags=None):
            txn(src, d, -D(str(amount)), f"Transfer to {dst.name}", tags=tags, is_transfer=True)
            txn(dst, d, D(str(amount)), f"Transfer from {src.name}", tags=tags, is_transfer=True)

        # --- accounts (with expected returns for the forecast) ---
        def account(name, type_, ret=0):
            a = Account(user_id=uid, connector="manual", type=type_, name=name, currency="EUR",
                        expected_return=D(str(ret)))
            session.add(a)
            return a

        giro = account("Girokonto", "checking", 0)
        savings = account("Tagesgeld", "savings", 2.5)
        broker = account("Trade Republic", "brokerage", 7)
        crypto = account("Bitpanda", "brokerage", 18)
        cash = account("Bargeld", "cash", 0)
        session.flush()

        # --- categories ---
        cat_defs = [
            ("Salary", "income", True), ("Freelance income", "income", False),
            ("Other Income", "income", False),
            ("Rent", "expense", True), ("Insurance", "expense", True), ("Internet", "expense", True),
            ("Mobile", "expense", True), ("Subscriptions", "expense", True),
            ("Groceries", "expense", False), ("Dining", "expense", False),
            ("Transport", "expense", False), ("Shopping", "expense", False),
            ("Health", "expense", False), ("Leisure", "expense", False),
            ("Travel", "expense", False), ("Software", "expense", False), ("Other", "expense", False),
        ]
        cats = {}
        for name, kind, fixed in cat_defs:
            c = Category(user_id=uid, name=name, kind=CategoryKind(kind), is_fixed=fixed)
            session.add(c)
            cats[name] = c
        session.flush()

        # --- opening balances + initial allocation across accounts ---
        start_y, start_m = _add_month(TODAY.year, TODAY.month, -29)  # ~30 months back
        first = date(start_y, start_m, 1)
        txn(giro, first, 18000, "Opening balance", desc="Starting balance")
        txn(cash, first, 250, "Opening balance")
        transfer(giro, savings, 4000, first)
        transfer(giro, broker, 6000, first)
        transfer(giro, crypto, 1500, first)

        # --- monthly history ---
        retainer_series = uuid.uuid4()
        y, m = start_y, start_m
        while (y, m) <= (TODAY.year, TODAY.month):
            d1 = date(y, m, 1)
            mi = y * 12 + m  # month index for deterministic variation
            txn(giro, d1, 4500, "Gehalt Acme GmbH", cat=cats["Salary"].id)
            txn(giro, d1, -1200, "Miete", cat=cats["Rent"].id)
            txn(giro, date(y, m, 3), -44.95, "Telekom Internet", cat=cats["Internet"].id)
            txn(giro, date(y, m, 5), -29.99, "Vodafone Mobil", cat=cats["Mobile"].id)
            txn(giro, date(y, m, 10), -149, "Allianz Versicherung", cat=cats["Insurance"].id)
            txn(giro, date(y, m, 6), -15.99, "Netflix", cat=cats["Subscriptions"].id)
            txn(giro, date(y, m, 6), -11.99, "Spotify", cat=cats["Subscriptions"].id)
            txn(giro, date(y, m, 2), -29.90, "FitX Gym", cat=cats["Leisure"].id)
            txn(giro, d1, -59, "BVG Monatsticket", cat=cats["Transport"].id)
            for day in (4, 11, 18, 25):
                txn(giro, date(y, m, day), -(60 + (mi % 5) * 7), "REWE", cat=cats["Groceries"].id)
            for day in (8, 16, 23):
                txn(giro, date(y, m, day), -(28 + (mi % 4) * 6), "Restaurant", cat=cats["Dining"].id)
            txn(giro, date(y, m, 14), -(40 + (mi % 6) * 15), "Amazon", cat=cats["Shopping"].id)
            # savings + investing
            transfer(giro, savings, 500, date(y, m, 2))
            transfer(giro, broker, 400, date(y, m, 2), tags=["sparplan"])
            if mi % 3 == 0:
                transfer(giro, crypto, 150, date(y, m, 2), tags=["crypto"])
            # freelancing income (real, on-balance, tagged) every other month
            if mi % 2 == 0:
                txn(giro, date(y, m, 20), 700 + (mi % 4) * 120, "GreatIdea UAB",
                    cat=cats["Freelance income"].id, tags=["freelance"], desc="Invoice")
            # off-balance freelancing software (tax record)
            txn(giro, date(y, m, 7), -19.99, "Adobe Creative Cloud",
                cat=cats["Software"].id, tags=["freelance"], excluded=True, desc="Tax record")
            # linked backfill-style retainer series for 2025 H2
            if (y == TODAY.year - 1) and 7 <= m <= 12:
                txn(giro, date(y, m, 28), 1200, "Retainer Studio Nord",
                    cat=cats["Freelance income"].id, tags=["freelance"], series=retainer_series)
            y, m = _add_month(y, m, 1)

        # --- recurring cashflow items (drive Distribute leftover + Scheduled) ---
        def cf(direction, name, amount, acc, next_due, cat=None):
            session.add(CashflowItem(
                user_id=uid, direction=CashflowDirection(direction), name=name, amount=D(str(amount)),
                cadence=Cadence.monthly, currency="EUR", account_id=acc.id, next_due=next_due,
                category_id=(cat.id if cat else None)))

        nxt = date(*_add_month(TODAY.year, TODAY.month, 1), 1)  # 1st of next month
        soon = TODAY + timedelta(days=3)  # to show a "due soon" badge
        cf("inflow", "Gehalt Acme GmbH", 4500, giro, nxt, cats["Salary"])
        cf("outflow", "Miete", 1200, giro, nxt, cats["Rent"])
        cf("outflow", "Allianz Versicherung", 149, giro, nxt, cats["Insurance"])
        cf("outflow", "Telekom Internet", 44.95, giro, nxt, cats["Internet"])
        cf("outflow", "Vodafone Mobil", 29.99, giro, nxt, cats["Mobile"])
        cf("outflow", "Netflix", 15.99, giro, soon, cats["Subscriptions"])
        cf("outflow", "Spotify", 11.99, giro, nxt, cats["Subscriptions"])
        cf("outflow", "FitX Gym", 29.90, giro, nxt, cats["Leisure"])

        # --- budgets (one intentionally tight to trigger an over-budget alert) ---
        for name, limit in [("Groceries", 320), ("Dining", 90), ("Subscriptions", 50),
                            ("Shopping", 150), ("Transport", 70)]:
            session.add(Budget(user_id=uid, category_id=cats[name].id, monthly_limit=D(str(limit))))

        # --- debts (unpaid incl. one overdue → alert; plus paid history) ---
        session.add_all([
            Debt(user_id=uid, name="Strafzettel", amount=D("60"), due_date=TODAY - timedelta(days=6), paid=False),
            Debt(user_id=uid, name="Neue Couch", amount=D("850"), due_date=TODAY + timedelta(days=25), paid=False),
            Debt(user_id=uid, name="Autoreparatur", amount=D("900"), paid=True),
            Debt(user_id=uid, name="Laptop Ratenkauf", amount=D("1200"), paid=True),
        ])

        # --- emergency fund (target 3x fixed, ~58% funded) ---
        session.add(EmergencyFund(user_id=uid, target_months=3, target_amount=None,
                                  current_amount=D("2600")))

        # --- allocation buckets (+ Debt and Emergency fund off-the-top markers) ---
        for name, pct in [("Debt", 1), ("Emergency fund", 1), ("Savings", 40),
                          ("Invest", 35), ("Fun", 15)]:
            session.add(Allocation(user_id=uid, name=name, percent=D(str(pct))))

        # --- net-worth snapshots: monthly trend computed from the ledger ---
        sy, sm = _add_month(start_y, start_m, 6)
        while (sy, sm) <= (TODAY.year, TODAY.month):
            ny, nm = _add_month(sy, sm, 1)
            cutoff = _dt(date(ny, nm, 1))
            total = sum((amt for ts, amt, exc in ledger if not exc and ts < cutoff), D(0))
            session.add(NetWorthSnapshot(user_id=uid, ts=_dt(date(sy, sm, 28)),
                                         total=total, breakdown_json={}))
            sy, sm = ny, nm

        session.commit()
        return {"transactions": len(ledger), "accounts": 5, "categories": len(cats)}


if __name__ == "__main__":
    print(run())
