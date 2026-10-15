"""
Chart of Accounts management.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional

from .models import Account, AccountType
from .io import load_data_file, save_data_file


# Shared base accounts used by both entities
_BASE_ACCOUNTS = [
    # Assets (1000s)
    {"code": "1000", "name": "Cash and Cash Equivalents", "type": "Asset", "description": "Primary Operating Bank Account"},
    {"code": "1010", "name": "Checking Account", "type": "Asset", "parent": "1000"},
    {"code": "1020", "name": "Savings / Reserve Account", "type": "Asset", "parent": "1000"},
    {"code": "1050", "name": "Transfer Clearing", "type": "Asset"},
    {"code": "1200", "name": "Accounts Receivable", "type": "Asset"},
    {"code": "1300", "name": "Due from Sharealedger NFP", "type": "Asset", "description": "Inter-entity receivable (LLC books)"},
    {"code": "1400", "name": "Prepaid Expenses", "type": "Asset"},

    # Liabilities (2000s)
    {"code": "2000", "name": "Accounts Payable", "type": "Liability"},
    {"code": "2050", "name": "Credit Card Payable", "type": "Liability"},
    {"code": "2200", "name": "Accrued Expenses", "type": "Liability"},
    {"code": "2300", "name": "Due to Sharealedger LLC", "type": "Liability", "description": "Inter-entity payable (NFP books)"},
    {"code": "2500", "name": "Deferred Revenue", "type": "Liability"},

    # Expenses (5000s)
    {"code": "5000", "name": "Web Hosting & Infrastructure", "type": "Expense"},
    {"code": "5010", "name": "Domain Names & DNS", "type": "Expense"},
    {"code": "5020", "name": "Software & Subscriptions", "type": "Expense"},
    {"code": "5100", "name": "Legal & Professional Fees", "type": "Expense"},
    {"code": "5200", "name": "Filing & Regulatory Fees", "type": "Expense"},
    {"code": "5300", "name": "Educational Video & Media Production", "type": "Expense"},
    {"code": "5400", "name": "Bank & Merchant Processing Fees", "type": "Expense"},
    {"code": "5500", "name": "Office Supplies & Software", "type": "Expense"},
    {"code": "5600", "name": "Travel & Meeting Expenses", "type": "Expense"},
    {"code": "5900", "name": "Miscellaneous Expense", "type": "Expense"},
]

# LLC-specific accounts (member equity structure)
DEFAULT_LLC_ACCOUNTS = _BASE_ACCOUNTS + [
    # Equity — LLC uses member contribution/drawing structure
    {"code": "3000", "name": "Opening Balance Equity", "type": "Equity"},
    {"code": "3100", "name": "Member Contributions", "type": "Equity", "description": "Owner Investment / Drawings"},
    {"code": "3200", "name": "Retained Earnings", "type": "Equity"},

    # Revenue — LLC primarily funds itself via member contributions; record any misc income here
    {"code": "4900", "name": "Interest & Other Income", "type": "Revenue"},
]

# NFP-specific accounts (net assets structure, 501(c)(6))
DEFAULT_NFP_ACCOUNTS = _BASE_ACCOUNTS + [
    # Equity / Net Assets
    {"code": "3000", "name": "Opening Balance Equity", "type": "Equity"},
    {"code": "3100", "name": "Unrestricted Net Assets", "type": "Equity"},
    {"code": "3200", "name": "Temporarily Restricted Net Assets", "type": "Equity"},

    # Revenue
    {"code": "4000", "name": "Membership Dues", "type": "Revenue"},
    {"code": "4100", "name": "Contributions & Donations", "type": "Revenue"},
    {"code": "4200", "name": "Grants & Sponsorships", "type": "Revenue"},
    {"code": "4300", "name": "Educational Program Revenue", "type": "Revenue"},
    {"code": "4900", "name": "Interest & Other Income", "type": "Revenue"},
]

# Backward-compatible alias — defaults to NFP structure
DEFAULT_NONPROFIT_ACCOUNTS = DEFAULT_NFP_ACCOUNTS


class ChartOfAccounts:
    def __init__(self, accounts: Optional[Dict[str, Account]] = None):
        self.accounts: Dict[str, Account] = accounts or {}

    def add_account(self, account: Account):
        self.accounts[account.code] = account

    def get_account(self, code_or_name: str) -> Optional[Account]:
        if code_or_name in self.accounts:
            return self.accounts[code_or_name]
        for acc in self.accounts.values():
            if acc.name.lower() == code_or_name.lower():
                return acc
        return None

    def list_by_type(self, acc_type: AccountType) -> List[Account]:
        return [acc for acc in self.accounts.values() if acc.type == acc_type]

    @classmethod
    def load_from_yaml(cls, path: Path) -> "ChartOfAccounts":
        data = load_data_file(path) or []
        coa = cls()
        for item in data:
            acc = Account(
                code=str(item["code"]),
                name=str(item["name"]),
                type=AccountType(item["type"]),
                description=str(item.get("description", "")),
                parent=str(item.get("parent", "")) if item.get("parent") else None,
            )
            coa.add_account(acc)
        return coa

    def save_to_yaml(self, path: Path):
        data = [
            {
                "code": acc.code,
                "name": acc.name,
                "type": acc.type.value,
                **({"description": acc.description} if acc.description else {}),
                **({"parent": acc.parent} if acc.parent else {}),
            }
            for acc in sorted(self.accounts.values(), key=lambda a: a.code)
        ]
        save_data_file(data, path)

    @classmethod
    def _from_list(cls, account_list: list) -> "ChartOfAccounts":
        coa = cls()
        for item in account_list:
            acc = Account(
                code=item["code"],
                name=item["name"],
                type=AccountType(item["type"]),
                description=item.get("description", ""),
                parent=item.get("parent"),
            )
            coa.add_account(acc)
        return coa

    @classmethod
    def default_nonprofit(cls) -> "ChartOfAccounts":
        return cls._from_list(DEFAULT_NFP_ACCOUNTS)

    @classmethod
    def default_llc(cls) -> "ChartOfAccounts":
        return cls._from_list(DEFAULT_LLC_ACCOUNTS)

    @classmethod
    def default_nfp(cls) -> "ChartOfAccounts":
        return cls._from_list(DEFAULT_NFP_ACCOUNTS)
