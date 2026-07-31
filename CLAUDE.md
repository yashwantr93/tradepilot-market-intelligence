# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and human contributors
working in this repository.

## 1. Project Purpose

TradePilot AI is a rule-based swing-trading research dashboard for the Indian stock
market (NSE/BSE). It surfaces deal flow, institutional (FII/DII) activity, sector
rotation, corporate actions, and quarterly results as transparent if/else signals —
no ML/AI scoring anywhere in this codebase.

## 2. Folder Structure

```
market_intelligence_dashboard/
├── app.py                  # Streamlit entry point; PAGES dict wires up all pages
├── components.py           # Shared UI components
├── run_*.py                # Pipeline entry points (see "How to Run")
├── core/                   # V1 engine — connectors, pipelines, processing, db
│   ├── connectors/           # Raw data fetchers (NSE/BSE, yfinance), subclass BaseConnector
│   ├── pipelines/             # One file per data domain; EXTRACT→TRANSFORM→VALIDATE→STORE
│   ├── processing/            # Stateless rule logic (technicals, classification, sector map)
│   ├── db/                    # SQLAlchemy models + engine (data_store/market.db)
│   ├── validation/             # Row-level validators (bad rows quarantined, not dropped)
│   ├── watchlist/              # Selection engine / rules.py
│   ├── sector_rotation/        # Sector relative-strength logic
│   ├── utils/                  # Shared helpers
│   └── config.py               # ALL tunable thresholds — see Coding Standards
├── data/                    # data/contracts.py — the ONLY DB→UI read bridge
├── pages/                   # Streamlit pages (V1) — read-only, call contracts.py only
├── intelligence_v2/         # V2 — isolated subsystem, own db/config/logger (see below)
│   ├── config/ connectors/ contracts/ database/ models/ processors/ services/
│   ├── pages/                  # V2 Streamlit pages, wired into the same app.py PAGES dict
│   └── tests/                   # The only test suite in this repo
├── seed/                    # Deterministic offline/seeded data
├── scripts/                 # One-off utilities (e.g. brand asset generation)
├── assets/brand/            # Logos, icons
├── docs/                    # Design docs & PRDs (see Future Roadmap)
├── data_store/              # Generated SQLite DBs — gitignored, never hand-edit
├── reports/                 # Generated markdown/CSV report artifacts — gitignored
└── logs/                    # Runtime logs — gitignored
```

## 3. How to Run

```bash
pip install -r requirements.txt

# Run all pipelines in dependency order, then print next steps:
python run_daily.py
python run_daily.py --serve     # ...then also launch the dashboard

# Or run individual pipelines (same order run_daily.py uses):
python run_live.py              # Deal Flow: bulk/block deals + technicals
python run_institutional.py     # FII/DII + Sector Rotation
python run_corp_actions.py      # Corporate Actions
python run_results.py           # Quarterly Results
python run_combined.py          # Confluence (tiered combined watchlist)
python run_validation.py        # Signal validation (forward returns)

# V2 subsystem (separate database, run independently, in this order):
python run_v2_healthcheck.py
python run_v2_sector_intelligence.py   # requires V1's sector_rotation data to exist
python run_v2_market_cycle.py          # requires run_v2_sector_intelligence.py first

# Dashboard (reads whichever data the pipelines last wrote — re-run a pipeline
# and reload the page to refresh; the UI never fetches or computes on its own):
streamlit run app.py
```

VS Code / Claude launch config: `.claude/launch.json` (`streamlit run app.py
--server.headless true --server.port 8531`). On Windows, `run_daily_scheduled.ps1`
runs the full `run_daily.py` sequence unattended via Task Scheduler, logging to
`logs/scheduled_run.log`.

Set `MID_OFFLINE=0` to attempt live NSE/BSE/yfinance fetches instead of the
deterministic seeded fallback (default `MID_OFFLINE=1` — falls back to seed data
on any live-fetch failure, so the pipeline is always reproducible without credentials).

## 4. Development Workflow

1. Change thresholds/rules first in `core/config.py` before touching processing logic —
   that file is the intended extension point (see Coding Standards).
2. Run the relevant pipeline(s) locally with default offline mode before reloading the
   dashboard — the UI never computes anything itself, it only reads what pipelines wrote.
3. Adding a page = one import + one line in the `PAGES` dict in `app.py` (V1) or the
   equivalent in `intelligence_v2/`.
4. Keep V1 (`core/`, `data/`, `pages/`) and V2 (`intelligence_v2/`) isolated — see
   Architecture Notes below before adding any cross-imports.
5. `reports/` output is a side effect of pipeline runs, not something to hand-edit;
   re-run the pipeline to regenerate it.

## 5. Git Workflow

- Single `main` branch; no release branches yet. Commit directly to `main` for now,
  but keep commits scoped to one logical change (one rule tweak, one pipeline fix, etc.)
  so history stays useful for debugging a bad signal later.
- Commit message convention: `<area>: <what changed>` (e.g. `config: raise RS strong
  threshold to 1.15`, `pipelines: fix corp-actions dedup key`).
