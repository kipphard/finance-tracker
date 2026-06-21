"""Render a German Kleinunternehmer (§19 UStG) invoice to PDF bytes with reportlab.

Layout mirrors André's existing invoices: sender (top-right), client (left), place+date,
"Invoice No.", a Service / Duration (hours) / Total Price table, total, the §19 note, a
closing, and a bank-details + tax-number footer.
"""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.invoicing.i18n import texts
from backend.invoicing.text import flatten


def _girocode(profile, invoice):
    """A GiroCode (EPC-QR) so the client can scan-to-pay a SEPA transfer. None if no IBAN."""
    iban = (profile.iban or "").replace(" ", "")
    name = (getattr(profile, "company_name", "") or profile.name or "")[:70]
    amount = Decimal(invoice.total or 0)
    if not iban or not name or amount < Decimal("0.01"):
        return None
    payload = "\n".join([
        "BCD", "002", "1", "SCT", (profile.bic or "").replace(" ", ""), name, iban,
        f"EUR{amount:.2f}", "", "", f"Rechnung {invoice.number}"[:140], "",
    ])
    widget = qr.QrCodeWidget(payload, barLevel="M")
    b = widget.getBounds()
    w, h = b[2] - b[0], b[3] - b[1]
    side = 28 * mm
    d = Drawing(side, side, transform=[side / w, 0, 0, side / h, 0, 0])
    d.add(widget)
    return d


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _multiline(text: str) -> str:
    return _esc(text).replace("\n", "<br/>")


def _money(value: Decimal) -> str:
    value = Decimal(value)
    if value == value.to_integral_value():
        return f"{int(value)}€"
    return f"{value:.2f}".replace(".", ",") + "€"


def _hours(value: Decimal) -> str:
    value = Decimal(value).normalize()
    s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def render_invoice(profile, client, invoice, project=None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=25 * mm, rightMargin=20 * mm, topMargin=22 * mm, bottomMargin=28 * mm,
    )
    styles = getSampleStyleSheet()
    base = styles["Normal"]
    base.fontName = "Helvetica"
    base.fontSize = 10
    base.leading = 14
    right = ParagraphStyle("right", parent=base, alignment=TA_RIGHT)
    bold = ParagraphStyle("bold", parent=base, fontName="Helvetica-Bold")
    right_bold = ParagraphStyle("right_bold", parent=right, fontName="Helvetica-Bold")

    t = texts(getattr(invoice, "language", None))

    flow = []
    # Sender (top right): name / company / street / "PLZ City" / phone / email
    plz_city = f"{getattr(profile, 'postal_code', '')} {getattr(profile, 'city', '')}".strip()
    sender_lines = [profile.name, profile.company_name, profile.address, plz_city]
    if profile.phone:
        sender_lines.append(f"Tel: {profile.phone}")
    if profile.email:
        sender_lines.append(profile.email)
    sender = "\n".join(line for line in sender_lines if line)
    flow.append(Paragraph(_multiline(sender), right))
    flow.append(Spacer(1, 6 * mm))
    # Recipient: name + address, but don't repeat the name if the address already starts with it.
    addr = (client.address or "").strip()
    name = (client.name or "").strip()
    first_line = addr.splitlines()[0].strip().lower() if addr else ""
    if name and first_line != name.lower():
        recipient = f"{name}\n{addr}" if addr else name
    else:
        recipient = addr or name
    flow.append(Paragraph(_multiline(recipient), base))
    flow.append(Spacer(1, 26 * mm))

    place = (invoice.place or getattr(profile, "city", "") or "").strip()
    datestr = invoice.issue_date.strftime(t["date_format"]).lstrip("0")
    flow.append(Paragraph(f"{place + ', ' if place else ''}{_esc(datestr)}", right))
    flow.append(Spacer(1, 8 * mm))
    flow.append(Paragraph(f"{t['invoice_no']} {_esc(invoice.number)}", bold))
    if project is not None:
        flow.append(Paragraph(f"{t['project']}: {_esc(project.name)}", base))
    flow.append(Spacer(1, 4 * mm))
    intro = invoice.intro_text or t["intro_default"]
    if intro:
        flow.append(Paragraph(_multiline(intro), base))
        flow.append(Spacer(1, 6 * mm))

    # Line items table
    head = ParagraphStyle("th", parent=base, fontName="Helvetica-Bold")
    rows = [[Paragraph(t["service"], head), Paragraph(t["duration"], head),
             Paragraph(t["total_price"], head)]]
    for item in invoice.items:
        dur = _hours(item.hours) if Decimal(item.hours) > 0 else ""  # flat lines show no hours
        rows.append([
            Paragraph(_esc(flatten(item.description)), base),
            Paragraph(dur, right),
            Paragraph(_money(item.amount), right),
        ])
    table = Table(rows, colWidths=[98 * mm, 33 * mm, 34 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#444444")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    flow.append(table)
    flow.append(Spacer(1, 8 * mm))
    total_hours = sum((Decimal(it.hours) for it in invoice.items), Decimal(0))
    flow.append(Paragraph(f"{t['total_hours']}: {_hours(total_hours)}", right))
    flow.append(Spacer(1, 2 * mm))
    vat_rate = Decimal(invoice.vat_rate or 0)
    if vat_rate > 0:
        net = sum((Decimal(it.amount) for it in invoice.items), Decimal(0))
        vat_amount = Decimal(invoice.total) - net
        flow.append(Paragraph(f"{t['net_amount']}: {_money(net)}", right))
        flow.append(Paragraph(
            f"{t['plus_vat'].format(rate=_hours(vat_rate))}: {_money(vat_amount)}", right))
        flow.append(Spacer(1, 1 * mm))
    flow.append(Paragraph(f"{t['invoice_amount']}: {_money(invoice.total)}", right_bold))
    flow.append(Spacer(1, 8 * mm))
    # The §19 small-business note only applies when no VAT is charged.
    if vat_rate == 0:
        flow.append(Paragraph(_multiline(profile.vat_note or t["vat_note_default"]), base))
        flow.append(Spacer(1, 3 * mm))
    if getattr(invoice, "due_date", None):
        due_str = invoice.due_date.strftime(t["date_format"]).lstrip("0")
        flow.append(Paragraph(t["payable_by"].format(date=_esc(due_str)), base))
    else:
        flow.append(Paragraph(t["payable"], base))
    flow.append(Spacer(1, 6 * mm))
    flow.append(Paragraph(t["regards"], base))
    flow.append(Spacer(1, 5 * mm))
    flow.append(Paragraph(_esc(profile.name or profile.company_name), base))

    # Payment instructions + GiroCode (scan-to-pay)
    pay_info = (getattr(profile, "payment_info", "") or "").strip()
    giro = _girocode(profile, invoice)
    if pay_info or giro is not None:
        flow.append(Spacer(1, 8 * mm))
        if pay_info:
            flow.append(Paragraph(_multiline(pay_info), base))
            flow.append(Spacer(1, 2 * mm))
        if giro is not None:
            flow.append(Paragraph(t["giro_hint"], base))
            flow.append(Spacer(1, 2 * mm))
            flow.append(giro)

    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        y = 20 * mm
        left_lines = [t["bank_details"]]
        if profile.iban:
            left_lines.append(f"IBAN: {profile.iban}")
        if profile.bic:
            left_lines.append(f"BIC: {profile.bic}")
        for i, line in enumerate(left_lines):
            canvas.drawString(25 * mm, y - i * 11, line)
        if profile.tax_number:
            canvas.drawRightString(A4[0] - 20 * mm, y, f"{t['tax_number']}: {profile.tax_number}")
        canvas.restoreState()

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
