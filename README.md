# git-ledger

> **Git-native, plain-text double-entry accounting for open communities and micro-organizations.**

`git-ledger` is an open-source accounting engine designed to replace bloated SaaS accounting tools (like QuickBooks or Wave) with version-controlled, auditable, and human-readable financial records.

---

## Key Features

- **Git-Native Auditability:** Commits are journal entries; pull requests are approvals; Git tags mark closed accounting periods.
- **Double-Entry Integrity:** Automatically enforces that every transaction balances ($\sum \text{Debits} = \sum \text{Credits}$) and adheres to standard accounting equations.
- **Zero Database Overhead:** Operates directly on plain YAML or JSON files. No databases to configure or maintain.
- **Zero Required Dependencies:** Runs on standard Python 3.10+ (PyYAML is supported if installed, with seamless standard-library fallback).
- **Automated Financial Statements:** Instant generation of Trial Balances, Income Statements (P&L), and Balance Sheets in Terminal tables and Markdown.
- **Bank CSV Importer:** Fast ingestion of bank and credit card CSV exports with rule-based categorization.
- **Pre-Commit Enforcement:** Built-in Git pre-commit hooks prevent committing out-of-balance transactions to repository history.

---

## Directory Structure

A `git-ledger` directory contains:

```
my-books/
├── accounts.yaml          # Chart of Accounts definition
└── journal/
    ├── 2024.yaml          # Journal entries for 2024
    ├── 2025.yaml          # Journal entries for 2025
    └── 2026.yaml          # Journal entries for 2026
```

---

## Quickstart

### 1. Initialize a Ledger
```bash
python3 -m gitledger.cli init ./books
# or if installed:
git-ledger init ./books
```
This generates a standard 501(c)(6) / micro-nonprofit Chart of Accounts and initial journal folder.

### 2. Record Transactions
Transactions are stored in plain YAML format:

```yaml
- id: tx-20260115-001
  date: "2026-01-15"
  description: "Annual domain registration renewal"
  reference: "REC-88912"
  entries:
    - account: "5010"     # Domain Names & DNS Expense
      debit: 35.00
      memo: "sharealedger.org renewal"
    - account: "1010"     # Checking Account
      credit: 35.00
```

You can also record transactions from the command line:
```bash
git-ledger record ./books \
  --desc "Member voluntary contribution" \
  --debit 1010 \
  --credit 4100 \
  --amount 500.00
```

### 3. Check Ledger Health
```bash
git-ledger check ./books
```

### 4. Generate Reports

#### Trial Balance:
```bash
git-ledger balance ./books
git-ledger balance ./books --md
```

#### Income Statement (Statement of Activities):
```bash
git-ledger income ./books --from 2026-01-01 --to 2026-12-31 --md
```

#### Balance Sheet (Statement of Financial Position):
```bash
git-ledger balance-sheet ./books --as-of 2026-12-31 --md
```

### 5. Install Git Pre-Commit Hook
Prevent accidental commits with unbalanced journal entries:
```bash
git-ledger hook install .
```

---

## Architecture & Accounting Model

`git-ledger` implements the standard accounting equation:

$$\text{Assets} = \text{Liabilities} + \text{Equity} + (\text{Revenues} - \text{Expenses})$$

Account types and normal balance rules:
- **1000s (Assets):** Normal Debit
- **2000s (Liabilities):** Normal Credit
- **3000s (Equity / Net Assets):** Normal Credit
- **4000s (Revenue):** Normal Credit
- **5000s–6000s (Expenses):** Normal Debit

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
