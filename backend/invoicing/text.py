"""Small text helpers for invoices."""
from __future__ import annotations


def flatten(text: str) -> str:
    """Collapse a multi-line description into one comma-separated line.

    "Kurse erstellen\\nRebranding" -> "Kurse erstellen, Rebranding".
    Leading list markers ("- ", "• ") are stripped.
    """
    parts = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip("-•").strip()
        if line:
            parts.append(line)
    return ", ".join(parts)
