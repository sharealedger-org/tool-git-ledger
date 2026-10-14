"""
Bank CSV importer and journal entry generator.
"""

from __future__ import annotations
import csv
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from .models import EntryLine, Transaction


class CSVBankImporter:
    """
    Parses standard bank / credit card CSVs into double-entry transactions.
    """
    def __init__(self, default_cash_account: str = "1010", default_expense_account: str = "5900"):
        self.default_cash_account = default_cash_account
        self.default_expense_account = default_expense_account
        # Basic matching rules: keyword -> account code
        self.rules: Dict[str, str] = {
            "github": "5000",
            "aws": "5000",
            "digitalocean": "5000",
            "cloudflare": "5010",
            "namecheap": "5010",
            "godaddy": "5010",
            "google": "5020",
            "zoom": "5020",
            "stripe": "5400",
            "paypal": "5400",
            "donation": "4100",
            "dues": "4000",
            "membership": "4000",
        }

    def guess_account(self, description: str, is_deposit: bool) -> str:
        desc_lower = description.lower()
        for keyword, account_code in self.rules.items():
            if keyword in desc_lower:
                return account_code
        if is_deposit:
            return "4100"  # Default deposit to Contribution
        return self.default_expense_account

    def parse_csv(self, csv_path: Path, cash_account: Optional[str] = None) -> List[Transaction]:
        cash_acc = cash_account or self.default_cash_account
        transactions: List[Transaction] = []

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # Find column names case-insensitively
            field_map = {name.lower().strip(): name for name in (reader.fieldnames or [])}

            date_col = field_map.get("date") or field_map.get("transaction date") or field_map.get("posting date")
            desc_col = field_map.get("description") or field_map.get("memo") or field_map.get("payee") or field_map.get("name")
            amt_col = field_map.get("amount")
            debit_col = field_map.get("debit")
            credit_col = field_map.get("credit")

            if not date_col or not desc_col:
                raise ValueError(f"Could not identify Date and Description columns in CSV: {reader.fieldnames}")

            for idx, row in enumerate(reader, start=1):
                raw_date = row[date_col].strip()
                tx_date = self._parse_date(raw_date)
                if not tx_date:
                    continue

                desc = row[desc_col].strip()
                amt = Decimal("0.00")
                is_deposit = False

                if amt_col and row.get(amt_col):
                    val = Decimal(row[amt_col].replace("$", "").replace(",", "").strip())
                    if val > 0:
                        is_deposit = True
                        amt = val
                    else:
                        is_deposit = False
                        amt = abs(val)
                elif debit_col and credit_col:
                    deb_val = row.get(debit_col, "").replace("$", "").replace(",", "").strip()
                    cred_val = row.get(credit_col, "").replace("$", "").replace(",", "").strip()
                    if cred_val and Decimal(cred_val) > 0:
                        is_deposit = True
                        amt = Decimal(cred_val)
                    elif deb_val and Decimal(deb_val) > 0:
                        is_deposit = False
                        amt = Decimal(deb_val)

                if amt == 0:
                    continue

                offset_acc = self.guess_account(desc, is_deposit)
                lines: List[EntryLine] = []

                if is_deposit:
                    # Debit Cash, Credit Revenue/Source
                    lines.append(EntryLine(account=cash_acc, amount=amt, is_debit=True, memo=desc))
                    lines.append(EntryLine(account=offset_acc, amount=amt, is_debit=False, memo=desc))
                else:
                    # Debit Expense/Target, Credit Cash
                    lines.append(EntryLine(account=offset_acc, amount=amt, is_debit=True, memo=desc))
                    lines.append(EntryLine(account=cash_acc, amount=amt, is_debit=False, memo=desc))

                tx_id = f"imp-{tx_date.strftime('%Y%m%d')}-{idx:03d}"
                tx = Transaction(
                    id=tx_id,
                    date=tx_date,
                    description=desc,
                    lines=lines,
                    reference=f"Imported from {csv_path.name}",
                    tags=["imported"],
                )
                transactions.append(tx)

        return transactions

    def _parse_date(self, date_str: str) -> Optional[date]:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
