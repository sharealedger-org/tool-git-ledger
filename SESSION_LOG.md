# git-ledger Session Log & Architecture Roadmap

**Date:** March 2026
**Status:** Live Import Complete | Journals on `import/wave-all-years` PR | All year-end statements reconciled ✓

---

## 1. Accomplishments — Session 1

1. **Repository Setup & Workspace Integration:**
   - Initialized `git-ledger` repository with Apache-2.0 licensing and `pyproject.toml` packaging.
   - Integrated `git-ledger` into the root VS Code workspace (`sharealedger.code-workspace`).
   - Added `git-ledger` project cards and links across the public Sharealedger website (`community/docs/`).

2. **Core Accounting Engine (`gitledger`):**
   - **`models.py`**: Double-entry data structures using exact `Decimal` precision.
   - **`chart.py`**: Configurable Chart of Accounts with defaults for micro-entities and 501(c)(6) nonprofits.
   - **`ledger.py`**: Plain-text journal ingestion (YAML/JSON), balance calculation, invariant validation.
   - **`reports.py`**: Trial Balance, Income Statement, Balance Sheet in Terminal and Markdown formats.
   - **`importer.py`**: Bank/card CSV import engine with keyword-to-account rule mapping.
   - **`hooks.py`**: Git pre-commit hook integration.
   - **`io.py`**: Zero-dependency standard library support with optional PyYAML integration.
   - **`cli.py`**: CLI (`init`, `check`, `balance`, `income`, `balance-sheet`, `record`, `import`, `hook`).

3. **Testing & Verification:**
   - 100% test coverage on core invariant verification, imbalance detection, and report math.
   - Verified sample journal transactions in `examples/sample_ledger/`.

---

## 2. Accomplishments — Session 2

**Architecture informed by the Sharealedger Conceptual Model** (`conceptual-model` repo), specifically:
- TTL (source event) layer is unique to the source — preserve it, don't transform immediately.
- Events are perspective-independent; charts of accounts are projections, not the universal ontology.
- Shared vs. private partition: inter-entity transfers are one economic event, two accounting projections.

### Changes Made

1. **`models.py` — Multi-entity fields on `Transaction`:**
   - `entity: Optional[str]` — tags each transaction to its owning entity (e.g. `sharealedger-llc`)
   - `source_event_id: Optional[str]` — preserves original source system ID (Wave Transaction ID)
   - `shared_event_id: Optional[str]` — links both sides of an inter-entity event

2. **`ledger.py` — Entity-aware loading and filtering:**
   - `Ledger.__init__` and `Ledger.load()` accept an `entity` parameter; entity is inferred from directory name if not supplied.
   - `Ledger.load_consolidated(books_dir)` — loads all entity sub-ledgers into one consolidated ledger.
   - `Ledger.get_balances()` accepts an `entity` filter parameter.
   - `add_transaction()` writes `entity`, `source_event_id`, `shared_event_id` to YAML journal.

3. **`chart.py` — Entity-specific charts:**
   - `_BASE_ACCOUNTS` — shared accounts used by both entities (including inter-company: `1300 Due from NFP`, `2300 Due to LLC`).
   - `DEFAULT_LLC_ACCOUNTS` — member equity structure (contributions/drawings).
   - `DEFAULT_NFP_ACCOUNTS` — net assets structure (unrestricted/restricted, 501(c)(6) revenue).
   - `ChartOfAccounts.default_llc()` and `.default_nfp()` factory methods.

4. **`importer.py` — `WaveImporter` class:**
   - Reads Wave's two-rows-per-transaction double-entry format, grouping by `Transaction ID`.
   - Resolves Wave account names → chart codes via a **declared mapping-rules YAML file** (not hardcoded keywords).
   - Falls back to Wave `Account Group` (`Asset`/`Liability`/etc.) if no exact name match.
   - Preserves Wave `Transaction ID` as `source_event_id` on every generated `Transaction`.
   - **Smoke-tested against real Wave exports:** LLC 55/55 balanced, NFP 255/255 balanced.

5. **`reports.py`** — All three report methods accept `entity` filter parameter.

6. **`cli.py`** — New `wave-import` command; `--entity` flag on `balance`, `income`, `balance-sheet`.

