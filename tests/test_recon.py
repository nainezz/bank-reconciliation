import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from recon import Transaction, load_transactions, reconcile
from recon.loader import LoadError, parse_amount, parse_date
from recon.models import Discrepancy

SAMPLE = Path(__file__).resolve().parent.parent / "sample_data"


def tx(id, d, desc, amount, ref=""):
    return Transaction(id=id, date=date.fromisoformat(d), description=desc,
                       amount=Decimal(amount), reference=ref)


class ParsingTests(unittest.TestCase):
    def test_amount_formats(self):
        self.assertEqual(parse_amount("1,250.50"), Decimal("1250.50"))
        self.assertEqual(parse_amount("(300)"), Decimal("-300.00"))
        self.assertEqual(parse_amount("KES 4,000"), Decimal("4000.00"))
        with self.assertRaises(ValueError):
            parse_amount("abc")

    def test_date_formats(self):
        self.assertEqual(parse_date("2026-11-05"), date(2026, 11, 5))
        self.assertEqual(parse_date("05/11/2026"), date(2026, 11, 5))
        with self.assertRaises(ValueError):
            parse_date("11/31/2026")

    def test_bad_row_reports_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bank.csv"
            f.write_text("date,description,amount\n2026-11-01,ok,10\n2026-11-02,bad,ten\n")
            with self.assertRaisesRegex(LoadError, "line 3"):
                load_transactions(f, "B")

    def test_missing_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bank.csv"
            f.write_text("date,amount\n2026-11-01,10\n")
            with self.assertRaisesRegex(LoadError, "description"):
                load_transactions(f, "B")


class MatchingTests(unittest.TestCase):
    def test_reference_match_beats_date(self):
        bank = [tx("B1", "2026-11-07", "CHQ 000412 PRESENTED", "-500")]
        book = [tx("L1", "2026-11-01", "Rent", "-500", ref="000412")]
        r = reconcile(bank, book)
        self.assertEqual([m.rule for m in r.matches], ["reference"])

    def test_reference_is_whole_token(self):
        bank = [tx("B1", "2026-11-20", "CHQ 0004120", "-500")]
        book = [tx("L1", "2026-11-01", "Rent", "-500", ref="000412")]
        r = reconcile(bank, book)
        self.assertEqual(r.matches, [])

    def test_exact_then_tolerance(self):
        bank = [tx("B1", "2026-11-05", "KPLC", "-100"), tx("B2", "2026-11-12", "DEPOSIT", "250")]
        book = [tx("L1", "2026-11-05", "Electricity", "-100"), tx("L2", "2026-11-10", "Cash", "250")]
        r = reconcile(bank, book, tolerance_days=3)
        self.assertEqual(sorted(m.rule for m in r.matches), ["date-tolerance", "exact"])

    def test_outside_tolerance_stays_unmatched(self):
        bank = [tx("B1", "2026-11-20", "DEPOSIT", "250")]
        book = [tx("L1", "2026-11-10", "Cash", "250")]
        r = reconcile(bank, book, tolerance_days=3)
        self.assertEqual(len(r.unmatched_bank), 1)
        self.assertEqual(len(r.unmatched_book), 1)

    def test_discrepancy_and_transposition_hint(self):
        bank = [tx("B1", "2026-11-09", "RTGS INV-1043", "45000")]
        book = [tx("L1", "2026-11-08", "Sale", "54000", ref="INV-1043")]
        r = reconcile(bank, book)
        self.assertEqual(len(r.discrepancies), 1)
        d = r.discrepancies[0]
        self.assertEqual(d.difference, Decimal("-9000"))
        self.assertTrue(d.possible_transposition)

    def test_non_transposition_difference(self):
        d = Discrepancy(bank=tx("B1", "2026-11-01", "x", "100"), book=tx("L1", "2026-11-01", "x", "105"))
        self.assertFalse(d.possible_transposition)

    def test_duplicates_detected(self):
        bank = [tx("B1", "2026-11-18", "SAFARICOM", "-6000"), tx("B2", "2026-11-18", "safaricom ", "-6000")]
        r = reconcile(bank, [])
        self.assertEqual(len(r.possible_duplicates), 1)


class SampleDataTests(unittest.TestCase):
    def test_sample_reconciles(self):
        bank = load_transactions(SAMPLE / "bank_statement.csv", "B")
        book = load_transactions(SAMPLE / "cashbook.csv", "L")
        r = reconcile(bank, book, bank_balance=Decimal("160833.50"), book_balance=Decimal("168801.00"))
        s = r.statement
        self.assertEqual(len(r.matches), 10)
        self.assertEqual(s.adjusted_bank_balance, Decimal("156333.50"))
        self.assertTrue(s.is_reconciled)

    def test_wrong_balance_is_flagged(self):
        bank = load_transactions(SAMPLE / "bank_statement.csv", "B")
        book = load_transactions(SAMPLE / "cashbook.csv", "L")
        r = reconcile(bank, book, bank_balance=Decimal("160000.00"), book_balance=Decimal("168801.00"))
        self.assertFalse(r.statement.is_reconciled)
        self.assertEqual(r.statement.unexplained_difference, Decimal("-833.50"))


if __name__ == "__main__":
    unittest.main()
