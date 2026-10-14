"""
Ledger engine and journal storage.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .models import Account, AccountType, EntryLine, Transaction
from .chart import ChartOfAccounts
from .io import load_data_file, save_data_file


@dataclass
class AccountBalance:
    account: Account
    total_debits: Decimal = Decimal("0.00")
    total_credits: Decimal = Decimal("0.00")

    @property
    def net_balance(self) -> Decimal:
        """Computes net balance adhering to normal debit/credit orientation."""
        if self.account.type in (AccountType.ASSET, AccountType.EXPENSE):
            return self.total_debits - self.total_credits
        return self.total_credits - self.total_debits


class Ledger:
    def __init__(self, chart: ChartOfAccounts, root_dir: Optional[Path] = None):
        self.chart = chart
        self.root_dir = root_dir or Path.cwd()
        self.transactions: List[Transaction] = []

    @classmethod
    def load(cls, ledger_dir: Path) -> "Ledger":
        accounts_file = ledger_dir / "accounts.yaml"
        if not accounts_file.exists():
            accounts_file = ledger_dir / "accounts.json"

        if accounts_file.exists():
            chart = ChartOfAccounts.load_from_yaml(accounts_file)
        else:
            chart = ChartOfAccounts.default_nonprofit()

        ledger = cls(chart=chart, root_dir=ledger_dir)
        journal_dir = ledger_dir / "journal"
        if journal_dir.exists():
            for yaml_file in sorted(journal_dir.glob("*.yaml")):
                ledger.load_journal_file(yaml_file)
            for yml_file in sorted(journal_dir.glob("*.yml")):
                ledger.load_journal_file(yml_file)
            for json_file in sorted(journal_dir.glob("*.json")):
                ledger.load_journal_file(json_file)

        return ledger

    def load_journal_file(self, file_path: Path):
        data = load_data_file(file_path) or []

        if not isinstance(data, list):
            return

        for idx, item in enumerate(data, start=1):
            tx_id = str(item.get("id", f"{file_path.stem}-{idx}"))
            raw_date = item.get("date")
            if isinstance(raw_date, str):
                tx_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            elif isinstance(raw_date, date):
                tx_date = raw_date
            elif isinstance(raw_date, datetime):
                tx_date = raw_date.date()
            else:
                continue

            description = str(item.get("description", ""))
            reference = str(item.get("reference", ""))
            tags = item.get("tags", [])

            lines: List[EntryLine] = []
            for entry in item.get("entries", []):
                acc_code = str(entry.get("account"))
                memo = str(entry.get("memo", ""))
                if "debit" in entry and entry["debit"] is not None:
                    amt = Decimal(str(entry["debit"]))
                    lines.append(EntryLine(account=acc_code, amount=amt, is_debit=True, memo=memo))
                elif "credit" in entry and entry["credit"] is not None:
                    amt = Decimal(str(entry["credit"]))
                    lines.append(EntryLine(account=acc_code, amount=amt, is_debit=False, memo=memo))
                elif "amount" in entry and entry["amount"] is not None:
                    amt = Decimal(str(entry["amount"]))
                    is_deb = entry.get("type", "debit").lower() == "debit"
                    lines.append(EntryLine(account=acc_code, amount=amt, is_debit=is_deb, memo=memo))

            tx = Transaction(
                id=tx_id,
                date=tx_date,
                description=description,
                lines=lines,
                reference=reference,
                tags=tags,
                source_file=str(file_path.name),
                source_line=idx,
                metadata=item.get("metadata", {}),
            )
            self.transactions.append(tx)

    def validate(self) -> List[str]:
        """Validates double-entry invariants and account validity."""
        errors: List[str] = []
        for tx in self.transactions:
            if not tx.is_balanced:
                errors.append(
                    f"Transaction {tx.id} on {tx.date} ('{tx.description}') is out of balance! "
                    f"Debits: {tx.total_debits:.2f}, Credits: {tx.total_credits:.2f}, Imbalance: {tx.imbalance:.2f} "
                    f"in {tx.source_file or 'unknown'}"
                )
            for line in tx.lines:
                if line.account not in self.chart.accounts:
                    errors.append(
                        f"Transaction {tx.id} references undefined account code '{line.account}' "
                        f"in {tx.source_file or 'unknown'}"
                    )
        return errors

    def get_balances(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        accounts: Optional[Set[str]] = None,
    ) -> Dict[str, AccountBalance]:
        balances: Dict[str, AccountBalance] = {
            code: AccountBalance(account=acc)
            for code, acc in self.chart.accounts.items()
            if accounts is None or code in accounts
        }

        for tx in self.transactions:
            if start_date and tx.date < start_date:
                continue
            if end_date and tx.date > end_date:
                continue

            for line in tx.lines:
                if accounts is not None and line.account not in accounts:
                    continue
                if line.account not in balances:
                    acc = self.chart.get_account(line.account)
                    if not acc:
                        acc = Account(code=line.account, name=f"Unknown Account ({line.account})", type=AccountType.EXPENSE)
                    balances[line.account] = AccountBalance(account=acc)

                bal = balances[line.account]
                if line.is_debit:
                    bal.total_debits += line.amount
                else:
                    bal.total_credits += line.amount

        return balances

    def add_transaction(self, tx: Transaction, file_path: Optional[Path] = None):
        if not tx.is_balanced:
            raise ValueError(f"Cannot record unbalanced transaction. Debits={tx.total_debits}, Credits={tx.total_credits}")
        
        self.transactions.append(tx)
        
        target_path = file_path
        if not target_path:
            journal_dir = self.root_dir / "journal"
            journal_dir.mkdir(parents=True, exist_ok=True)
            target_path = journal_dir / f"{tx.date.year}.yaml"

        entries_data = []
        for line in tx.lines:
            line_dict = {"account": line.account}
            if line.is_debit:
                line_dict["debit"] = float(line.amount)
            else:
                line_dict["credit"] = float(line.amount)
            if line.memo:
                line_dict["memo"] = line.memo
            entries_data.append(line_dict)

        tx_dict = {
            "id": tx.id,
            "date": tx.date.strftime("%Y-%m-%d"),
            "description": tx.description,
            "entries": entries_data,
        }
        if tx.reference:
            tx_dict["reference"] = tx.reference
        if tx.tags:
            tx_dict["tags"] = tx.tags
        if tx.metadata:
            tx_dict["metadata"] = tx.metadata

        existing_data = []
        if target_path.exists():
            existing_data = load_data_file(target_path) or []

        existing_data.append(tx_dict)
        save_data_file(existing_data, target_path)
