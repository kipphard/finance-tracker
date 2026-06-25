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

from backend.invoicing.grouping import build_items
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
    PlannedPurchase,
    Project,
    Reconciliation,
    Recurring,
    RecurringInvoice,
    Rule,
    TaxProfile,
    TaxReserve,
    TaxYearInput,
    TimeEntry,
    Transaction,
    Trip,
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
    session.execute(delete(Trip).where(Trip.user_id == uid))
    session.execute(delete(TimeEntry).where(TimeEntry.user_id == uid))
    session.execute(delete(Invoice).where(Invoice.user_id == uid))
    session.execute(delete(RecurringInvoice).where(RecurringInvoice.user_id == uid))
    session.execute(delete(Project).where(Project.user_id == uid))
    session.execute(delete(Client).where(Client.user_id == uid))
    session.execute(delete(BusinessProfile).where(BusinessProfile.user_id == uid))
    session.execute(delete(Attachment).where(Attachment.user_id == uid))
    session.execute(delete(Reconciliation).where(Reconciliation.user_id == uid))
    session.execute(delete(Transaction).where(Transaction.user_id == uid))
    session.execute(delete(Balance).where(Balance.account_id.in_(acct_ids)))
    session.execute(delete(CashflowItem).where(CashflowItem.user_id == uid))
    session.execute(delete(Recurring).where(Recurring.user_id == uid))
    session.execute(delete(Budget).where(Budget.user_id == uid))
    session.execute(delete(Debt).where(Debt.user_id == uid))
    session.execute(delete(Allocation).where(Allocation.user_id == uid))
    session.execute(delete(PlannedPurchase).where(PlannedPurchase.user_id == uid))
    session.execute(delete(EmergencyFund).where(EmergencyFund.user_id == uid))
    session.execute(delete(NetWorthSnapshot).where(NetWorthSnapshot.user_id == uid))
    session.execute(delete(Rule).where(Rule.user_id == uid))
    session.execute(delete(TaxYearInput).where(TaxYearInput.user_id == uid))
    session.execute(delete(TaxProfile).where(TaxProfile.user_id == uid))
    session.execute(delete(Budget).where(Budget.user_id == uid))
    session.execute(delete(Category).where(Category.user_id == uid))
    session.execute(delete(Account).where(Account.user_id == uid))
    session.flush()


