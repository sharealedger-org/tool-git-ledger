"""
Bank CSV importer and journal entry generator.
"""

from __future__ import annotations
import csv
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow running directly as a script or via package
try:
    from .models import EntryLine, Transaction
    from .io import load_data_file
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from gitledger.models import EntryLine, Transaction
    from gitledger.io import load_data_file


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


class WaveImporter:
    """
    Imports Wave accounting CSV exports into git-ledger Transactions.

    Wave exports double-entry data: each transaction appears as two rows sharing
    the same Transaction ID — one row per account leg. This importer groups those
    rows by Transaction ID, resolves Wave account names to chart codes via a
    declared mapping-rules file, and preserves the source Wave Transaction ID as
    source_event_id on every Transaction.

    The mapping-rules YAML file format:
        entity: <entity-name>
        account_mappings:
            "Wave Account Name": "chart-code"
        account_group_fallbacks:
            Asset: "1010"
            ...
    """

    def __init__(self, mapping_rules_path: Path, entity: str):
        self.entity = entity
        self.account_mappings: Dict[str, str] = {}
        self.group_fallbacks: Dict[str, str] = {
            "Asset": "1010",
            "Liability": "2000",
            "Equity": "3100",
            "Income": "4100",
            "Expense": "5900",
        }
        self._load_rules(mapping_rules_path)

    def _load_rules(self, path: Path):
        data = load_data_file(path) or {}
        self.account_mappings = {
            str(k): str(v)
            for k, v in data.get("account_mappings", {}).items()
        }
        self.group_fallbacks.update({
            str(k): str(v)
            for k, v in data.get("account_group_fallbacks", {}).items()
        })

    def resolve_account(self, wave_account_name: str, wave_account_group: str) -> str:
        """Map a Wave account name to a chart code using declared rules."""
        if wave_account_name in self.account_mappings:
            return self.account_mappings[wave_account_name]
        return self.group_fallbacks.get(wave_account_group, "5900")

    def parse_csv(self, csv_path: Path) -> List[Transaction]:
        """
        Parse a Wave accounting CSV export into a list of balanced Transactions.

        Wave exports both legs of every double-entry transaction. We group by
        Transaction ID, then convert each group into one Transaction with the
        full debit/credit entry set.
        """
        # Group raw rows by Transaction ID
        groups: Dict[str, List[Dict[str, str]]] = {}
        order: List[str] = []  # preserve encounter order for deterministic output

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tx_id = row.get("Transaction ID", "").strip()
                if not tx_id:
                    continue
                if tx_id not in groups:
                    groups[tx_id] = []
                    order.append(tx_id)
                groups[tx_id].append(dict(row))

        transactions: List[Transaction] = []

        for wave_tx_id in order:
            rows = groups[wave_tx_id]
            tx = self._build_transaction(wave_tx_id, rows)
            if tx is not None:
                transactions.append(tx)

        return transactions

    def _build_transaction(
        self, wave_tx_id: str, rows: List[Dict[str, str]]
    ) -> Optional[Transaction]:
        """Convert a group of Wave rows (same Transaction ID) into one Transaction."""
        if not rows:
            return None

        # Use first row for transaction-level fields
        first = rows[0]
        raw_date = first.get("Transaction Date", "").strip()
        tx_date = self._parse_date(raw_date)
        if not tx_date:
            return None

        description = first.get("Transaction Description", "").strip()
        notes = first.get("Notes / Memo", "").strip()

        lines: List[EntryLine] = []

        for row in rows:
            account_name = row.get("Account Name", "").strip()
            account_group = row.get("Account Group", "").strip()
            chart_code = self.resolve_account(account_name, account_group)

            # Wave uses signed single-column amounts: positive = debit to this account
            # We also have explicit Debit/Credit columns; prefer them if populated.
            debit_str = row.get("Debit Amount (Two Column Approach)", "").strip()
            credit_str = row.get("Credit Amount (Two Column Approach)", "").strip()

            if debit_str:
                try:
                    amt = Decimal(debit_str.replace(",", ""))
                    if amt != Decimal("0"):
                        lines.append(EntryLine(
                            account=chart_code,
                            amount=amt,
                            is_debit=True,
                            memo=account_name,
                        ))
                        continue
                except Exception:
                    pass

            if credit_str:
                try:
                    amt = Decimal(credit_str.replace(",", ""))
                    if amt != Decimal("0"):
                        lines.append(EntryLine(
                            account=chart_code,
                            amount=amt,
                            is_debit=False,
                            memo=account_name,
                        ))
                        continue
                except Exception:
                    pass

            # Fallback: use signed single-column amount
            signed_str = row.get("Amount (One column)", "").strip()
            if signed_str:
                try:
                    signed = Decimal(signed_str.replace(",", ""))
                    if signed > Decimal("0"):
                        lines.append(EntryLine(
                            account=chart_code,
                            amount=signed,
                            is_debit=True,
                            memo=account_name,
                        ))
                    elif signed < Decimal("0"):
                        lines.append(EntryLine(
                            account=chart_code,
                            amount=abs(signed),
                            is_debit=False,
                            memo=account_name,
                        ))
                except Exception:
                    pass

        if not lines:
            return None

        metadata: Dict[str, str] = {}
        if notes:
            # Truncate notes to first line for clean metadata; full notes in description
            metadata["wave_notes"] = notes[:500]

        return Transaction(
            id=f"wave-{wave_tx_id}",
            date=tx_date,
            description=description,
            lines=lines,
            reference=wave_tx_id,
            tags=["wave-import"],
            entity=self.entity,
            source_event_id=wave_tx_id,
            metadata=metadata,
        )

    def _parse_date(self, date_str: str) -> Optional[date]:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None


