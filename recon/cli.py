"""Command-line entry point: python -m recon BANK.csv CASHBOOK.csv [options]"""

from __future__ import annotations

import argparse
import sys

from .loader import LoadError, load_transactions, parse_amount
from .matcher import reconcile
from .report import summary_text, write_csv, write_html


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="recon",
        description="Match a bank statement against a cash book and prepare a bank reconciliation.")
    p.add_argument("bank", help="bank statement CSV (date, description, amount)")
    p.add_argument("cashbook", help="cash book CSV (date, description, amount, optional reference)")
    p.add_argument("--bank-balance", help="closing balance on the bank statement")
    p.add_argument("--book-balance", help="closing balance in the cash book")
    p.add_argument("--tolerance", type=int, default=3, metavar="DAYS",
                   help="match equal amounts up to this many days apart (default 3)")
    p.add_argument("--html", metavar="FILE", help="write an HTML report")
    p.add_argument("--csv", metavar="FILE", help="write line-by-line results as CSV")
    p.add_argument("--title", default="Bank reconciliation", help="report title")
    p.add_argument("--period", default="", help="period label, e.g. 'November 2026'")
    p.add_argument("--currency", default="KES", help="currency label (default KES)")
    args = p.parse_args(argv)

    if (args.bank_balance is None) != (args.book_balance is None):
        p.error("give both --bank-balance and --book-balance, or neither")

    try:
        bank = load_transactions(args.bank, "B")
        book = load_transactions(args.cashbook, "L")
        bank_bal = parse_amount(args.bank_balance) if args.bank_balance else None
        book_bal = parse_amount(args.book_balance) if args.book_balance else None
    except (LoadError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = reconcile(bank, book, tolerance_days=args.tolerance,
                       bank_balance=bank_bal, book_balance=book_bal)
    print(summary_text(result, args.currency))

    if args.html:
        write_html(result, args.html, title=args.title, period=args.period, currency=args.currency)
        print(f"\nHTML report: {args.html}")
    if args.csv:
        write_csv(result, args.csv)
        print(f"CSV results: {args.csv}")

    if result.statement and not result.statement.is_reconciled:
        return 1
    return 0