def seed_demo_for_user(session, user_id) -> dict:
    """Populate a given user with the full demo dataset. No wipe, no fixed email — the caller
    commits. Used by both the CLI and the public /api/auth/demo sandbox endpoint."""
    uid = user_id
    TODAY = datetime.now(timezone.utc).date()  # fresh each call (server may run for days)

    ledger: list[tuple[datetime, Decimal, bool]] = []  # (ts, amount, excluded) for snapshots

    def txn(acc, d: date, amount, payee, *, cat=None, tags=None, excluded=False,
            is_transfer=False, series=None, desc=None, deductible_pct=None, is_business=False):
        t = Transaction(
            user_id=uid, account_id=acc.id, ts=_dt(d), amount=D(str(amount)), currency="EUR",
            raw_payee=payee, description=desc, category_id=cat, tags=list(tags or []),
            excluded=excluded, is_transfer=is_transfer, series_id=series, hash=uuid.uuid4().hex,
            deductible_pct=None if deductible_pct is None else D(str(deductible_pct)),
            is_business=is_business,
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
    steuer = account("Steuerrücklage", "savings", 1.5)
    broker = account("Trade Republic", "brokerage", 7)
    crypto = account("Bitpanda", "brokerage", 18)
    cash = account("Bargeld", "cash", 0)
    session.flush()

    # --- categories ---
    cat_defs = [
        ("Salary", "income", True), ("Business income", "income", False),
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
                cat=cats["Business income"].id, is_business=True, desc="Invoice")
        # off-balance freelancing software (tax record)
        txn(giro, date(y, m, 7), -19.99, "Adobe Creative Cloud",
            cat=cats["Software"].id, is_business=True, excluded=True, desc="Tax record")
        # linked backfill-style retainer series for 2025 H2
        if (y == TODAY.year - 1) and 7 <= m <= 12:
            txn(giro, date(y, m, 28), 1200, "Retainer Studio Nord",
                cat=cats["Business income"].id, is_business=True, series=retainer_series)
        y, m = _add_month(y, m, 1)

    # --- bigger one-off freelance expenses (Arbeitsmittel) for the Taxes/EÜR view ---
    for fy in (TODAY.year - 1, TODAY.year):
        txn(giro, date(fy, 3, 12), -1299, "MacBook Air (Arbeitsmittel)",
            cat=cats["Shopping"].id, is_business=True, desc="Tax record")
        txn(giro, date(fy, 5, 8), -249, "Online-Kurs (Fortbildung)",
            cat=cats["Other"].id, is_business=True, desc="Tax record")
        # Partly-business purchase: per-transaction 70% override (no category rate needed).
        txn(giro, date(fy, 6, 18), -880, "Bürostuhl (anteilig betrieblich)",
            cat=cats["Shopping"].id, deductible_pct=70, desc="70% betrieblich genutzt")

    # --- bigger current-year freelance projects so the EÜR + Steuerrücklage show a real
    #     profit this year (only book those dated on/before today) ---
    for mm, amt, label in [(2, 3200, "Projekt Website Relaunch Brandwerk"),
                           (4, 2800, "Projekt Branding Helios")]:
        d = date(TODAY.year, mm, 15)
        if d <= TODAY:
            txn(giro, d, amt, label, cat=cats["Business income"].id,
                is_business=True, desc="Invoice")

    # --- Steuerrücklage: money set aside into the dedicated, earmarked reserve account ---
    for mm, amt in [(2, 700), (4, 700)]:
        d = date(TODAY.year, mm, 25)
        if d <= TODAY:
            transfer(giro, steuer, amt, d)

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

    # --- tax reserve (Steuerrücklage): set-aside lives in the dedicated reserve account,
    #     which is earmarked out of the cash-runway liquid pool ---
    session.add(TaxReserve(user_id=uid, reserve_account_id=steuer.id))

    # --- allocation buckets (+ Debt and Emergency fund off-the-top markers); Savings/Invest
    #     are linked to real accounts so "Apply this month" can transfer into them ---
    bucket_accounts = {"Savings": savings.id, "Invest": broker.id}
    for name, pct in [("Debt", 1), ("Emergency fund", 1), ("Savings", 40),
                      ("Invest", 35), ("Fun", 15)]:
        session.add(Allocation(user_id=uid, name=name, percent=D(str(pct)),
                               account_id=bucket_accounts.get(name)))

    # --- planned purchases (wishlist; a monthly_save feeds the "Planned purchases fund").
    #     "Urlaub" saves into the Tagesgeld account so "Apply this month" can transfer into it ---
    for pname, price, save, pacc in [("Nintendo Switch 2", "499", "100", None),
                                      ("Urlaub Lissabon", "1000", "150", savings.id),
                                      ("MacBook Pro", "2500", "0", None)]:
        session.add(PlannedPurchase(user_id=uid, name=pname, price=D(price),
                                    monthly_save=D(save), account_id=pacc))

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
        payment_terms_days=14,
        payment_info="Zahlung bevorzugt an Revolut: revolut.me/andre-demo",
        digest_cadence="weekly",
        default_language="de",
        default_hourly_rate=D("45"),
        next_invoice_number=100003,
    ))

    # === Taxes: EÜR profile + per-year inputs ===
    session.add(TaxProfile(
        user_id=uid,
        business_type="freiberufler",
        mixed_use_rates={str(cats["Internet"].id): 50, str(cats["Mobile"].id): 60},
        km_rate=D("0.30"),
        home_office_mode="flat",
    ))
    for fy in (TODAY.year - 1, TODAY.year):
        session.add(TaxYearInput(
            user_id=uid, year=fy,
            other_taxable_income=D("54000"),  # the seeded Salary (4.500 €/mo)
            withheld_lohnsteuer=D("12100"),   # ≈ Lohnsteuer the employer withheld on it
            home_office_days=120, business_km=D("1500"),
            notes="Demo-Werte für die EÜR.",
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
        issue_date=(now - timedelta(days=18)).date(),
        due_date=(now - timedelta(days=4)).date(), place="Köln", language="de",
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

    # A second invoice for Helios, already sent but now OVERDUE (due date in the past) →
    # shows the overdue badge + Mahnwesen.
    overdue_inv = Invoice(
        user_id=uid, client_id=helios.id, number="100002",
        issue_date=(now - timedelta(days=30)).date(),
        due_date=(now - timedelta(days=16)).date(), place="Köln", language="de",
        intro_text="", status="sent", vat_rate=D("0"), total=D("0"),
        reminder_level=1, last_reminder_at=(now - timedelta(days=9)),  # Zahlungserinnerung sent
    )
    session.add(overdue_inv)
    session.flush()
    hel_billed = [
        tentry(helios, 6, 10, 120, "Monatliche Webseiten-Pflege", overdue_inv),
        tentry(helios, 2, 15, 60, "Öffnungszeiten & Notdienst aktualisiert", overdue_inv),
    ]
    hel_items: list[InvoiceItem] = []
    hel_total = D("0")
    for i, te in enumerate(hel_billed):
        hrs = (D(te.minutes) / D(60)).quantize(D("0.01"))
        amount = _q(hrs * helios.hourly_rate)
        hel_total += amount
        hel_items.append(InvoiceItem(description=te.description, hours=hrs,
                                     rate=helios.hourly_rate, amount=amount, position=i))
    overdue_inv.items = hel_items
    overdue_inv.total = _q(hel_total)

    # A third Brandwerk invoice that demonstrates "group by project": many varied entries across
    # two projects bundled into one line each (theme header + tasks as bullets, hours summed).
    grouped_inv = Invoice(
        user_id=uid, client_id=brandwerk.id, number="100003",
        issue_date=(now - timedelta(days=2)).date(),
        due_date=(now + timedelta(days=12)).date(), place="Köln", language="de",
        intro_text=(
            "Sehr geehrte Damen und Herren,\n\nvielen Dank für die gute Zusammenarbeit. "
            "Hiermit stelle ich Ihnen die folgenden Leistungen in Rechnung:"
        ),
        status="draft", vat_rate=D("0"), total=D("0"),
    )
    session.add(grouped_inv)
    session.flush()
    grouped_billed = [
        tentry(brandwerk, 14, 9, 120, "Newsletter-Template gebaut", grouped_inv, relaunch),
        tentry(brandwerk, 13, 11, 75, "Produktbilder optimiert & eingepflegt", grouped_inv, relaunch),
        tentry(brandwerk, 12, 14, 45, "SEO-Meta-Tags ergänzt", grouped_inv, relaunch),
        tentry(brandwerk, 9, 10, 60, "Sicherheitsupdates eingespielt", grouped_inv, care),
        tentry(brandwerk, 8, 16, 30, "Monatliches Backup geprüft", grouped_inv, care),
    ]
    _proj_by_id = {relaunch.id: relaunch, care.id: care}

    def _grp_rate(e):
        p = _proj_by_id.get(e.project_id)
        return p.hourly_rate if p and p.hourly_rate is not None else brandwerk.hourly_rate

    def _grp_name(pid):
        p = _proj_by_id.get(pid)
        return p.name if p else None

    g_items, g_net = build_items(grouped_billed, _grp_rate, _grp_name, group_by="project", lang="de")
    grouped_inv.items = g_items
    grouped_inv.total = _q(g_net)

    tentry(mondia, 8, 9, 240, "Speisekarte für Web & Print gestaltet")
    tentry(mondia, 4, 14, 180, "Instagram-Grafiken (5 Posts)")
    tentry(mondia, 4, 17, 90, "Logo-Varianten")

    # A monthly flat-fee retainer for Helios — auto-drafts an invoice next month.
    session.add(RecurringInvoice(
        user_id=uid, client_id=helios.id, cadence="monthly", mode="flat",
        amount=D("80"), description="Monatliche Webseiten-Pflege (Pauschale)",
        language="de", next_run=TODAY + timedelta(days=30), active=True,
    ))

    # === Fahrtenbuch: a few business trips (their km feed the EÜR Reisekosten) ===
    session.add_all([
        Trip(user_id=uid, date=TODAY - timedelta(days=40), from_place="Köln", to_place="Düsseldorf",
             km=D("84"), purpose="Kick-off Studio Brandwerk", client_id=brandwerk.id),
        Trip(user_id=uid, date=TODAY - timedelta(days=21), from_place="Köln", to_place="Brühl",
             km=D("32"), purpose="Vor-Ort-Termin Helios", client_id=helios.id),
        Trip(user_id=uid, date=TODAY - timedelta(days=7), from_place="Köln", to_place="Bonn",
             km=D("56"), purpose="Fotoshooting Café Mondia", client_id=mondia.id),
    ])

    session.flush()
    return {
        "transactions": len(ledger), "accounts": 5, "categories": len(cats),
        "clients": 3, "projects": 2, "time_entries": 16, "invoices": 3, "retainers": 1, "trips": 3,
    }


def run() -> dict:
    """CLI entrypoint: find-or-create the DEMO_EMAIL user, wipe, reseed."""
    with SessionLocal() as session:
        from backend.auth.security import hash_password
        user = session.execute(select(User).where(User.email == DEMO_EMAIL)).scalars().first()
        if user is None:
            user = User(email=DEMO_EMAIL, password_hash=hash_password(uuid.uuid4().hex))
            session.add(user)
            session.flush()
        wipe(session, user.id)
        result = seed_demo_for_user(session, user.id)
        session.commit()
        return result


if __name__ == "__main__":
    print(run())
