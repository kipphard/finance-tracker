"""Translations for invoice PDFs. Invoices can be issued in German or English."""
from __future__ import annotations

LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "de"

INVOICE_TEXT = {
    "de": {
        "date_format": "%d.%m.%Y",
        "date_short": "%d.%m.",
        "week": "KW",
        "general": "Allgemein",
        "months": (
            "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ),
        "invoice_no": "Rechnung Nr.",
        "project": "Projekt",
        "service": "Leistung",
        "duration": "Dauer (Stunden)",
        "total_price": "Gesamtpreis",
        "total_hours": "Gesamtstunden",
        "net_amount": "Nettobetrag",
        "plus_vat": "zzgl. USt. ({rate}%)",
        "invoice_amount": "Rechnungsbetrag",
        "payable": "Der Rechnungsbetrag ist sofort fällig.",
        "payable_by": "Bitte überweisen Sie den Rechnungsbetrag bis zum {date}.",
        "giro_hint": "Per Überweisung – QR-Code mit der Banking-App scannen:",
        "regards": "Mit freundlichen Grüßen,",
        "bank_details": "Bankverbindung:",
        "tax_number": "Steuernummer",
        "vat_note_default": "Gemäß § 19 Abs. 1 UStG wird keine Umsatzsteuer berechnet.",
        "intro_default": (
            "Sehr geehrte Damen und Herren,\n\nvielen Dank für die gute Zusammenarbeit. "
            "Hiermit stelle ich Ihnen die folgenden Leistungen in Rechnung:"
        ),
    },
    "en": {
        "date_format": "%B %d, %Y",
        "date_short": "%b %d",
        "week": "Week",
        "general": "General",
        "months": (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        "invoice_no": "Invoice No.",
        "project": "Project",
        "service": "Service",
        "duration": "Duration (hours)",
        "total_price": "Total Price",
        "total_hours": "Total hours",
        "net_amount": "Net amount",
        "plus_vat": "plus VAT ({rate}%)",
        "invoice_amount": "Invoice Amount",
        "payable": "The invoice is payable immediately.",
        "payable_by": "Please transfer the invoice amount by {date}.",
        "giro_hint": "Pay by bank transfer – scan the QR code with your banking app:",
        "regards": "Kind regards,",
        "bank_details": "Bank Details:",
        "tax_number": "Tax Number",
        "vat_note_default": (
            "In accordance with § 19 (1) UStG (German VAT Act), no VAT is charged."
        ),
        "intro_default": (
            "Dear Sir or Madam,\n\nthank you for the successful cooperation. "
            "I hereby invoice you for the following services as agreed:"
        ),
    },
}


def texts(language: str | None) -> dict:
    return INVOICE_TEXT.get(language or DEFAULT_LANGUAGE, INVOICE_TEXT[DEFAULT_LANGUAGE])
