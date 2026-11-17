# 🏦 Bank Reconciliation Tool (Python)

Match a **bank statement** against a **cash book**, find what doesn't agree, and produce a full **bank reconciliation statement** as a terminal summary, an HTML report and a CSV.

**🔗 Live sample report:** https://nainezz.github.io/bank-reconciliation/

Built by an accountant who writes software. It automates the month-end task of ticking every bank line against the books, then explains every remaining difference the way an accountant would.

## What it does

- **Matches in three passes,** from most to least certain:
  1. **Reference:** the cash book reference (invoice or cheque number) appears in the bank description and the amounts agree.
  2. **Exact:** same amount on the same date.
  3. **Date tolerance:** same amount within a few days (default 3), for deposits and cheques that clear late.
- **Flags discrepancies.** When the same reference shows different amounts, it reports the difference. If the difference is **divisible by 9**, it flags a likely **transposition error** (for example 54,000 posted instead of 45,000).
- **Finds possible duplicates:** the same date, amount and description twice in one file, such as a double bank debit.
- **Builds the reconciliation statement:**
  - Bank side: balance per bank, **add** deposits in transit, **less** outstanding payments.
  - Book side: balance per cash book, **add** bank credits not yet recorded (interest, direct deposits), **less** bank charges, **adjust** for discrepancies.
  - It confirms both adjusted balances agree, or shows the unexplained difference.
- **No dependencies.** Python standard library only. Money uses `Decimal`, never floats, so totals are exact to the cent.

## Quick start

```bash
git clone https://github.com/nainezz/bank-reconciliation.git
cd bank-reconciliation

python -m recon sample_data/bank_statement.csv sample_data/cashbook.csv \
    --bank-balance 160833.50 --book-balance 168801.00 \
    --period "November 2026" --html report.html --csv results.csv
```

Output:

```
BANK RECONCILIATION
====================================================
Matched                10   (62% of bank lines)
Discrepancies           1
Only on statement       5
Only in cash book       4
Possible duplicates     1
  ! INV-1043: bank 45,000.00 vs book 54,000.00  <- divisible by 9: possible transposition
----------------------------------------------------
Adjusted bank balance  KES       156,333.50
Adjusted book balance  KES       156,333.50
Unexplained difference KES             0.00
RECONCILED
```

Or install it as a command: `pip install .`, then run `recon BANK.csv CASHBOOK.csv ...`

## Input format

Two CSV files. Use **positive amounts for money in** and **negative amounts for money out** in both.

| Column | Required | Example |
|---|---|---|
| `date` | yes | `2026-11-05` or `05/11/2026` |
| `description` | yes | `CHQ 000412 PRESENTED` |
| `amount` | yes | `-120,000.00`, `(120000)` or `KES 85,000` |
| `reference` | cash book only, optional | `INV-1041`, `000412` |

Errors name the file and the line, for example `bank.csv, line 7: unrecognised amount 'ten'`.

## Options

| Option | Meaning |
|---|---|
| `--bank-balance`, `--book-balance` | Closing balances; both are needed for the reconciliation statement |
| `--tolerance DAYS` | Days apart allowed for amount-only matches (default 3) |
| `--html FILE` | Write the HTML report |
| `--csv FILE` | Write line-by-line results |
| `--period`, `--title`, `--currency` | Report labels (currency defaults to KES) |

Exit code is `0` when reconciled, `1` when a difference is unexplained, and `2` on input errors, so it can run in scripts.

## Project structure

```
recon/
├── models.py   # Transaction, Match, Discrepancy, Statement, Result
├── loader.py   # CSV reading, date and amount parsing, validation
├── matcher.py  # Matching passes, discrepancies, duplicates, statement
├── report.py   # Terminal summary, CSV and HTML report
└── cli.py      # Command-line interface
sample_data/    # A month of transactions for a sample Kenyan business
tests/          # 13 unit tests
tools/          # Rebuilds the live sample report (index.html)
```

## Tests

```bash
python -m unittest discover -s tests -t .
```

## Sample data

`sample_data/` holds November 2026 for a made-up Nairobi business, Jamii Traders Ltd, with M-Pesa, RTGS, PesaLink and cheque payments, KPLC, KRA and Zuku bills, bank charges with excise duty, a transposition error and a double debit. The figures are invented for demonstration.

## Author

**Nainezz**, a software engineer and accountant in Nairobi, Kenya · [Portfolio](https://nainezz.github.io/portfolio/) · [GitHub](https://github.com/nainezz)

## License

[MIT](LICENSE)