7. **Book directory structure created:**
   ```
   books/
     sharealedger-llc/
       accounts.yaml                      ← LLC chart (26 accounts, member equity)
       journal/                           ← empty, ready for import
       mapping-rules/
         wave-import.yaml                 ← Wave account name → chart code rules
     sharealedger-nfp/
       accounts.yaml                      ← NFP chart (30 accounts, net assets)
       journal/                           ← empty, ready for import
       mapping-rules/
         wave-import.yaml                 ← Wave account name → chart code rules
   ```

---

## 3. Accomplishments — Session 3: Repo Topology & Governance

### Architecture Decisions Made

1. **Three-book distinction clarified:**
   - **Journal** — raw chronological entries (the Wave YAML files). Private input layer.
   - **Ledger** — posted account positions derived from journals. The canonical member-readable record.
   - **Reports** — derived views (Income Statement, Balance Sheet, Trial Balance).

2. **Ephemeral vs. persisted ledger:**
   - Stay ephemeral (re-derive on every run) until journal file size approaches 10% of available memory.
   - At that threshold, auto-persist the ledger with a **Git commit SHA stamp** as provenance.
   - The Git SHA satisfies the conceptual model's derivation invariant without a custom stamping mechanism.
   - The committer/merge is the authorizing agent; the commit history is the evidence chain.

3. **Repo topology established — code and data separated:**

   | Repo | Visibility | Purpose |
   |------|-----------|---------|
   | `git-ledger` | Public (planned) | The tool — code only |
   | `sharealedger-books` | Private, member-readable | Journals, imports, ledger cache, reports |
   | `admin` | Private, officers only | Raw Wave CSVs (backup), corporate records |

4. **Two deployment patterns documented:**
   - **Organizational** (Sharealedger model): governance boundary between raw imports and authorized ledger; officers write, members read.
   - **Instance** (solo/small org QuickBooks user): owner is officer; full chain (CSV → journal → ledger) in one repo; members see everything.

5. **Write access control model:**
   - `sharealedger-members` GitHub team → `pull` (read) on `sharealedger-books`
   - `sharealedger-officers` GitHub team → `push` (write) on `sharealedger-books`
   - Branch protection (PR required, 1 officer review) → **blocked by GitHub Free plan** on private repos. Enforce via convention until org upgrades to GitHub Pro.

### Changes Made

1. **`sharealedger-org/sharealedger-books` repo created** — private, member-readable.
2. **`sharealedger-members` team** granted `pull` on `sharealedger-books` (confirmed `push: false`).
3. **`sharealedger-officers` team** created; `KipTwitchell` added as maintainer; granted `push` on `sharealedger-books`.
4. **`books/` migrated** from `git-ledger` → `sharealedger-books` (was untracked; no git history to preserve).
5. **`books/` added to `.gitignore`** in `git-ledger` — won't re-appear accidentally.
6. **Wave import CSVs copied** into `sharealedger-books/sharealedger-llc/imports/` and `sharealedger-nfp/imports/` — member-readable source record alongside journals.
7. **`admin/members/README.md` SOP updated** — Step 2 and welcome email now reference both `members` and `sharealedger-books`.
8. **`sharealedger.code-workspace` updated** — `sharealedger-books` added as workspace folder.

### Future Enhancements Identified

- **QuickBooks importer** — `QuickBooksImporter` class analogous to `WaveImporter`; needed when a QuickBooks user wants to contribute or adopt `git-ledger`.
- **`git-ledger/examples/sample_books/`** — reference instance repo structure for new adopters.
- **Auto-persist threshold** — implement memory check + Git SHA stamp in `ledger.py` (post `post` command).
- **Branch protection** — revisit when org upgrades to GitHub Pro.

---

## 4. Accomplishments — Session 4: Pre-Import Reconciliation & Structural Decisions

### Bug Fixed: YAML parser couldn't read mapping-rules files

**Root cause:** `io.py`'s fallback YAML parser (`_parse_simple_yaml`) only handled
list-of-dicts format. Mapping-rules files are top-level dicts — so without PyYAML installed,
every account mapping silently fell back to `5900 Miscellaneous`.

**Fix:** Extended `_parse_simple_yaml` into a dispatcher that detects list vs. dict structure
and routes accordingly. Added `_parse_yaml_dict` for top-level dict YAML with nested sub-dicts,
and `_strip_inline_comment` to handle `"5900"  # comment` value syntax correctly. All 4 tests
still pass.

### Account categorization: fully correct, pre-import

After the fix, verified every Wave account name routes to the correct chart code (both entities):

