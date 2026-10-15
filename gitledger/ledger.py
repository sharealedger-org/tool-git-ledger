"""
Ledger engine and journal storage.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Set, Tuple

from .models import Account, AccountType, EntryLine, Transaction
from .chart import ChartOfAccounts
from .io import load_data_file, save_data_file

# Fraction of available memory at which journal files trigger auto-persist.
DEFAULT_PERSIST_THRESHOLD = 0.10  # 10%


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
    def __init__(self, chart: ChartOfAccounts, root_dir: Optional[Path] = None, entity: Optional[str] = None):
        self.chart = chart
        self.root_dir = root_dir or Path.cwd()
        self.entity = entity  # entity this ledger represents, e.g. "sharealedger-llc"
        self.transactions: List[Transaction] = []

    @classmethod
    def load(cls, ledger_dir: Path, entity: Optional[str] = None) -> "Ledger":
        accounts_file = ledger_dir / "accounts.yaml"
        if not accounts_file.exists():
            accounts_file = ledger_dir / "accounts.json"

        if accounts_file.exists():
            chart = ChartOfAccounts.load_from_yaml(accounts_file)
        else:
            chart = ChartOfAccounts.default_nonprofit()

        # Infer entity name from directory name if not supplied
        resolved_entity = entity or ledger_dir.name

        ledger = cls(chart=chart, root_dir=ledger_dir, entity=resolved_entity)
        journal_dir = ledger_dir / "journal"
        if journal_dir.exists():
            for yaml_file in sorted(journal_dir.glob("*.yaml")):
                ledger.load_journal_file(yaml_file)
            for yml_file in sorted(journal_dir.glob("*.yml")):
                ledger.load_journal_file(yml_file)
            for json_file in sorted(journal_dir.glob("*.json")):
                ledger.load_journal_file(json_file)

        return ledger

    @classmethod
    def load_consolidated(cls, books_dir: Path) -> "Ledger":
        """Load all entity sub-ledgers under books_dir into a single consolidated ledger."""
        consolidated = cls(chart=ChartOfAccounts.default_nonprofit(), root_dir=books_dir, entity="consolidated")
        for entity_dir in sorted(books_dir.iterdir()):
            if not entity_dir.is_dir() or entity_dir.name.startswith("."):
                continue
            entity_ledger = cls.load(entity_dir)
            # Tag all transactions with their entity if not already set
            for tx in entity_ledger.transactions:
                if tx.entity is None:
                    tx.entity = entity_ledger.entity
            consolidated.transactions.extend(entity_ledger.transactions)
            # Merge charts
            for code, acc in entity_ledger.chart.accounts.items():
                if code not in consolidated.chart.accounts:
                    consolidated.chart.add_account(acc)
        return consolidated

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
                entity=item.get("entity") or self.entity,
                source_event_id=item.get("source_event_id"),
                shared_event_id=item.get("shared_event_id"),
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
        entity: Optional[str] = None,
    ) -> Dict[str, AccountBalance]:
        """Calculate balances, optionally filtered to a specific entity."""
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
            if entity and tx.entity and tx.entity != entity:
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

    # ------------------------------------------------------------------
    # Auto-persist helpers
    # ------------------------------------------------------------------

    @staticmethod
    def journal_size_bytes(ledger_dir: Path) -> int:
        """Return total byte size of all journal files under ledger_dir/journal/."""
        journal_dir = ledger_dir / "journal"
        if not journal_dir.exists():
            return 0
        return sum(
            f.stat().st_size
            for f in journal_dir.iterdir()
            if f.is_file() and f.suffix in (".yaml", ".yml", ".json")
        )

    @staticmethod
    def available_memory_bytes() -> int:
        """Return available memory in bytes using only the standard library."""
        try:
            # Linux / macOS
            import resource
            soft, _ = resource.getrlimit(resource.RLIMIT_AS)
            if soft > 0:
                return soft
        except (ImportError, AttributeError, ValueError):
            pass

        try:
            # macOS: vm_stat
            import subprocess as _sp
            result = _sp.run(["vm_stat"], capture_output=True, text=True, timeout=5)
            free_pages = 0
            for line in result.stdout.splitlines():
                if "Pages free" in line or "Pages inactive" in line:
                    val = line.split(":")[-1].strip().rstrip(".")
                    try:
                        free_pages += int(val)
                    except ValueError:
                        pass
            if free_pages:
                return free_pages * 4096  # macOS page size
        except Exception:
            pass

        try:
            # Linux: /proc/meminfo
            mem_info = Path("/proc/meminfo").read_text()
            for line in mem_info.splitlines():
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    return kb * 1024
        except (FileNotFoundError, ValueError, IndexError):
            pass

        # Conservative fallback: 512 MB
        return 512 * 1024 * 1024

    @staticmethod
    def _get_git_sha(ledger_dir: Path) -> Optional[str]:
        """Return the current HEAD SHA of the git repo containing ledger_dir."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(ledger_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def persist_ledger(self, git_sha: Optional[str] = None) -> Path:
        """
        Write a ledger-cache.yaml snapshot of all computed account balances to
        root_dir/ledger-cache.yaml.  The file records the Git SHA of the journal
        commit it was derived from, providing a provenance link.

        This does NOT replace the ephemeral re-derive model; it is a point-in-time
        snapshot written when journal files grow large, consistent with the session
        log design decision.

        Returns the path of the written cache file.
        """
        balances = self.get_balances()

        snapshot: Dict = {
            "meta": {
                "generated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "entity": self.entity,
                "transaction_count": len(self.transactions),
                "git_sha": git_sha or self._get_git_sha(self.root_dir),
            },
            "balances": [
                {
                    "code": code,
                    "name": bal.account.name,
                    "type": bal.account.type.value,
                    "debit": float(bal.total_debits),
                    "credit": float(bal.total_credits),
                    "net": float(bal.net_balance),
                }
                for code, bal in sorted(balances.items())
                if bal.total_debits or bal.total_credits
            ],
        }

        cache_path = self.root_dir / "ledger-cache.yaml"
        save_data_file(snapshot, cache_path)
        return cache_path

    def check_and_persist(
        self,
        threshold_pct: float = DEFAULT_PERSIST_THRESHOLD,
        git_sha: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Measure journal file size against available memory.  If the journals
        exceed threshold_pct of available memory, call persist_ledger() and
        return the cache path.  Otherwise return None.
        """
        journal_bytes = self.journal_size_bytes(self.root_dir)
        available = self.available_memory_bytes()
        if journal_bytes >= available * threshold_pct:
            return self.persist_ledger(git_sha=git_sha)
        return None

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
        if tx.entity:
            tx_dict["entity"] = tx.entity
        if tx.source_event_id:
            tx_dict["source_event_id"] = tx.source_event_id
        if tx.shared_event_id:
            tx_dict["shared_event_id"] = tx.shared_event_id

        existing_data = []
        if target_path.exists():
            existing_data = load_data_file(target_path) or []

        existing_data.append(tx_dict)
        save_data_file(existing_data, target_path)
