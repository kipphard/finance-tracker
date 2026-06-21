"""Send an invoice PDF by email over SMTP (e.g. Gmail with an app password)."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage


def _send(settings, msg: EmailMessage) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


def send_invoice_email(settings, *, to: str, subject: str, body: str,
                       pdf: bytes, filename: str, from_addr: str) -> None:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject or ""
    msg.set_content(body or "")
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=filename)
    _send(settings, msg)


def send_text_email(settings, *, to: str, subject: str, body: str, from_addr: str) -> None:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject or ""
    msg.set_content(body or "")
    _send(settings, msg)
