"""Parse a bank-statement CSV into transactions for manual import.

Tolerant of common German bank-export conventions: DD.MM.YYYY dates and "1.234,56" decimals,
plus ISO dates and plain decimals. Header names are matched case-insensitively against a few
common aliases (English + German). Required columns: a date and an amount.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

_DATE_ALIASES = {"date", "datum", "booking_date", "bookingdate", "buchungstag", "valuedate"}
_AMOUNT_ALIASES = {"amount", "betrag", "value", "wert"}
_PAYEE_ALIASES = {"payee", "name", "creditor", "debtor", "merchant", "empfaenger", "auftraggeber"}
_DESC_ALIASES = {"description", "desc", "memo", "reference", "verwendungszweck", "buchungstext"}

_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d")


@dataclass
class ParsedTransaction:
    ts: datetime
    amount: Decimal
    raw_payee: str | None
    description: str | None


@dataclass
class ParseResult:
    rows: list[ParsedTransaction]
    skipped: int  # rows that couldn't be parsed


def _parse_amount(value: str) -> Decimal:
    text = value.strip().replace(" ", "").replace("\xa0", "")
    if "." in text and "," in text:
        # German "1.234,56" -> 1234.56
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    return Decimal(text)


def _parse_date(value: str) -> datetime:
    text = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Last resort: ISO 8601 with time.
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _pick(header_map: dict[str, str], aliases: set[str]) -> str | None:
    for alias in aliases:
        if alias in header_map:
            return header_map[alias]
    return None


def parse_transactions_csv(content: str) -> ParseResult:
    # Sniff the delimiter (German exports often use ';').
    try:
        dialect = csv.Sniffer().sniff(content[:1024], delimiters=",;\t")
        reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    except csv.Error:
        reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")

    header_map = {name.strip().lower(): name for name in reader.fieldnames}
    date_col = _pick(header_map, _DATE_ALIASES)
    amount_col = _pick(header_map, _AMOUNT_ALIASES)
    payee_col = _pick(header_map, _PAYEE_ALIASES)
    desc_col = _pick(header_map, _DESC_ALIASES)

    if date_col is None or amount_col is None:
        raise ValueError(
            "CSV must have a date column (date/datum/...) and an amount column (amount/betrag/...)"
        )

    rows: list[ParsedTransaction] = []
    skipped = 0
    for raw in reader:
        try:
            ts = _parse_date(raw[date_col])
            amount = _parse_amount(raw[amount_col])
        except (ValueError, InvalidOperation, KeyError, TypeError):
            skipped += 1
            continue
        payee = (raw.get(payee_col) or "").strip() or None if payee_col else None
        description = (raw.get(desc_col) or "").strip() or None if desc_col else None
        rows.append(
            ParsedTransaction(ts=ts, amount=amount, raw_payee=payee, description=description)
        )

    return ParseResult(rows=rows, skipped=skipped)
