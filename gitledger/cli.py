"""
Command-line interface for git-ledger.
"""

from __future__ import annotations
import argparse
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
import sys
from typing import Optional

# Allow running directly as a script or via package
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from gitledger.chart import ChartOfAccounts
    from gitledger.ledger import Ledger
    from gitledger.models import AccountType, EntryLine, Transaction
    from gitledger.reports import ReportGenerator
    from gitledger.importer import CSVBankImporter
    from gitledger.hooks import install_hook
else:
    from .chart import ChartOfAccounts
    from .ledger import Ledger
    from .models import AccountType, EntryLine, Transaction
    from .reports import ReportGenerator
    from .importer import CSVBankImporter
    from .hooks import install_hook


def parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def cmd_init(args):
    target_dir = Path(args.path).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    journal_dir = target_dir / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)

    accounts_file = target_dir / "accounts.yaml"
    if not accounts_file.exists():
        coa = ChartOfAccounts.default_nonprofit()
        coa.save_to_yaml(accounts_file)
        print(f"Created standard Chart of Accounts at {accounts_file}")
    else:
        print(f"Chart of Accounts already exists at {accounts_file}")

    sample_journal = journal_dir / f"{datetime.now().year}.yaml"
    if not sample_journal.exists() and not list(journal_dir.glob("*.yaml")):
        with open(sample_journal, "w", encoding="utf-8") as f:
            f.write("# Journal entries for " + str(datetime.now().year) + "\n[]\n")
        print(f"Created journal directory at {journal_dir}")

    print(f"git-ledger initialized successfully in {target_dir}")