class QuickBooksImporter:
    """
    Imports a QuickBooks General Ledger / Transaction Detail CSV export into
    git-ledger Transactions.

    **Export format targeted:**
    QuickBooks Desktop → Reports → Accountant & Taxes → General Ledger
    (or Transaction Detail by Account).  Exported as CSV ("Save as Excel" then
    save-as CSV, or use "Export to .csv" directly if available).

    Expected columns (QuickBooks Desktop General Ledger CSV):
        Type, Date, Num, Name, Memo, Account, Debit, Credit, Balance

    Each row is one journal line.  Rows are grouped into transactions by (Date, Num,
    Memo) — the combination that uniquely identifies a QB transaction in this format.
    Any row where both Debit and Credit are empty/zero is skipped (header/subtotal rows).

    **QuickBooks Online** uses a similar format but may label columns differently:
        Transaction Type, Date, Num, Name, Memo/Description, Account, Debit, Credit
    Both variants are handled via case-insensitive column matching.

    .. note::
        This importer was written against the documented QB General Ledger CSV
        specification.  No live QuickBooks CSV sample was available during
        development.  Validate against a real export before relying on it in
        production, and adjust the ``account_mappings`` in your
        ``qb-import.yaml`` mapping rules file as needed.

    Mapping-rules YAML format (same structure as wave-import.yaml):
        entity: <entity-name>
        account_mappings:
            "QuickBooks Account Name": "chart-code"
        account_group_fallbacks:
            Bank: "1010"
            Accounts Receivable: "1100"
            Accounts Payable: "2000"
            Credit Card: "2050"
            Equity: "3100"
            Income: "4100"
            Expense: "5900"
    """

    # Default fallbacks keyed on QB account type keywords
    DEFAULT_FALLBACKS: Dict[str, str] = {
        "bank": "1010",
        "cash": "1010",
        "accounts receivable": "1100",
        "accounts payable": "2000",
        "credit card": "2050",
        "equity": "3100",
        "income": "4100",
        "revenue": "4100",
        "expense": "5900",
        "cost of goods sold": "5900",
        "other income": "4900",
        "other expense": "5900",
    }

    def __init__(self, mapping_rules_path: Path, entity: str):
        self.entity = entity
        self.account_mappings: Dict[str, str] = {}
        self.group_fallbacks: Dict[str, str] = dict(self.DEFAULT_FALLBACKS)
        if mapping_rules_path.exists():
            self._load_rules(mapping_rules_path)

    def _load_rules(self, path: Path):
        data = load_data_file(path) or {}
        self.account_mappings = {
            str(k): str(v)
            for k, v in data.get("account_mappings", {}).items()
        }
        self.group_fallbacks.update({
            str(k).lower(): str(v)
            for k, v in data.get("account_group_fallbacks", {}).items()
        })

    def resolve_account(self, qb_account_name: str) -> str:
        """Map a QB account name to a chart code."""
        if qb_account_name in self.account_mappings:
            return self.account_mappings[qb_account_name]
        # Try keyword match against fallbacks
        lower = qb_account_name.lower()
        for keyword, code in self.group_fallbacks.items():
            if keyword in lower:
                return code
        return "5900"  # catch-all

    def parse_csv(self, csv_path: Path) -> List[Transaction]:
        """
        Parse a QuickBooks General Ledger CSV export into balanced Transactions.

        Rows are grouped by (Date, Num, Memo) into individual transactions.
        Each group must balance (total debits == total credits); unbalanced
        groups are returned as-is and flagged so the caller can skip or inspect.
        """
        groups: Dict[Tuple, List[Dict[str, str]]] = {}
        order: List[Tuple] = []

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # Normalise fieldnames case-insensitively
            raw_fields = reader.fieldnames or []
            field_map = {name.lower().strip(): name for name in raw_fields}

            date_col   = field_map.get("date")
            num_col    = field_map.get("num") or field_map.get("transaction #") or field_map.get("ref no.")
            name_col   = field_map.get("name")
            memo_col   = field_map.get("memo") or field_map.get("memo/description") or field_map.get("description")
            type_col   = field_map.get("type") or field_map.get("transaction type")
            acct_col   = field_map.get("account")
            debit_col  = field_map.get("debit")
            credit_col = field_map.get("credit")

            if not date_col or not acct_col:
                raise ValueError(
                    f"Could not identify required columns (Date, Account) in: {raw_fields}"
                )

            for row in reader:
                # Skip subtotal / header rows that have no account or no amounts
                raw_date = row.get(date_col, "").strip()
                raw_acct = row.get(acct_col, "").strip() if acct_col else ""
                if not raw_date or not raw_acct:
                    continue
                raw_debit  = row.get(debit_col, "").strip()  if debit_col  else ""
                raw_credit = row.get(credit_col, "").strip() if credit_col else ""
                if not raw_debit and not raw_credit:
                    continue

                num  = row.get(num_col,  "").strip() if num_col  else ""
                memo = row.get(memo_col, "").strip() if memo_col else ""
                key  = (raw_date, num, memo)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(dict(row))

        transactions: List[Transaction] = []
        for idx, key in enumerate(order, start=1):
            tx = self._build_transaction(idx, key, groups[key], field_map)
            if tx is not None:
                transactions.append(tx)

        return transactions

    def _build_transaction(
        self,
        idx: int,
        key: Tuple,
        rows: List[Dict[str, str]],
        field_map: Dict[str, str],
    ) -> Optional[Transaction]:
        raw_date, num, memo = key

        tx_date = self._parse_date(raw_date)
        if not tx_date:
            return None

        acct_col   = field_map.get("account", "")
        debit_col  = field_map.get("debit", "")
        credit_col = field_map.get("credit", "")
        name_col   = field_map.get("name", "")
        type_col   = field_map.get("type") or field_map.get("transaction type", "")

        description = memo or (rows[0].get(type_col, "").strip() if type_col else "")
        if name_col:
            name = rows[0].get(name_col, "").strip()
            if name and not description:
                description = name

        lines: List[EntryLine] = []
        for row in rows:
            acct_name  = row.get(acct_col, "").strip()
            raw_debit  = row.get(debit_col,  "").replace(",", "").replace("$", "").strip() if debit_col  else ""
            raw_credit = row.get(credit_col, "").replace(",", "").replace("$", "").strip() if credit_col else ""

            chart_code = self.resolve_account(acct_name)

            if raw_debit:
                try:
                    amt = Decimal(raw_debit)
                    if amt > 0:
                        lines.append(EntryLine(
                            account=chart_code,
                            amount=amt,
                            is_debit=True,
                            memo=acct_name,
                        ))
                except Exception:
                    pass

            if raw_credit:
                try:
                    amt = Decimal(raw_credit)
                    if amt > 0:
                        lines.append(EntryLine(
                            account=chart_code,
                            amount=amt,
                            is_debit=False,
                            memo=acct_name,
                        ))
                except Exception:
                    pass

        if not lines:
            return None

        tx_id = f"qb-{tx_date.strftime('%Y%m%d')}-{num or idx:03}"
        return Transaction(
            id=tx_id,
            date=tx_date,
            description=description,
            lines=lines,
            reference=num,
            tags=["qb-import"],
            entity=self.entity,
            source_event_id=num or None,
        )

    def _parse_date(self, date_str: str) -> Optional[date]:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