- Generated data (`data_store/*.db`, `logs/`, `reports/`, `__pycache__/`) is gitignored —
  never `git add -f` these; if a pipeline needs its output tracked, export a summary into
  `docs/` instead.
- Before committing a `core/config.py` threshold change, note the *reason* in the commit
  body (what signal prompted it) — thresholds have no other changelog.

## 6. Testing Commands

```bash
# V2 only — V1 currently has no automated test suite (see Future Roadmap):
python -m pytest intelligence_v2/tests/ -v
```

For V1, validate changes manually via `python run_validation.py` (forward-return
signal validation) and by spot-checking `reports/` output after a pipeline run.

## 7. Common Troubleshooting

- **Dashboard shows stale/empty data** — the UI never fetches on its own; re-run the
  relevant pipeline (`run_live.py`, `run_institutional.py`, etc.) then reload the page.
- **V2 pipeline errors referencing missing sector data** — run
  `run_v2_sector_intelligence.py` before `run_v2_market_cycle.py`; V2 depends on V1's
  `sector_rotation` table via a read-only bridge.
- **`database is locked`** — close any other process (Streamlit, a Python shell) holding
  an open connection to `data_store/market.db` or `market_v2.db`.
- **A write attempt into V1's DB from V2 code fails unexpectedly** — this is by design;
  `intelligence_v2/database/v1_reference.py` opens `market.db` with SQLite's
  `mode=ro` URI, so writes are rejected at the OS/SQLite level, not just by convention.
- **`ModuleNotFoundError`** — re-run `pip install -r requirements.txt`; V1 and V2 share
  one requirements file.
- **Corporate-action miscategorized** — check keyword order in `EVENT_TYPE_RULES` in
  `core/config.py`; it's an ordered list and the first matching keyword wins (e.g.
  "rights"/"preferential" must precede a generic "fund rais" match).
- **Live fetch failing** — confirm `MID_OFFLINE` is set as intended; `0` attempts live
  NSE/BSE/yfinance and falls back to seed data on failure, `1` (default) skips the
  network entirely.

## 8. Coding Standards

- **Rule-based only.** No ML/AI scoring, probabilistic ranking, or opaque heuristics.
  Every classification is a deterministic, documented threshold/condition in
  `core/config.py`. A new rule = an explicit condition there, not a model.
- **Pipelines follow EXTRACT → TRANSFORM → VALIDATE → STORE**: fetch via a
  `BaseConnector` subclass, enrich via `core/processing/transforms.py`, validate via
  `core/processing/validators.py` (bad rows go to a dead-letter table, never silently
  dropped), then dedup-upsert via `core/db/repository.py`. Wrap every run in a job
  record (`repo.start_job` / `repo.finish_job`) for auditability.
- **`data/contracts.py` is the only read bridge** between the DB and the UI. All
  `st.cache_data` getters live there, including `opportunity_hub()`'s priority/action/
  "why not" derivation — display-only re-ranking over already-computed fields, never a
  new scoring model.
- **Dashboard pages are strictly read-only** — they call `data/contracts.py` getters
  and render; they never touch connectors, pipelines, or the DB directly.
- **V1/V2 isolation is load-bearing, not stylistic.** Nothing in `intelligence_v2/`
  imports from `core.*`, and nothing in `core/` imports from `intelligence_v2/`. If you
  touch `intelligence_v2/`, do not add a `core.*` import.

## 9. Files That Should Never Be Modified Automatically

- `data_store/*.db` (`market.db`, `market_v2.db`) — generated by pipelines; hand-editing
  breaks provenance/job-record auditability. Gitignored.
- `reports/*` — generated artifacts, overwritten on each pipeline run. Gitignored.
- `logs/*` — runtime logs. Gitignored.
- `intelligence_v2/database/v1_reference.py`'s read-only connection logic — this is a
  hard safety boundary (SQLite `mode=ro`), not a convenience wrapper; do not "simplify"
  it into a normal read-write connection.
- `.streamlit/secrets.toml` (if ever created) — never commit; already gitignored.
- `__pycache__/`, `.pytest_cache/` — build/tool cache, regenerated automatically.

## 10. Future Roadmap

V1 (this dashboard) is considered **frozen** — active design work is happening in
`docs/`, not yet in code:

- `docs/V2_PRODUCT_REQUIREMENTS.md` — product definition for the V2 expansion.
- `docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md` — technical architecture for Sector
  Intelligence / Market Cycle / Position / Bearish engines (design only, partially
  implemented so far as `run_v2_sector_intelligence.py` / `run_v2_market_cycle.py`).
- `docs/V2_DATA_INTEGRATION_PLAN.md`, `docs/V2_IMPLEMENTATION_PLAN.md` — supporting plans.

Known gaps worth addressing (inferred from the current codebase, not a commitment):
a V1 test suite doesn't exist yet; `MID_DATABASE_URL` suggests a future Postgres
backend but SQLite is the only implementation today; the Task Scheduler-based daily
run (`run_daily_scheduled.ps1`) is Windows-only, worth revisiting after the workspace
migration to `D:\Projects`.
