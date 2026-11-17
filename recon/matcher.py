"""Match bank statement lines against cash book entries."""

from __future__ import annotations

import re
from decimal import Decimal

from .models import Discrepancy, Match, Result, Statement, Transaction


def _mentions(reference: str, text: str) -> bool:
    """True if `reference` appears in `text` as a whole token (case-insensitive)."""
    if not reference:
        return False
    return re.search(rf"(?<![A-Z0-9]){re.escape(reference.upper())}(?![A-Z0-9])", text.upper()) is not None


def find_duplicates(rows: list[Transaction]) -> list[tuple[Transaction, Transaction]]:
    """Pairs of lines with the same date, amount and description: possible double postings."""
    seen: dict[tuple, Transaction] = {}
    pairs = []
    for t in rows:
        key = (t.date, t.amount, t.description.strip().lower())
        if key in seen:
            pairs.append((seen[key], t))
        else:
            seen[key] = t
    return pairs


def reconcile(bank: list[Transaction], book: list[Transaction], *,
              tolerance_days: int = 3,
              bank_balance: Decimal | None = None,
              book_balance: Decimal | None = None) -> Result:
    """Match the two lists in passes, from the most certain rule to the least.

    1. reference      the cash book reference (invoice, cheque no.) appears in the bank
                      description and the amounts agree
    2. exact          same amount on the same date
    3. date-tolerance same amount within `tolerance_days` (closest date wins)

    A shared reference with different amounts is reported as a discrepancy, not a match.
    """
    open_bank = list(bank)
    open_book = list(book)
    result = Result(possible_duplicates=find_duplicates(bank) + find_duplicates(book))

    def take(b: Transaction, l: Transaction, rule: str) -> None:
        open_bank.remove(b)
        open_book.remove(l)
        result.matches.append(Match(bank=b, book=l, rule=rule))

    # Pass 1: references
    for l in [x for x in open_book if x.reference]:
        candidates = [b for b in open_bank if _mentions(l.reference, b.description)]
        same_amount = [b for b in candidates if b.amount == l.amount]
        if same_amount:
            take(min(same_amount, key=lambda b: abs((b.date - l.date).days)), l, "reference")
        elif len(candidates) == 1:
            b = candidates[0]
            open_bank.remove(b)
            open_book.remove(l)
            result.discrepancies.append(Discrepancy(bank=b, book=l))

    # Pass 2: same amount, same date
    for l in list(open_book):
        hit = next((b for b in open_bank if b.amount == l.amount and b.date == l.date), None)
        if hit:
            take(hit, l, "exact")

    # Pass 3: same amount, nearby date
    for l in list(open_book):
        near = [b for b in open_bank
                if b.amount == l.amount and abs((b.date - l.date).days) <= tolerance_days]
        if near:
            take(min(near, key=lambda b: abs((b.date - l.date).days)), l, "date-tolerance")

    result.unmatched_bank = sorted(open_bank, key=lambda t: t.date)
    result.unmatched_book = sorted(open_book, key=lambda t: t.date)

    if bank_balance is not None and book_balance is not None:
        result.statement = Statement(
            bank_balance=bank_balance,
            book_balance=book_balance,
            deposits_in_transit=[t for t in result.unmatched_book if t.amount > 0],
            outstanding_payments=[t for t in result.unmatched_book if t.amount < 0],
            bank_credits_not_in_books=[t for t in result.unmatched_bank if t.amount > 0],
            bank_debits_not_in_books=[t for t in result.unmatched_bank if t.amount < 0],
            discrepancies=result.discrepancies,
        )
    return result
