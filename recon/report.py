"""Turn a reconciliation result into a terminal summary, a CSV and an HTML report."""

from __future__ import annotations

import csv
import html
from datetime import date
from decimal import Decimal
from pathlib import Path

from .models import Result, Transaction


def money(value: Decimal) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{abs(value):,.2f}"


# ---------------------------------------------------------------- terminal

def summary_text(result: Result, currency: str = "KES") -> str:
    lines = [
        "BANK RECONCILIATION",
        "=" * 52,
        f"Matched              {len(result.matches):>4}   ({result.match_rate:.0%} of bank lines)",
        f"Discrepancies        {len(result.discrepancies):>4}",
        f"Only on statement    {len(result.unmatched_bank):>4}",
        f"Only in cash book    {len(result.unmatched_book):>4}",
        f"Possible duplicates  {len(result.possible_duplicates):>4}",
    ]
    for d in result.discrepancies:
        hint = "  <- divisible by 9: possible transposition" if d.possible_transposition else ""
        lines.append(f"  ! {d.book.reference or d.book.description}: bank {money(d.bank.amount)}"
                     f" vs book {money(d.book.amount)}{hint}")
    s = result.statement
    if s:
        lines += [
            "-" * 52,
            f"Adjusted bank balance  {currency} {money(s.adjusted_bank_balance):>16}",
            f"Adjusted book balance  {currency} {money(s.adjusted_book_balance):>16}",
            f"Unexplained difference {currency} {money(s.unexplained_difference):>16}",
            "RECONCILED" if s.is_reconciled else "NOT RECONCILED: investigate the difference",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------- csv

def write_csv(result: Result, path: str | Path) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["status", "rule", "bank_id", "bank_date", "bank_description", "bank_amount",
                    "book_id", "book_date", "book_description", "book_reference", "book_amount"])
        blank = [""] * 4
        for m in result.matches:
            w.writerow(["matched", m.rule, *_cells(m.bank), *_cells(m.book, ref=True)])
        for d in result.discrepancies:
            w.writerow(["discrepancy", "", *_cells(d.bank), *_cells(d.book, ref=True)])
        for t in result.unmatched_bank:
            w.writerow(["only on statement", "", *_cells(t), *blank, ""])
        for t in result.unmatched_book:
            w.writerow(["only in cash book", "", *blank, *_cells(t, ref=True)])


def _cells(t: Transaction, ref: bool = False) -> list[str]:
    cells = [t.id, t.date.isoformat(), t.description]
    if ref:
        cells.append(t.reference)
    cells.append(str(t.amount))
    return cells


# ---------------------------------------------------------------- html

CSS = """
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;color:#1d2433;background:#f5f6f8;line-height:1.5}
.wrap{max-width:1040px;margin:0 auto;padding:32px 20px 60px}
header h1{font-size:1.7rem;margin:0 0 4px}header p{margin:0;color:#5b6475}
.banner{background:#0b0d10;color:#eef1f5;padding:10px 20px;font-size:.88rem;text-align:center}
.banner a{color:#5ee7ff}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:24px 0}
.card{background:#fff;border:1px solid #e3e6eb;border-radius:12px;padding:14px 16px}
.card b{display:block;font-size:1.5rem}.card span{color:#5b6475;font-size:.85rem}
.ok{color:#0f7b4f}.bad{color:#b42318}.warn{color:#9a5b00}
section{background:#fff;border:1px solid #e3e6eb;border-radius:12px;padding:20px;margin-top:18px}
section h2{font-size:1.1rem;margin:0 0 4px}section > p{margin:0 0 12px;color:#5b6475;font-size:.9rem}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th{text-align:left;color:#5b6475;font-weight:600;border-bottom:1px solid #e3e6eb;padding:8px 6px}
td{border-bottom:1px solid #f0f1f4;padding:8px 6px;vertical-align:top}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;font-size:.75rem;padding:1px 8px;border-radius:999px;background:#eef1f5}
.stmt td{border:none;padding:4px 6px}.stmt .sub td{padding-left:24px;color:#5b6475}
.stmt .total td{border-top:1px solid #1d2433;font-weight:700}
.scroll{overflow-x:auto}
.result{font-weight:700;padding:10px 14px;border-radius:10px;margin-top:12px}
.result.ok{background:#e7f6ee}.result.bad{background:#fdecea}
"""


def _rows(items: list[Transaction], ref: bool = False) -> str:
    out = []
    for t in items:
        ref_cell = f"<td>{html.escape(t.reference)}</td>" if ref else ""
        out.append(f"<tr><td>{t.date:%d %b %Y}</td><td>{html.escape(t.description)}</td>{ref_cell}"
                   f"<td class='num'>{money(t.amount)}</td></tr>")
    return "".join(out) or f"<tr><td colspan='{4 if ref else 3}'>None</td></tr>"


def _stmt_block(label: str, items: list[Transaction], sign: str) -> str:
    total = sum((t.amount for t in items), Decimal("0"))
    rows = [f"<tr><td>{label}</td><td></td><td class='num'>{sign}{money(abs(total))}</td></tr>"]
    for t in items:
        rows.append(f"<tr class='sub'><td>{t.date:%d %b} · {html.escape(t.description)}</td>"
                    f"<td class='num'>{money(abs(t.amount))}</td><td></td></tr>")
    return "".join(rows)