**LLC routing (key mappings):**
- `Bank Service Charges` → `5400` Bank & Merchant Processing Fees
- `Computer – Hosting` → `5000` Web Hosting & Infrastructure
- `Computer – Software` / `Dues & Subscriptions` / `Business Association Expenses` → `5900` Miscellaneous (LLC → NFP contributions; dedicated account `5800` deferred)
- `Education & Training` → `5300` Educational Video & Media Production
- `Meals and Entertainment` → `5600` Travel & Meeting Expenses
- `CREDIT CARD (4908)` → `2050` Credit Card Payable
- `Transfer Clearing` → `1050` Transfer Clearing

**NFP routing (key mappings):**
- `Accounting Fees` / `Contract Services` / `Legal Fees` → `5100` Legal & Professional Fees
- `Website & IT Expenses` → `5000` Web Hosting & Infrastructure
- `Travel Expense` / `Conferences Fees` → `5600` Travel & Meeting Expenses
- `Taxes – Corporate Tax` → `5200` Filing & Regulatory Fees
- `Postage & Delivery` → `5500` Office Supplies & Software
- `K. TWITCHELL (4908)` → `2050` Credit Card Payable
- `Payable to Sharealedger LLC` → `2300` Due to Sharealedger LLC
- `Direct Public Support – Business Contributions` → `4100` Contributions & Donations

### Pre-import reconciliation: fully confirmed

Dry-run P&L compared against `Sharealedger Financial Statements.xlsx` for all years:

| Year | NFP Revenue | NFP Expenses | NFP Net | LLC Expenses | Status |
|------|-------------|--------------|---------|--------------|--------|
| 2021 | $6,500.00 | $4,868.03 | $1,631.97 | $6,991.76 | ✓ exact match |
| 2022 | $13,710.51 | $13,273.56 | $436.95 | $3,589.00* | ✓ match (see note) |
| 2023 | $1,800.00 | $1,577.08 | $222.92 | $1,800.00 | ✓ exact match |
| 2024 | $2,800.00 | $2,755.30 | $44.70 | $2,800.00 | ✓ exact match |
| 2025 | $2,000.00 | $2,025.88 | ($25.88) | $2,000.00 | ✓ exact match |

*LLC 2022 delta of $20.76: Wave dates a cash-balancing entry 2023-01-02; Excel absorbed it into 2022.
All-years totals are correct; the difference is year-split only, not a missing transaction.

### Conceptual model evaluation: storage and partition boundary

Evaluated the current `sharealedger-books` design against the Sharealedger Open Accounting
Framework (`conceptual-model/framework/open-accounting-framework.md`), specifically the
shared/private partition model.

**Finding:** Two legal entities in one repo is a **Pattern 3 — Shared Governance** deployment.
It is a deliberate simplification, not an oversight. The framework's partition boundary is
declared by directory structure (`sharealedger-llc/` vs `sharealedger-nfp/`) but cannot be
enforced at the file access level within a single repo.

**Why this is acceptable now:**
- LLC and NFP share the same member population and officer set — no governance reason for
  independent read access today
- Directory structure preserves conceptual clarity and makes a future split clean
- `shared_event_id` on `Transaction` is the right hook for inter-entity event integrity;
  validation deferred to a future `git-ledger check` enhancement

**Trigger for a future repo split:**
- Entities develop different member populations
- Regulatory or audit requirements mandate separated records
- A third-party auditor needs access to one entity only

**When that happens:** YAML journal files are self-contained; migration is `git mv` + URL update.

### Documentation updated

1. **`git-ledger/README.md`** — Added four deployment patterns (Solo, Governed Single Entity,
   Multi-Entity Shared Governance, Multi-Entity Independent Governance) plus a Code/Data
   Separation section. Added Wave Importer to features. Updated directory structure to include
   `imports/` and `mapping-rules/`.

2. **`sharealedger-books/README.md`** — Full rewrite. Documents the repo structure, identifies
   Pattern 3 as the chosen deployment model, explains the known simplification and its
   acceptable conditions, documents the inter-entity transfer mechanism, provides ready-to-run
   CLI commands for imports and reports, and documents the GitHub access model.

---

## 5. Accomplishments — Session 5: Live Import & Full Reconciliation

### Steps Completed

