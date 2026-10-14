"""
Unit tests for git-ledger core functionality using standard library unittest.
"""

from datetime import date
from decimal import Decimal
import tempfile
from pathlib import Path
import unittest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitledger.chart import ChartOfAccounts
from gitledger.models import Account, AccountType, EntryLine, Transaction
from gitledger.ledger import Ledger
from gitledger.reports import ReportGenerator
from gitledger.importer import CSVBankImporter


class TestGitLedger(unittest.TestCase):
    def test_balanced_transaction(self):
        lines = [
            EntryLine(account="1010", amount=Decimal("100.00"), is_debit=True),
            EntryLine(account="4100", amount=Decimal("100.00"), is_debit=False),
        ]
        tx = Transaction(id="tx-1", date=date(2026, 1, 1), description="Donation", lines=lines)
        self.assertTrue(tx.is_balanced)
        self.assertEqual(tx.total_debits, Decimal("100.00"))
        self.assertEqual(tx.total_credits, Decimal("100.00"))
        self.assertEqual(tx.imbalance, Decimal("0.00"))

    def test_unbalanced_transaction(self):
        lines = [
            EntryLine(account="1010", amount=Decimal("100.00"), is_debit=True),
            EntryLine(account="4100", amount=Decimal("90.00"), is_debit=False),
        ]
        tx = Transaction(id="tx-2", date=date(2026, 1, 1), description="Error Entry", lines=lines)
        self.assertFalse(tx.is_balanced)
        self.assertEqual(tx.imbalance, Decimal("10.00"))

    def test_ledger_validation(self):
        chart = ChartOfAccounts.default_nonprofit()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            ledger = Ledger(chart=chart, root_dir=tmp_path)
            
            # Valid transaction
            tx1 = Transaction(
                id="tx-1",
                date=date(2026, 1, 1),
                description="Valid",
                lines=[
                    EntryLine(account="1010", amount=Decimal("50.00"), is_debit=True),
                    EntryLine(account="5010", amount=Decimal("50.00"), is_debit=False),
                ],
            )
            ledger.transactions.append(tx1)
            self.assertEqual(len(ledger.validate()), 0)

            # Out-of-balance transaction
            tx2 = Transaction(
                id="tx-2",
                date=date(2026, 1, 2),
                description="Invalid",
                lines=[
                    EntryLine(account="1010", amount=Decimal("50.00"), is_debit=True),
                    EntryLine(account="5010", amount=Decimal("40.00"), is_debit=False),
                ],
            )
            ledger.transactions.append(tx2)
            errors = ledger.validate()
            self.assertEqual(len(errors), 1)
            self.assertIn("out of balance", errors[0])

    def test_financial_reports(self):
        chart = ChartOfAccounts.default_nonprofit()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            ledger = Ledger(chart=chart, root_dir=tmp_path)

            # 1. Opening balance: Dr Cash $1000, Cr Opening Equity $1000
            tx1 = Transaction(
                id="tx-1",
                date=date(2026, 1, 1),
                description="Opening",
                lines=[
                    EntryLine(account="1010", amount=Decimal("1000.00"), is_debit=True),
                    EntryLine(account="3000", amount=Decimal("1000.00"), is_debit=False),
                ],
            )
            # 2. Revenue: Dr Cash $500, Cr Contribution $500
            tx2 = Transaction(
                id="tx-2",
                date=date(2026, 1, 10),
                description="Donation",
                lines=[
                    EntryLine(account="1010", amount=Decimal("500.00"), is_debit=True),
                    EntryLine(account="4100", amount=Decimal("500.00"), is_debit=False),
                ],
            )
            # 3. Expense: Dr Domain $50, Cr Cash $50
            tx3 = Transaction(
                id="tx-3",
                date=date(2026, 1, 20),
                description="Domain",
                lines=[
                    EntryLine(account="5010", amount=Decimal("50.00"), is_debit=True),
                    EntryLine(account="1010", amount=Decimal("50.00"), is_debit=False),
                ],
            )
            ledger.transactions.extend([tx1, tx2, tx3])

            rep = ReportGenerator(ledger)

            # Trial balance should balance at $1,500
            tb_text = rep.trial_balance()
            self.assertIn("1,500.00", tb_text)
            self.assertNotIn("OUT OF BALANCE", tb_text)

            # Income statement: Revenue $500, Expenses $50, Net Surplus $450
            inc_text = rep.income_statement()
            self.assertIn("500.00", inc_text)
            self.assertIn("50.00", inc_text)
            self.assertIn("450.00", inc_text)

            # Balance sheet: Assets $1450, Liab $0, Equity $1000 + Surplus $450 = $1450
            bs_text = rep.balance_sheet()
            self.assertIn("1,450.00", bs_text)
            self.assertNotIn("OUT OF BALANCE", bs_text)


if __name__ == "__main__":
    unittest.main()
