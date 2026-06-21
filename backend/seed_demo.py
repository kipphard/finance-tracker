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
    BusinessProfile,
    Cadence,
    CashflowDirection,
    CashflowItem,
    Category,
    CategoryKind,
    Client,
    Debt,
    EmergencyFund,
    Invoice,
    InvoiceItem,
    NetWorthSnapshot,
    Project,
    Recurring,
    Rule,
    TimeEntry,
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
    inv_ids = select(Invoice.id).where(Invoice.user_id == uid)
    session.execute(delete(InvoiceItem).where(InvoiceItem.invoice_id.in_(inv_ids)))
    session.execute(delete(TimeEntry).where(TimeEntry.user_id == uid))
    session.execute(delete(Invoice).where(Invoice.user_id == uid))
    session.execute(delete(Project).where(Project.user_id == uid))
    session.execute(delete(Client).where(Client.user_id == uid))
    session.execute(delete(BusinessProfile).where(BusinessProfile.user_id == uid))
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

        # === Freelance: business profile, clients, tracked time, one invoice ===
        def _q(v: Decimal) -> Decimal:
            return v.quantize(D("0.01"))

        now = datetime.now(timezone.utc)

        session.add(BusinessProfile(
            user_id=uid,
            name="André Kipphard",
            company_name="Kipphard Studio",
            phone="+49 151 23456789",
            email="hallo@kipphard.de",
            address="Musterstraße 12",
            postal_code="50667",
            city="Köln",
            iban="DE89 3704 0044 0532 0130 00",
            bic="COBADEFFXXX",
            tax_number="GA 123/4567/8901",
            is_kleinunternehmer=True,
            vat_note="",      # blank → PDF uses the language-appropriate §19 note
            intro_text="",    # blank → PDF uses the language-appropriate greeting
            default_language="de",
            default_hourly_rate=D("45"),
            next_invoice_number=100002,
        ))

        brandwerk = Client(user_id=uid, name="Studio Brandwerk GmbH",
                           email="rechnung@brandwerk.de",
                           address="Studio Brandwerk GmbH\nDesignallee 4\n40213 Düsseldorf",
                           hourly_rate=D("45"), budget_hours=D("20"),
                           notes="Website relaunch + ongoing care.", archived=False)
        helios = Client(user_id=uid, name="Helios Apotheke",
                        email="info@helios-apotheke.de",
                        address="Helios Apotheke\nMarktplatz 9\n50321 Brühl",
                        hourly_rate=D("50"), budget_hours=None,
                        notes="Monthly website maintenance.", archived=False)
        mondia = Client(user_id=uid, name="Café Mondia",
                        email="hallo@cafe-mondia.de",
                        address="Café Mondia\nLindenstr. 2\n50674 Köln",
                        hourly_rate=D("40"), budget_hours=D("8"),
                        notes="Menu + social media graphics.", archived=False)
        session.add_all([brandwerk, helios, mondia])
        session.flush()

        # Two projects under the agency: one inherits the client rate, one overrides it.
        relaunch = Project(user_id=uid, client_id=brandwerk.id, name="Website Relaunch",
                           hourly_rate=None, budget_hours=D("12"),
                           notes="One-off relaunch project.")
        care = Project(user_id=uid, client_id=brandwerk.id, name="Laufende Betreuung",
                       hourly_rate=D("55"), budget_hours=None,
                       notes="Ongoing care, billed at a higher rate.")
        session.add_all([relaunch, care])
        session.flush()

        def tentry(client, days_ago, hour, minutes, desc, invoice=None, project=None):
            started = (now - timedelta(days=days_ago)).replace(
                hour=hour, minute=0, second=0, microsecond=0)
            te = TimeEntry(
                user_id=uid, client_id=client.id,
                project_id=project.id if project else None, started_at=started,
                ended_at=started + timedelta(minutes=minutes), minutes=minutes,
                description=desc, invoice_id=invoice.id if invoice else None,
            )
            session.add(te)
            return te

        # One issued + paid invoice for Brandwerk's Website Relaunch project (German).
        invoice = Invoice(
            user_id=uid, client_id=brandwerk.id, project_id=relaunch.id, number="100001",
            issue_date=(now - timedelta(days=18)).date(), place="Köln", language="de",
            intro_text=(
                "Sehr geehrte Damen und Herren,\n\nvielen Dank für die gute Zusammenarbeit. "
                "Hiermit stelle ich Ihnen die folgenden Leistungen in Rechnung:"
            ),
            status="paid", vat_rate=D("0"), total=D("0"),
        )
        session.add(invoice)
        session.flush()

        billed = [
            tentry(brandwerk, 26, 9, 180, "Landing page redesign – hero + navigation", invoice, relaunch),
            tentry(brandwerk, 25, 10, 120, "Responsive layout fixes", invoice, relaunch),
            tentry(brandwerk, 22, 14, 90, "Client feedback round 1", invoice, relaunch),
        ]
        items: list[InvoiceItem] = []
        total = D("0")
        for i, te in enumerate(billed):
            hrs = (D(te.minutes) / D(60)).quantize(D("0.01"))
            amount = _q(hrs * brandwerk.hourly_rate)
            total += amount
            items.append(InvoiceItem(description=te.description, hours=hrs,
                                     rate=brandwerk.hourly_rate, amount=amount, position=i))
        invoice.items = items
        invoice.total = _q(total)

        # Unbilled time: some on each project (shows per-project rate + budget), some plain.
        tentry(brandwerk, 5, 9, 150, "CMS integration & content migration", project=relaunch)
        tentry(brandwerk, 3, 11, 75, "Bugfixing checkout flow", project=relaunch)
        tentry(brandwerk, 1, 13, 210, "Monatliches Care-Paket: Updates & Backups", project=care)

        tentry(helios, 6, 10, 120, "Monatliche Webseiten-Pflege")
        tentry(helios, 2, 15, 60, "Öffnungszeiten & Notdienst aktualisiert")

        tentry(mondia, 8, 9, 240, "Speisekarte für Web & Print gestaltet")
        tentry(mondia, 4, 14, 180, "Instagram-Grafiken (5 Posts)")
        tentry(mondia, 4, 17, 90, "Logo-Varianten")

        session.commit()
        return {
            "transactions": len(ledger), "accounts": 5, "categories": len(cats),
            "clients": 3, "projects": 2, "time_entries": 11, "invoices": 1,
        }


if __name__ == "__main__":
    print(run())
