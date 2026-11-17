"""Data types used across the reconciliation tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Transaction:
    """One line from a bank statement or a cash book.

    Amounts follow one sign convention for both files:
    positive = money in (receipts, deposits), negative = money out (payments, charges).
    """

    id: str            # e.g. "B7" or "L12": source letter + line number in the file
    date: date
    description: str
    amount: Decimal
    reference: str = ""


@dataclass(frozen=True)
class Match:
    bank: Transaction
    book: Transaction
    rule: str          # "reference", "exact" or "date-tolerance"

    @property
    def days_apart(self) -> int:
        return abs((self.bank.date - self.book.date).days)


@dataclass(frozen=True)
class Discrepancy:
    """A bank line and a book line that share a reference but disagree on amount."""

    bank: Transaction
    book: Transaction

    @property
    def difference(self) -> Decimal:
        """Correction needed in the books: bank amount minus book amount."""
        return self.bank.amount - self.book.amount

    @property
    def possible_transposition(self) -> bool:
        """A difference divisible by 9 often means two digits were swapped (45,000 vs 54,000)."""
        diff = abs(self.difference)
        return diff != 0 and (diff * 100) % 9 == 0


@dataclass
class Statement:
    """Bank reconciliation statement at period end."""

    bank_balance: Decimal
    book_balance: Decimal
    deposits_in_transit: list[Transaction]
    outstanding_payments: list[Transaction]
    bank_credits_not_in_books: list[Transaction]
    bank_debits_not_in_books: list[Transaction]
    discrepancies: list[Discrepancy]

    @staticmethod
    def _total(items: list[Transaction]) -> Decimal:
        return sum((t.amount for t in items), Decimal("0"))

    @property
    def adjusted_bank_balance(self) -> Decimal:
        # Receipts already in the books but not yet on the statement are added;
        # payments already in the books but not yet cleared are subtracted (they are negative).
        return (self.bank_balance
                + self._total(self.deposits_in_transit)
                + self._total(self.outstanding_payments))

    @property
    def adjusted_book_balance(self) -> Decimal:
        corrections = sum((d.difference for d in self.discrepancies), Decimal("0"))
        return (self.book_balance
                + self._total(self.bank_credits_not_in_books)
                + self._total(self.bank_debits_not_in_books)
                + corrections)

    @property
    def unexplained_difference(self) -> Decimal:
        return self.adjusted_bank_balance - self.adjusted_book_balance

    @property
    def is_reconciled(self) -> bool:
        return self.unexplained_difference == 0


@dataclass
class Result:
    matches: list[Match] = field(default_factory=list)
    discrepancies: list[Discrepancy] = field(default_factory=list)
    unmatched_bank: list[Transaction] = field(default_factory=list)
    unmatched_book: list[Transaction] = field(default_factory=list)
    possible_duplicates: list[tuple[Transaction, Transaction]] = field(default_factory=list)
    statement: Statement | None = None

    @property
    def match_rate(self) -> float:
        total = len(self.matches) + len(self.unmatched_bank) + len(self.discrepancies)
        return len(self.matches) / total if total else 1.0
