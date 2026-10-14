"""
Data models for git-ledger.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional


class AccountType(str, Enum):
    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    REVENUE = "Revenue"
    EXPENSE = "Expense"

    @property
    def normal_balance(self) -> str:
        """Returns 'debit' or 'credit' for normal balance."""
        if self in (AccountType.ASSET, AccountType.EXPENSE):
            return "debit"
        return "credit"


@dataclass
class Account:
    code: str
    name: str
    type: AccountType
    description: str = ""
    parent: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = AccountType(self.type)


@dataclass
class EntryLine:
    account: str
    amount: Decimal  # Positive decimal
    is_debit: bool
    memo: str = ""

    @property
    def debit(self) -> Decimal:
        return self.amount if self.is_debit else Decimal("0.00")

    @property
    def credit(self) -> Decimal:
        return Decimal("0.00") if self.is_debit else self.amount


@dataclass
class Transaction:
    id: str
    date: date
    description: str
    lines: List[EntryLine] = field(default_factory=list)
    reference: str = ""
    tags: List[str] = field(default_factory=list)
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def total_debits(self) -> Decimal:
        return sum((line.debit for line in self.lines), Decimal("0.00"))

    @property
    def total_credits(self) -> Decimal:
        return sum((line.credit for line in self.lines), Decimal("0.00"))

    @property
    def is_balanced(self) -> bool:
        return self.total_debits == self.total_credits

    @property
    def imbalance(self) -> Decimal:
        return self.total_debits - self.total_credits
