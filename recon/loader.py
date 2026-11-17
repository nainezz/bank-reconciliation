"""Read bank statements and cash books from CSV files."""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import Transaction

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y")
REQUIRED = ("date", "description", "amount")


class LoadError(ValueError):
    """Raised with the file name and line number when a row cannot be read."""


def parse_date(text: str) -> date:
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date {text!r} (use YYYY-MM-DD or DD/MM/YYYY)")


def parse_amount(text: str) -> Decimal:
    """Parse '1,250.50', '-300', '(300.00)' or 'KES 4,000' into a Decimal."""
    cleaned = text.strip().upper().replace(",", "").replace("KES", "").replace("KSH", "").strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1]
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"unrecognised amount {text!r}") from None
    return (-value if negative else value).quantize(Decimal("0.01"))


def load_transactions(path: str | Path, prefix: str) -> list[Transaction]:
    """Load a CSV with columns date, description, amount and an optional reference.

    `prefix` labels each line's id ("B" for bank, "L" for ledger/cash book).
    """
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED if c not in headers]
        if missing:
            raise LoadError(f"{path.name}: missing column(s) {', '.join(missing)}")

        rows: list[Transaction] = []
        for line_no, raw in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            if not any(row.values()):
                continue  # skip blank lines
            try:
                rows.append(Transaction(
                    id=f"{prefix}{line_no}",
                    date=parse_date(row["date"]),
                    description=row["description"],
                    amount=parse_amount(row["amount"]),
                    reference=row.get("reference", ""),
                ))
            except ValueError as exc:
                raise LoadError(f"{path.name}, line {line_no}: {exc}") from None
    return rows
