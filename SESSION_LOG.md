# git-ledger Session Log & Architecture Roadmap

**Date:** March 2026
**Status:** Repo Topology Established | Next Phase: Wave Import into sharealedger-books

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

## 4. Next Session Plan: Wave Import into sharealedger-books

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
