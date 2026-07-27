# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TradePilot AI — a rule-based swing-trading research dashboard for the Indian stock market
(NSE/BSE). It surfaces deal flow, institutional (FII/DII) activity, sector rotation,
corporate actions, and quarterly results as transparent if/else signals. **There is no
ML/AI scoring anywhere in this codebase** — every classification is a deterministic,
explainable rule defined in `core/config.py`. Do not introduce probabilistic scoring,
ranking models, or opaque heuristics; if a new rule is needed, add it as an explicit,
documented threshold/condition.

## Commands

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
python run_v2_market_cycle.py         # requires run_v2_sector_intelligence.py first

# Dashboard (reads whichever data the pipelines last wrote — re-run a pipeline
# and reload the page to refresh; the UI never fetches or computes on its own):
streamlit run app.py

# Tests (V2 only — V1 has no test suite):
python -m pytest intelligence_v2/tests/ -v
```

There is a VS-Code/Claude launch config at `.claude/launch.json` (`streamlit run app.py
--server.headless true --server.port 8531`).

On Windows, the whole `run_daily.py` sequence is also invoked unattended via Task
Scheduler through `run_daily_scheduled.ps1`, which logs to `logs/scheduled_run.log`.

Set `MID_OFFLINE=0` to attempt live data sources (NSE/BSE/yfinance) instead of the
deterministic seeded fallback data — see Offline mode below.

## Architecture

```
Connectors → Processing → Database (SQLite) → Contracts → Dashboard (read-only)
```

- **Connectors** (`core/connectors/`) — fetch raw data (NSE/BSE archive CSVs, yfinance
  prices). All subclass `BaseConnector` (`core/connectors/base.py`): one `fetch(resource,
  **params)` method returning a normalized DataFrame, with retry/backoff built in.
- **Pipelines** (`core/pipelines/`) — one file per data domain (deals, FII/DII, corp
  actions, results, price/technicals). Each follows **EXTRACT → TRANSFORM → VALIDATE →
  STORE**: fetch via connector(s), enrich via `core/processing/transforms.py`, validate/
  quarantine bad rows via `core/processing/validators.py` (rejects go to a dead-letter
  table, they never silently disappear), then dedup-upsert via `core/db/repository.py`.
  Every pipeline run is wrapped in a job record (`repo.start_job` / `repo.finish_job`)
  for auditability.
- **Processing** (`core/processing/`) — shared, stateless rule logic: technicals
  (SMA/RS/52-week range), event classification, results classification, sector mapping,
  symbol master resolution. This is where "rule-based, not ML" actually lives.
- **Database** — local SQLite at `data_store/market.db` (SQLAlchemy models in
  `core/db/models.py`, engine/session in `core/db/engine.py`). Override with
  `MID_DATABASE_URL` env var (e.g. for a future Postgres backend).
- **Contracts** (`data/contracts.py`) — the **only** read bridge between the DB and the
  UI. All `st.cache_data`-decorated getters live here, including the "Daily Opportunity
  Hub" derivation (`opportunity_hub()`), which computes priority (A/B/C), action
  (Ready/Research/Watch/Avoid), and a plain-English "why not" — all as pure functions
  over already-computed fields (`_conditions`, `_priority`, `_action` etc. in that file).
  This derivation is display-only re-ranking; it introduces no new data or scoring.
- **Dashboard** (`app.py`, `pages/`, `components.py`) — Streamlit pages. Strictly
  read-only: pages call `data/contracts.py` getters and render; they never touch
  connectors, pipelines, or the DB directly. Adding a page = one import + one line in
  the `PAGES` dict in `app.py`.

### Central configuration (`core/config.py`)

Every tunable threshold — watchlist trigger sizes, technical bands (SMA period, RS
strong/weak %, 52-week breakout distance), sector index/basket mappings, corporate-action
keyword rules and impact/priority tags, results growth thresholds — lives in this one
file. When asked to tune behavior ("make RS stricter", "add a new corporate-action
keyword"), this is almost always the file to change, not the processing logic.

Corporate-action classification (`EVENT_TYPE_RULES`) is an **ordered** list of
(event_type, keywords) — the first matching keyword wins, so order matters for
overlapping phrases (e.g. "rights"/"preferential" must be checked before a generic
"fund rais" match).

### Offline mode

`OFFLINE_MODE` (env `MID_OFFLINE`, default `"1"`) makes connectors skip the network and
return deterministic seeded data (`seed/seed_data.py`, `data/sample_data.py`) instead.
This is the default so the pipeline always runs reproducibly without live credentials;
set `MID_OFFLINE=0` to attempt real NSE/BSE/yfinance fetches (falling back to seed data
on failure).

### V1 vs. V2 — two isolated subsystems, one dashboard

`intelligence_v2/` is a second-generation subsystem (Sector Intelligence, Market Cycle
classification) built as a **deliberately isolated add-on**, not a replacement:

- It has its own database (`data_store/market_v2.db`), own config, own logger
  (`logs/v2_backend.log`), own settings (`intelligence_v2/config/settings.py`) — nothing
  in `intelligence_v2/` imports from `core.*` (V1), by design.
- The **only** place V2 is permitted to touch V1's database is
  `intelligence_v2/database/v1_reference.py`, and only read-only. This isn't just a
  convention: the connection is opened with SQLite's `file:...?mode=ro` URI, so any
  write attempt fails at the SQLite/OS level regardless of what calling code asks for.
  `verify_read_only()` in that module actively proves this by attempting (and expecting
  the rejection of) a `CREATE TABLE` through the bridge.
- V2 pipelines (`run_v2_sector_intelligence.py`, `run_v2_market_cycle.py`) read V1 data
  as their primary input (e.g. V1's `sector_rotation` table) but only ever write to
  `market_v2.db`. `run_v2_sector_intelligence.py` must run before `run_v2_market_cycle.py`.
- V2 pages (`intelligence_v2/pages/`) are wired into the same `app.py` `PAGES` dict as
  V1 pages — from the user's perspective it's one dashboard, but the codebases and data
  stores never mix.
- If you touch `intelligence_v2/`, do not add a `core.*` import — keep the isolation
  boundary intact. If you touch `core/db/models.py` schema, it has no effect on
  `market_v2.db` and vice versa.

### Reports

`run_combined.py`, `run_corp_actions.py`, `run_institutional.py`, `run_results.py`, and
`run_validation.py` each also write dated markdown/CSV reports into `reports/` (via
`core/reports.py`) as a side effect — these are generated artifacts, not source, and are
overwritten/added to on each run rather than hand-edited.
