"""
Financial statement generation (Trial Balance, Income Statement, Balance Sheet).
"""

from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from .models import AccountType
from .ledger import Ledger, AccountBalance


class ReportGenerator:
    def __init__(self, ledger: Ledger):
        self.ledger = ledger

    def trial_balance(
        self,
        as_of_date: Optional[date] = None,
        as_markdown: bool = False,
        entity: Optional[str] = None,
    ) -> str:
        balances = self.ledger.get_balances(end_date=as_of_date, entity=entity)
        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")

        rows = []
        for code in sorted(balances.keys()):
            bal = balances[code]
            if bal.total_debits == 0 and bal.total_credits == 0:
                continue

            # Net position in normal orientation
            if bal.account.type in (AccountType.ASSET, AccountType.EXPENSE):
                net = bal.total_debits - bal.total_credits
                if net >= 0:
                    deb_val = net
                    cred_val = Decimal("0.00")
                else:
                    deb_val = Decimal("0.00")
                    cred_val = -net
            else:
                net = bal.total_credits - bal.total_debits
                if net >= 0:
                    deb_val = Decimal("0.00")
                    cred_val = net
                else:
                    deb_val = -net
                    cred_val = Decimal("0.00")

            total_debits += deb_val
            total_credits += cred_val
            rows.append((bal.account.code, bal.account.name, deb_val, cred_val))

        as_of_str = f"As of {as_of_date.strftime('%Y-%m-%d')}" if as_of_date else "All Dates"
        
        if as_markdown:
            lines = [
                f"# Trial Balance",
                f"*{as_of_str}*",
                "",
                "| Account | Name | Debit ($) | Credit ($) |",
                "| :--- | :--- | ---: | ---: |",
            ]
            for code, name, deb, cred in rows:
                lines.append(f"| {code} | {name} | {deb:,.2f} | {cred:,.2f} |")
            lines.append(f"| **TOTAL** | | **{total_debits:,.2f}** | **{total_credits:,.2f}** |")
            diff = total_debits - total_credits
            if diff != 0:
                lines.append(f"\n> **WARNING: Out of Balance by ${diff:,.2f}**")
            return "\n".join(lines)
        else:
            lines = [
                "=" * 70,
                f"TRIAL BALANCE — {as_of_str}",
                "=" * 70,
                f"{'Code':<6} {'Account Name':<34} {'Debit':>13} {'Credit':>13}",
                "-" * 70,
            ]
            for code, name, deb, cred in rows:
                lines.append(f"{code:<6} {name[:34]:<34} {deb:>13,.2f} {cred:>13,.2f}")
            lines.append("-" * 70)
            lines.append(f"{'TOTALS':<41} {total_debits:>13,.2f} {total_credits:>13,.2f}")
            lines.append("=" * 70)
            diff = total_debits - total_credits
            if diff != 0:
                lines.append(f"*** OUT OF BALANCE BY ${diff:,.2f} ***")
            return "\n".join(lines)

    def income_statement(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        as_markdown: bool = False,
        entity: Optional[str] = None,
    ) -> str:
        balances = self.ledger.get_balances(start_date=start_date, end_date=end_date, entity=entity)
        
        revenue_items = []
        expense_items = []
        total_revenue = Decimal("0.00")
        total_expenses = Decimal("0.00")

        for code in sorted(balances.keys()):
            bal = balances[code]
            if bal.account.type == AccountType.REVENUE:
                net = bal.total_credits - bal.total_debits
                if net != 0:
                    revenue_items.append((bal.account.code, bal.account.name, net))
                    total_revenue += net
            elif bal.account.type == AccountType.EXPENSE:
                net = bal.total_debits - bal.total_credits
                if net != 0:
                    expense_items.append((bal.account.code, bal.account.name, net))
                    total_expenses += net

        net_income = total_revenue - total_expenses
        period_str = f"{start_date or 'Beginning'} to {end_date or 'Present'}"

        if as_markdown:
            lines = [
                f"# Income Statement (Statement of Activities)",
                f"*{period_str}*",
                "",
                "### Revenue",
                "| Code | Account | Amount ($) |",
                "| :--- | :--- | ---: |",
            ]
            for code, name, amt in revenue_items:
                lines.append(f"| {code} | {name} | {amt:,.2f} |")
            lines.append(f"| | **Total Revenue** | **{total_revenue:,.2f}** |")
            lines.append("")
            lines.append("### Expenses")
            lines.append("| Code | Account | Amount ($) |")
            lines.append("| :--- | :--- | ---: |")
            for code, name, amt in expense_items:
                lines.append(f"| {code} | {name} | {amt:,.2f} |")
            lines.append(f"| | **Total Expenses** | **{total_expenses:,.2f}** |")
            lines.append("")
            lines.append(f"## **Net Surplus / (Deficit): ${net_income:,.2f}**")
            return "\n".join(lines)
        else:
            lines = [
                "=" * 60,
                f"INCOME STATEMENT — {period_str}",
                "=" * 60,
                "REVENUE",
                "-" * 60,
            ]
            for code, name, amt in revenue_items:
                lines.append(f"  {code:<6} {name:<36} {amt:>13,.2f}")
            lines.append(f"  {'TOTAL REVENUE':<43} {total_revenue:>13,.2f}")
            lines.append("")
            lines.append("EXPENSES")
            lines.append("-" * 60)
            for code, name, amt in expense_items:
                lines.append(f"  {code:<6} {name:<36} {amt:>13,.2f}")
            lines.append(f"  {'TOTAL EXPENSES':<43} {total_expenses:>13,.2f}")
            lines.append("=" * 60)
            lines.append(f"  {'NET SURPLUS / (DEFICIT)':<43} {net_income:>13,.2f}")
            lines.append("=" * 60)
            return "\n".join(lines)

    def balance_sheet(
        self,
        as_of_date: Optional[date] = None,
        as_markdown: bool = False,
        entity: Optional[str] = None,
    ) -> str:
        # All historical balances up to as_of_date
        balances = self.ledger.get_balances(end_date=as_of_date, entity=entity)
        
        assets = []
        liabilities = []
        equity = []
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        total_equity = Decimal("0.00")
        
        # Calculate net income for all history to date to include in Equity
        total_revenue = Decimal("0.00")
        total_expenses = Decimal("0.00")

        for code in sorted(balances.keys()):
            bal = balances[code]
            if bal.account.type == AccountType.ASSET:
                net = bal.total_debits - bal.total_credits
                if net != 0:
                    assets.append((bal.account.code, bal.account.name, net))
                    total_assets += net
            elif bal.account.type == AccountType.LIABILITY:
                net = bal.total_credits - bal.total_debits
                if net != 0:
                    liabilities.append((bal.account.code, bal.account.name, net))
                    total_liabilities += net
            elif bal.account.type == AccountType.EQUITY:
                net = bal.total_credits - bal.total_debits
                if net != 0:
                    equity.append((bal.account.code, bal.account.name, net))
                    total_equity += net
            elif bal.account.type == AccountType.REVENUE:
                total_revenue += (bal.total_credits - bal.total_debits)
            elif bal.account.type == AccountType.EXPENSE:
                total_expenses += (bal.total_debits - bal.total_credits)

        retained_surplus = total_revenue - total_expenses
        total_liabilities_and_equity = total_liabilities + total_equity + retained_surplus
        as_of_str = f"As of {as_of_date.strftime('%Y-%m-%d')}" if as_of_date else "All Dates"

        if as_markdown:
            lines = [
                f"# Balance Sheet (Statement of Financial Position)",
                f"*{as_of_str}*",
                "",
                "### Assets",
                "| Code | Account | Amount ($) |",
                "| :--- | :--- | ---: |",
            ]
            for code, name, amt in assets:
                lines.append(f"| {code} | {name} | {amt:,.2f} |")
            lines.append(f"| | **Total Assets** | **{total_assets:,.2f}** |")
            lines.append("")
            lines.append("### Liabilities")
            lines.append("| Code | Account | Amount ($) |")
            lines.append("| :--- | :--- | ---: |")
            for code, name, amt in liabilities:
                lines.append(f"| {code} | {name} | {amt:,.2f} |")
            lines.append(f"| | **Total Liabilities** | **{total_liabilities:,.2f}** |")
            lines.append("")
            lines.append("### Net Assets / Equity")
            lines.append("| Code | Account | Amount ($) |")
            lines.append("| :--- | :--- | ---: |")
            for code, name, amt in equity:
                lines.append(f"| {code} | {name} | {amt:,.2f} |")
            lines.append(f"| | Current Surplus / (Deficit) | {retained_surplus:,.2f} |")
            lines.append(f"| | **Total Net Assets & Equity** | **{(total_equity + retained_surplus):,.2f}** |")
            lines.append("")
            lines.append(f"## **Total Liabilities & Equity: ${total_liabilities_and_equity:,.2f}**")
            diff = total_assets - total_liabilities_and_equity
            if diff != 0:
                lines.append(f"\n> **WARNING: Assets != Liab + Equity by ${diff:,.2f}**")
            return "\n".join(lines)
        else:
            lines = [
                "=" * 60,
                f"BALANCE SHEET — {as_of_str}",
                "=" * 60,
                "ASSETS",
                "-" * 60,
            ]
            for code, name, amt in assets:
                lines.append(f"  {code:<6} {name:<36} {amt:>13,.2f}")
            lines.append(f"  {'TOTAL ASSETS':<43} {total_assets:>13,.2f}")
            lines.append("")
            lines.append("LIABILITIES")
            lines.append("-" * 60)
            for code, name, amt in liabilities:
                lines.append(f"  {code:<6} {name:<36} {amt:>13,.2f}")
            lines.append(f"  {'TOTAL LIABILITIES':<43} {total_liabilities:>13,.2f}")
            lines.append("")
            lines.append("NET ASSETS / EQUITY")
            lines.append("-" * 60)
            for code, name, amt in equity:
                lines.append(f"  {code:<6} {name:<36} {amt:>13,.2f}")
            lines.append(f"  {'Current Net Surplus / (Deficit)':<43} {retained_surplus:>13,.2f}")
            lines.append(f"  {'TOTAL NET ASSETS / EQUITY':<43} {(total_equity + retained_surplus):>13,.2f}")
            lines.append("=" * 60)
            lines.append(f"  {'TOTAL LIABILITIES & EQUITY':<43} {total_liabilities_and_equity:>13,.2f}")
            lines.append("=" * 60)
            diff = total_assets - total_liabilities_and_equity
            if diff != 0:
                lines.append(f"*** OUT OF BALANCE: Assets vs Liab+Equity differs by ${diff:,.2f} ***")
            return "\n".join(lines)