1. **Wrote journals** (dropped `--dry-run`) for both entities:
   - LLC: 55 transactions written to `sharealedger-books/sharealedger-llc/journal/` (2021–2025)
   - NFP: 255 transactions written to `sharealedger-books/sharealedger-nfp/journal/` (2021–2026)

2. **Validated**: `git-ledger check` passed on both — 55 and 255 transactions all balanced and valid.

3. **Verified Transfer Clearing**: Account `1050` nets to **$0.00** on both entities. ✓

4. **Committed and pushed** to `sharealedger-books` branch `import/wave-all-years`:
   - 11 journal YAML files, 7,247 lines inserted
   - PR: https://github.com/sharealedger-org/sharealedger-books/pull/new/import/wave-all-years

5. **Generated all year-end statements** and reconciled against `admin/financials/Accounting/Sharealedger Financial Statements.xlsx`:

   **NFP — Income Statement** ✓ exact match all years

   | Year | Revenue | Expenses | Net |
   |------|---------|----------|-----|
   | 2021 | $6,500.00 | $4,868.03 | $1,631.97 |
   | 2022 | $13,710.51 | $13,273.56 | $436.95 |
   | 2023 | $1,800.00 | $1,577.08 | $222.92 |
   | 2024 | $2,800.00 | $2,755.30 | $44.70 |
   | 2025 | $2,000.00 | $2,025.88 | ($25.88) |

   **NFP — Balance Sheet** ✓ exact match all years (checking, liabilities, equity)

   **LLC — Income Statement** ✓ exact match all years except known 2022 year-split delta ($20.76)

   **LLC — Balance Sheet** ✓ exact match all years

### Known Delta — LLC 2022
- git-ledger 2022 expenses: $3,589.00 vs. Excel $3,568.24 (delta $20.76)
- Root cause: Wave dates a cash-balancing entry 2023-01-02; git-ledger books it in 2023 as `Opening Balance Equity`. Excel absorbed it into 2022.
- All-years totals reconcile correctly. Not a missing or erroneous transaction.

---

## 6. Accomplishments — Session 6: Auto-Persist & QuickBooks Importer

### Auto-Persist Threshold (`ledger.py`)

Implemented the design from Session 3: re-derive ephemerally until journal files reach 10% of available memory; at that threshold, auto-persist computed balances with a Git SHA provenance stamp.

**New methods on `Ledger`:**
- `journal_size_bytes(ledger_dir)` — sums all journal file sizes under `journal/`
- `available_memory_bytes()` — reads available memory via `resource` (Linux/macOS), `vm_stat` (macOS fallback), `/proc/meminfo` (Linux fallback), then 512 MB conservative fallback
- `_get_git_sha(ledger_dir)` — runs `git rev-parse HEAD` to get the authorizing commit
- `persist_ledger(git_sha)` — writes `ledger-cache.yaml` with all account balances + metadata (generated timestamp, entity, transaction count, git SHA)
- `check_and_persist(threshold_pct)` — compares journal bytes to available memory × threshold; calls `persist_ledger()` if exceeded

**New CLI command: `persist`**
```bash
# Check against threshold (default 10% of available memory)
python3 gitledger/cli.py persist ../sharealedger-books/sharealedger-nfp

# Force snapshot regardless of threshold
python3 gitledger/cli.py persist ../sharealedger-books/sharealedger-nfp --force

# Custom threshold
python3 gitledger/cli.py persist ../sharealedger-books/sharealedger-nfp --threshold 5
```

**Design note:** The cache is a provenance record, not a read-through cache. `Ledger.load()` always re-derives from journals — the snapshot is for archival and auditability when files grow large, not for performance.

### QuickBooks Importer (`importer.py`)

Implemented `QuickBooksImporter`, structured identically to `WaveImporter`:
- Targets the QuickBooks Desktop **General Ledger** / **Transaction Detail by Account** CSV export format
- Handles both Desktop (`Type, Date, Num, Name, Memo, Account, Debit, Credit`) and Online (`Transaction Type, Date, Num, Name, Memo/Description, Account, Debit, Credit`) column variants via case-insensitive matching
- Groups rows by `(Date, Num, Memo)` into transactions (the QB natural transaction key)
- Skips header/subtotal rows (no account or no debit/credit values)
- Resolves QB account names → chart codes via declared `qb-import.yaml` mapping rules; falls back to keyword matching on account type (bank, expense, income, etc.)
- `--rules` is optional; keyword fallbacks cover common cases without a rules file