def cmd_check(args):
    target_dir = Path(args.path).resolve()
    ledger = Ledger.load(target_dir)
    errors = ledger.validate()

    if errors:
        print(f"FAILED: Found {len(errors)} error(s) in {target_dir}:", file=sys.stderr)
        for err in errors:
            print(f"  [X] {err}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"OK: All {len(ledger.transactions)} transactions are balanced and valid in {target_dir}.")


def cmd_balance(args):
    target_dir = Path(args.path).resolve()
    ledger = Ledger.load(target_dir)
    errors = ledger.validate()
    if errors and args.strict:
        print("Cannot generate report: ledger has validation errors.", file=sys.stderr)
        sys.exit(1)

    as_of = parse_date(args.as_of)
    rep = ReportGenerator(ledger)
    print(rep.trial_balance(as_of_date=as_of, as_markdown=args.md))


def cmd_income(args):
    target_dir = Path(args.path).resolve()
    ledger = Ledger.load(target_dir)
    rep = ReportGenerator(ledger)
    start_d = parse_date(args.from_date)
    end_d = parse_date(args.to_date)
    print(rep.income_statement(start_date=start_d, end_date=end_d, as_markdown=args.md))


def cmd_balance_sheet(args):
    target_dir = Path(args.path).resolve()
    ledger = Ledger.load(target_dir)
    rep = ReportGenerator(ledger)
    as_of = parse_date(args.as_of)
    print(rep.balance_sheet(as_of_date=as_of, as_markdown=args.md))


def cmd_record(args):
    target_dir = Path(args.path).resolve()
    ledger = Ledger.load(target_dir)

    tx_date = parse_date(args.date) or date.today()
    tx_id = args.id or f"tx-{tx_date.strftime('%Y%m%d')}-{len(ledger.transactions) + 1:03d}"
    description = args.description

    # Simple two-legged entry: debit account, credit account, amount
    if args.debit_account and args.credit_account and args.amount:
        amt = Decimal(str(args.amount))
        lines = [
            EntryLine(account=args.debit_account, amount=amt, is_debit=True, memo=args.memo or ""),
            EntryLine(account=args.credit_account, amount=amt, is_debit=False, memo=args.memo or ""),
        ]
        tx = Transaction(
            id=tx_id,
            date=tx_date,
            description=description,
            lines=lines,
            reference=args.reference or "",
        )
        ledger.add_transaction(tx)
        print(f"Successfully recorded transaction {tx.id}: {tx.description} (${amt:,.2f})")
    else:
        print("Error: For automated record, specify --debit-account, --credit-account, --amount, and --description.", file=sys.stderr)
        sys.exit(1)


def cmd_import(args):
    target_dir = Path(args.path).resolve()
    ledger = Ledger.load(target_dir)
    importer = CSVBankImporter(default_cash_account=args.cash_account)

    csv_path = Path(args.csv_file).resolve()
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    imported_txs = importer.parse_csv(csv_path, cash_account=args.cash_account)
    print(f"Parsed {len(imported_txs)} transactions from {csv_path.name}")

    if args.dry_run:
        for tx in imported_txs:
            print(f"  [{tx.date}] {tx.description[:40]:<40} | ${tx.lines[0].amount:,.2f}")
        print("Dry run complete. Use without --dry-run to commit to ledger.")
        return

    for tx in imported_txs:
        ledger.add_transaction(tx)
    print(f"Successfully wrote {len(imported_txs)} transactions to ledger journal.")


def cmd_hook(args):
    repo_root = Path(args.path).resolve()
    success, msg = install_hook(repo_root)
    if success:
        print(msg)
    else:
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="git-ledger",
        description="Git-native plain-text accounting package for open communities and micro-organizations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new ledger directory")
    p_init.add_argument("path", nargs="?", default=".", help="Directory path to initialize (default: current directory)")
    p_init.set_defaults(func=cmd_init)

    # check
    p_check = subparsers.add_parser("check", help="Verify double-entry balance and accounts")
    p_check.add_argument("path", nargs="?", default=".", help="Ledger directory path")
    p_check.set_defaults(func=cmd_check)

    # balance / trial-balance
    p_bal = subparsers.add_parser("balance", help="Display Trial Balance")
    p_bal.add_argument("path", nargs="?", default=".", help="Ledger directory path")
    p_bal.add_argument("--as-of", dest="as_of", help="As of date (YYYY-MM-DD)")
    p_bal.add_argument("--md", action="store_true", help="Output in Markdown format")
    p_bal.add_argument("--strict", action="store_true", help="Fail if any unbalanced transaction exists")
    p_bal.set_defaults(func=cmd_balance)

    # income
    p_inc = subparsers.add_parser("income", help="Generate Income Statement (Profit & Loss)")
    p_inc.add_argument("path", nargs="?", default=".", help="Ledger directory path")
    p_inc.add_argument("--from", dest="from_date", help="Start date (YYYY-MM-DD)")
    p_inc.add_argument("--to", dest="to_date", help="End date (YYYY-MM-DD)")
    p_inc.add_argument("--md", action="store_true", help="Output in Markdown format")
    p_inc.set_defaults(func=cmd_income)

    # balance-sheet
    p_bs = subparsers.add_parser("balance-sheet", help="Generate Balance Sheet")
    p_bs.add_argument("path", nargs="?", default=".", help="Ledger directory path")
    p_bs.add_argument("--as-of", dest="as_of", help="As of date (YYYY-MM-DD)")
    p_bs.add_argument("--md", action="store_true", help="Output in Markdown format")
    p_bs.set_defaults(func=cmd_balance_sheet)

    # record
    p_rec = subparsers.add_parser("record", help="Record a new transaction")
    p_rec.add_argument("path", nargs="?", default=".", help="Ledger directory path")
    p_rec.add_argument("--id", dest="id", help="Transaction ID")
    p_rec.add_argument("--date", dest="date", help="Transaction date (YYYY-MM-DD, default today)")
    p_rec.add_argument("--desc", dest="description", required=True, help="Transaction description")
    p_rec.add_argument("--debit", dest="debit_account", required=True, help="Debit account code")
    p_rec.add_argument("--credit", dest="credit_account", required=True, help="Credit account code")
    p_rec.add_argument("--amount", dest="amount", required=True, type=float, help="Transaction amount")
    p_rec.add_argument("--memo", dest="memo", help="Optional memo")
    p_rec.add_argument("--ref", dest="reference", help="Reference / check number")
    p_rec.set_defaults(func=cmd_record)

    # import
    p_imp = subparsers.add_parser("import", help="Import bank CSV statement")
    p_imp.add_argument("csv_file", help="Path to bank CSV file")
    p_imp.add_argument("path", nargs="?", default=".", help="Ledger directory path")
    p_imp.add_argument("--cash-account", default="1010", help="Cash account code (default: 1010)")
    p_imp.add_argument("--dry-run", action="store_true", help="Preview without writing")
    p_imp.set_defaults(func=cmd_import)

    # hook
    p_hk = subparsers.add_parser("hook", help="Git hooks management")
    p_hk_sub = p_hk.add_subparsers(dest="hook_action", required=True)
    p_hk_inst = p_hk_sub.add_parser("install", help="Install pre-commit hook")
    p_hk_inst.add_argument("path", nargs="?", default=".", help="Repository root path")
    p_hk_inst.set_defaults(func=cmd_hook)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