def write_html(result: Result, path: str | Path, *, title: str = "Bank reconciliation",
               period: str = "", currency: str = "KES", banner: str = "") -> None:
    s = result.statement
    status = ""
    if s:
        cls = "ok" if s.is_reconciled else "bad"
        status = f"<div class='card'><b class='{cls}'>{'Reconciled' if s.is_reconciled else 'Not reconciled'}</b><span>Unexplained difference {currency} {money(s.unexplained_difference)}</span></div>"

    cards = (
        f"<div class='card'><b>{len(result.matches)}</b><span>Matched ({result.match_rate:.0%} of bank lines)</span></div>"
        f"<div class='card'><b class='{'warn' if result.discrepancies else 'ok'}'>{len(result.discrepancies)}</b><span>Amount discrepancies</span></div>"
        f"<div class='card'><b>{len(result.unmatched_bank)}</b><span>Only on statement</span></div>"
        f"<div class='card'><b>{len(result.unmatched_book)}</b><span>Only in cash book</span></div>"
        + status
    )

    disc_rows = "".join(
        f"<tr><td>{html.escape(d.book.reference)}</td><td>{html.escape(d.bank.description)}</td>"
        f"<td class='num'>{money(d.bank.amount)}</td><td class='num'>{money(d.book.amount)}</td>"
        f"<td class='num'>{money(d.difference)}</td>"
        f"<td>{'<span class=tag>Divisible by 9: possible transposed digits</span>' if d.possible_transposition else ''}</td></tr>"
        for d in result.discrepancies) or "<tr><td colspan='6'>None</td></tr>"

    dup_rows = "".join(
        f"<tr><td>{a.id} / {b.id}</td><td>{a.date:%d %b %Y}</td><td>{html.escape(a.description)}</td>"
        f"<td class='num'>{money(a.amount)}</td></tr>"
        for a, b in result.possible_duplicates) or "<tr><td colspan='4'>None</td></tr>"

    match_rows = "".join(
        f"<tr><td>{m.bank.date:%d %b}</td><td>{html.escape(m.bank.description)}</td>"
        f"<td>{html.escape(m.book.description)}</td><td><span class='tag'>{m.rule}</span>"
        f"{f' ({m.days_apart}d)' if m.days_apart else ''}</td><td class='num'>{money(m.bank.amount)}</td></tr>"
        for m in result.matches)

    stmt_html = ""
    if s:
        corrections = sum((d.difference for d in s.discrepancies), Decimal("0"))
        corr_row = (f"<tr><td>Add/(less): corrections for discrepancies</td><td></td>"
                    f"<td class='num'>{money(corrections)}</td></tr>") if s.discrepancies else ""
        cls = "ok" if s.is_reconciled else "bad"
        msg = ("Reconciled: the adjusted balances agree."
               if s.is_reconciled else
               f"Not reconciled: {currency} {money(s.unexplained_difference)} is still unexplained.")
        stmt_html = f"""
<section>
  <h2>Bank reconciliation statement</h2>
  <p>Amounts in {currency}{f' · {html.escape(period)}' if period else ''}.</p>
  <table class="stmt">
    <tr><td><b>Balance as per bank statement</b></td><td></td><td class='num'><b>{money(s.bank_balance)}</b></td></tr>
    {_stmt_block('Add: deposits in transit', s.deposits_in_transit, '+')}
    {_stmt_block('Less: outstanding payments', s.outstanding_payments, '−')}
    <tr class="total"><td>Adjusted bank balance</td><td></td><td class='num'>{money(s.adjusted_bank_balance)}</td></tr>
    <tr><td colspan="3">&nbsp;</td></tr>
    <tr><td><b>Balance as per cash book</b></td><td></td><td class='num'><b>{money(s.book_balance)}</b></td></tr>
    {_stmt_block('Add: bank credits not yet in books', s.bank_credits_not_in_books, '+')}
    {_stmt_block('Less: bank charges and debits not yet in books', s.bank_debits_not_in_books, '−')}
    {corr_row}
    <tr class="total"><td>Adjusted cash book balance</td><td></td><td class='num'>{money(s.adjusted_book_balance)}</td></tr>
  </table>
  <div class="result {cls}">{msg}</div>
</section>"""

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}</style></head><body>
{f'<div class="banner">{banner}</div>' if banner else ''}
<div class="wrap">
<header><h1>{html.escape(title)}</h1><p>{html.escape(period)}{' · ' if period else ''}Generated {date.today():%d %b %Y}</p></header>
<div class="cards">{cards}</div>
{stmt_html}
<section><h2>Discrepancies</h2><p>Same reference on both sides, different amounts. Correct the books or query the bank.</p>
<div class="scroll"><table><tr><th>Reference</th><th>Bank description</th><th class='num'>Bank</th><th class='num'>Cash book</th><th class='num'>Difference</th><th></th></tr>{disc_rows}</table></div></section>
<section><h2>Only on the bank statement</h2><p>Record these in the cash book (bank charges, interest, direct deposits).</p>
<div class="scroll"><table><tr><th>Date</th><th>Description</th><th class='num'>Amount</th></tr>{_rows(result.unmatched_bank)}</table></div></section>
<section><h2>Only in the cash book</h2><p>Timing differences: deposits in transit and payments not yet cleared.</p>
<div class="scroll"><table><tr><th>Date</th><th>Description</th><th>Reference</th><th class='num'>Amount</th></tr>{_rows(result.unmatched_book, ref=True)}</table></div></section>
<section><h2>Possible duplicates</h2><p>Same date, amount and description appearing twice in one file.</p>
<div class="scroll"><table><tr><th>Lines</th><th>Date</th><th>Description</th><th class='num'>Amount</th></tr>{dup_rows}</table></div></section>
<section><h2>Matched transactions</h2><p>How each bank line was paired with the cash book.</p>
<div class="scroll"><table><tr><th>Date</th><th>Bank description</th><th>Cash book description</th><th>Rule</th><th class='num'>Amount</th></tr>{match_rows}</table></div></section>
</div></body></html>"""
    Path(path).write_text(page, encoding="utf-8")