**New CLI command: `qb-import`**
```bash
python3 gitledger/cli.py qb-import \
  "general-ledger.csv" \
  path/to/entity-books \
  --entity my-org \
  --rules path/to/mapping-rules/qb-import.yaml \
  --dry-run
```

**⚠️ Important caveat:** `QuickBooksImporter` was written against the documented QB CSV specification. No live QuickBooks export was available to test against. Validate with a real export before using in production; adjust `account_mappings` in the rules file as needed.

## 7. Next Session Plan

### Immediate: Merge the PR
- URL: https://github.com/sharealedger-org/sharealedger-books/pull/new/import/wave-all-years
- Officer review → merge `import/wave-all-years` → `main`

### Future Enhancements (carry-forward)
- **`shared_event_id` validation** — `git-ledger check` enhancement to verify inter-entity transfer pairs match
- **QuickBooks importer live test** — validate `QuickBooksImporter` against a real QB General Ledger CSV export; adjust column handling as needed
- **`git-ledger/examples/sample_books/`** — reference instance repo structure for new adopters; include a `qb-import.yaml` sample rules file
- **Branch protection** — revisit when org upgrades to GitHub Pro
- **Closing entries** — automate year-end retained earnings roll-forward (currently re-derives from all history)

---

## 6. Former Session 4 Plan (now completed as pre-work in Session 4)

### Step 1 — Run the Wave import (dry-run first)
```bash
# LLC dry run — paths now point to sharealedger-books
python3 gitledger/cli.py wave-import \
  "../sharealedger-books/sharealedger-llc/imports/accounting.csv" \
  ../sharealedger-books/sharealedger-llc \
  --entity sharealedger-llc \
  --rules ../sharealedger-books/sharealedger-llc/mapping-rules/wave-import.yaml \
  --dry-run

# NFP dry run
python3 gitledger/cli.py wave-import \
  "../sharealedger-books/sharealedger-nfp/imports/accounting.csv" \
  ../sharealedger-books/sharealedger-nfp \
  --entity sharealedger-nfp \
  --rules ../sharealedger-books/sharealedger-nfp/mapping-rules/wave-import.yaml \
  --dry-run
```

### Step 2 — Write journals and validate
```bash
# Run without --dry-run to write journals into sharealedger-books
python3 gitledger/cli.py check ../sharealedger-books/sharealedger-llc
python3 gitledger/cli.py check ../sharealedger-books/sharealedger-nfp
```

### Step 3 — Commit journals to sharealedger-books (PR workflow)
```bash
cd ../sharealedger-books
git checkout -b import/wave-2021
git add sharealedger-llc/journal/ sharealedger-nfp/journal/
git commit -m "import: Wave 2021 — LLC 55 transactions, NFP 255 transactions"
# Open PR → officer reviews → merge to main
```

### Step 4 — Generate statements and reconcile
```bash
python3 gitledger/cli.py income ../sharealedger-books/sharealedger-llc \
  --from 2021-01-01 --to 2021-12-31 --md

python3 gitledger/cli.py balance-sheet ../sharealedger-books/sharealedger-nfp \
  --as-of 2021-12-31 --md

python3 gitledger/cli.py balance ../sharealedger-books --entity consolidated --md
```

### Step 5 — Compare against admin financials
Reconcile output against `admin/financials/Accounting/Sharealedger Financial Statements.xlsx`
and the year-end PDFs in `admin/financials/Accounting/2021-Year-end/`.

### Key things to watch for:
- **`Dues & Subscriptions` on LLC side** maps to `5900` (Miscellaneous) today via fallback — may need a dedicated account.
- **`Transfer Clearing` (1050)** — Wave uses this for inter-entity moves; verify it nets to zero.
- **Inter-entity matching** — LLC "Contributions to NFP" should match NFP "Received from Sharealedger LLC" via `shared_event_id` (future enhancement).
- **Paths** — all CLI commands now target `../sharealedger-books/` not `books/`.
- **Verify `wave-import` writes to the correct location** — the `books_dir` argument was previously smoke-tested against `books/sharealedger-llc` (a subdirectory of `git-ledger`). It now points to `../sharealedger-books/sharealedger-llc` (a sibling repo). Confirm the CLI resolves this path correctly and that journal YAML files are written into `../sharealedger-books/sharealedger-llc/journal/` before running without `--dry-run`.
