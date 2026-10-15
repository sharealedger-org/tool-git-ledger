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
- **Wave Importer:** Reads Wave's double-entry CSV export format, preserving source transaction IDs as provenance.
- **Pre-Commit Enforcement:** Built-in Git pre-commit hooks prevent committing out-of-balance transactions to repository history.

---

## Directory Structure

A `git-ledger` books directory contains:

```
my-books/
├── accounts.yaml          # Chart of Accounts definition
├── journal/
│   ├── 2024.yaml          # Journal entries by year
│   └── 2025.yaml
├── imports/               # Source CSVs (Wave, bank, card exports)
│   └── accounting.csv
└── mapping-rules/
    └── wave-import.yaml   # Account name → chart code rules for Wave import
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

### 3. Import from Wave
```bash
git-ledger wave-import accounting.csv ./books \
  --entity my-org \
  --rules ./books/mapping-rules/wave-import.yaml \
  --dry-run    # preview without writing
```

### 4. Check Ledger Health
```bash
git-ledger check ./books
```

### 5. Generate Reports

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

### 6. Install Git Pre-Commit Hook
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

## Deployment Patterns

`git-ledger` separates **the tool** (this repo) from **the books** (a separate data repo). This mirrors how you would separate source code from the data it processes, and enables independent access control and history for financial records.

### Pattern 1 — Single Entity (Solo / Small Org)

One data repo holds one entity's books. The owner is both officer and member; everyone with repo access sees everything.

```
my-books/                  ← one Git repo, one entity
├── accounts.yaml
├── journal/
├── imports/
└── mapping-rules/
```

Typical GitHub access model: private repo, owner has full access, invite members as collaborators with read access.

### Pattern 2 — Single Entity, Governed Access (Membership Org)

Same single-entity structure, but the data repo has a formal access model separating officers (write) from members (read).

```
my-books/                  ← one Git repo, one entity
├── accounts.yaml
├── journal/
├── imports/               ← source CSVs stay here, visible to members
└── mapping-rules/
```

GitHub access model:
- Create a `members` team → `pull` (read) on the books repo
- Create an `officers` team → `push` (write) on the books repo
- Require pull request + officer review before merging to `main` (requires GitHub Pro for private repos)

### Pattern 3 — Multiple Legal Entities, Shared Governance

When two or more legal entities share the same member population and officer set, their books can live in a single data repo under entity-named subdirectories. The directory structure declares the partition boundary; access control is applied at the repo level.

```
my-org-books/              ← one Git repo, multiple entities
├── entity-a/
│   ├── accounts.yaml
│   ├── journal/
│   ├── imports/
│   └── mapping-rules/
└── entity-b/
    ├── accounts.yaml
    ├── journal/
    ├── imports/
    └── mapping-rules/
```

CLI commands scope to the entity subdirectory:
```bash
git-ledger balance ./my-org-books/entity-a
git-ledger income  ./my-org-books/entity-b --from 2025-01-01 --to 2025-12-31
```

**Known limitation:** All repo members can read all entities' books. The directory structure declares the conceptual partition but cannot enforce independent read access between entities within the same repo. If the two entities ever need independent access control (different member populations, regulatory separation, or third-party audit of only one entity), the correct path is to split into two repos — one per entity. The YAML journal files are self-contained and portable; migration is a `git mv` and a URL update in your tooling.

**Inter-entity transfers:** When one entity pays another (e.g., LLC contributes to NFP), each entity records its own journal entry. Both entries share a `shared_event_id` field that links them as two accounting projections of one economic event. Future tooling will validate that linked entries net to zero across entities.

### Pattern 4 — Multiple Legal Entities, Independent Governance

Each entity has its own repo with its own access model. Use this when entities have different member populations, require independent audit trails, or are governed by different officer sets.

```
entity-a-books/            ← separate Git repo
└── ...

entity-b-books/            ← separate Git repo
└── ...
```

Consolidated reports can still be generated by pointing `git-ledger balance --consolidated` at a parent directory that contains both repos as subdirectories (or Git submodules).

---

## Code and Data Separation

The tool (`git-ledger`) and the books (your data repo) are intentionally separate Git repositories:

| Repo | What it holds | Who should have access |
|------|--------------|------------------------|
| `git-ledger` | Source code, CLI, importer engine | Public (open source) |
| `my-org-books` | Journals, charts, imports, reports | Members (read), Officers (write) |
| `my-org-admin` | Raw exports, corporate records, tax filings | Officers only |

This separation means:
- Members can inspect the financial record without seeing the source accounting system exports
- Officers can update books via pull request, giving an officer-review audit trail on every change
- The tool can be upgraded independently of the financial record history

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
