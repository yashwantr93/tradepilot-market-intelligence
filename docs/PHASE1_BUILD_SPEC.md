# Phase 1 — Build Specification (Revised)
### Indian Market Intelligence Dashboard · V2 Data Integration

> **Engineering blueprint only. No implementation code. No dashboard UI changes.**
> **Phase 1 scope (revised):** *Data Ingestion · Storage · Validation · Daily Watchlist Generation (rule-based).*
> **The Scoring Engine has been moved to Phase 3** — it requires the §SCORING_VALIDATION_FRAMEWORK gate to pass first. Phase 1 deliberately ships **no predictive scores**; it produces a transparent, rule-based watchlist from raw facts only.
> Principle carried from the V2 plan: *the dashboard reads only from the DB via standardized contracts; it never knows where data comes from.*

**Phase 1 modules:** Market Overview · FII/DII Activity · Bulk Deals · Block Deals.

### Why scoring moved out
The Validation Framework proved we must **ingest history → validate factors → then score**. Building a scoring engine before factors are proven would violate the project's own guardrail ("don't build a dashboard around metrics that don't improve decisions"). So Phase 1 becomes a clean, execution-focused **data + facts** layer. The watchlist it generates uses only **deterministic, explainable rules** (thresholds on real values), not weighted scores.

```
Phase 1: Ingest → Store → Validate → Rule-based Watchlist      ← THIS DOC
Phase 2: Corporate Actions + Insider Trading ingestion
Phase 3: Scoring Engine (after validation passes) + score-driven Stock Radar
```

---

## A. Deliverable 1 — Folder Structure

```
market_intelligence_dashboard/
├── app.py                     # UNCHANGED (V1 UI)
├── components.py              # UNCHANGED
├── pages/                     # UNCHANGED
│
├── data/
│   ├── __init__.py
│   ├── sample_data.py         # KEPT as fallback (USE_SAMPLE_DATA flag)
│   └── contracts.py           # NEW: read API the UI calls (same signatures as sample_data)
│
├── core/                      # NEW — backend engine (NO Streamlit imports anywhere here)
│   ├── __init__.py
│   ├── config.py              # env, secrets, USE_SAMPLE_DATA, thresholds
│   ├── db/
│   │   ├── __init__.py
│   │   ├── engine.py          # SQLAlchemy engine/session factory
│   │   ├── models.py          # ORM table definitions
│   │   └── repository.py      # typed read/write helpers (upserts, queries)
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseConnector (abstract)
│   │   ├── kite_connector.py
│   │   ├── nse_connector.py
│   │   ├── bse_connector.py
│   │   └── nsdl_connector.py
│   ├── pipelines/             # E-T-V-L orchestration per module
│   │   ├── __init__.py
│   │   ├── market_overview_pipeline.py
│   │   ├── fii_dii_pipeline.py
│   │   ├── bulk_deals_pipeline.py
│   │   └── block_deals_pipeline.py
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── symbol_master.py   # ISIN ↔ NSE ↔ BSE ↔ name mapping
│   │   ├── transforms.py      # cleaning, derived metrics
│   │   └── validators.py      # pandera/pydantic schemas + DQ rules
│   ├── watchlist/             # NEW (replaces scoring/ in Phase 1)
│   │   ├── __init__.py
│   │   └── rules.py           # deterministic rule-based watchlist builder
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       ├── retry.py           # tenacity wrappers / circuit breaker
│       └── timeutils.py       # IST calendar, market-hours helpers
│
├── jobs/
│   ├── __init__.py
│   ├── scheduler.py           # APScheduler registration
│   └── runners.py             # thin callables the scheduler invokes
│
├── docs/
│   ├── V2_DATA_INTEGRATION_PLAN.md
│   ├── PHASE1_BUILD_SPEC.md           # this file
│   └── SCORING_VALIDATION_FRAMEWORK.md
│
├── data_store/
│   └── market.db              # SQLite (gitignored)
├── logs/                      # rotating logs (gitignored)
└── requirements.txt
```

> Note: there is **no `core/scoring/` in Phase 1**. That folder arrives in Phase 3. `core/watchlist/rules.py` is intentionally simple — pure threshold logic, no weights.

**Key boundary:** `core/` and `jobs/` never import Streamlit. `pages/` never imports `core/` — it only calls `data/contracts.py`, which returns the exact shapes `sample_data.py` returns today.

---

## B. Module Data Sources

| Module | Exact Source | Access Method | Update Frequency |
|---|---|---|---|
| **Market Overview** | Kite Connect: `quote()` / `ltp()` / `historical_data()` for NSE indices (NIFTY 50, BANK, MIDCAP 100, SMLCAP 100, INDIA VIX) + constituent quotes for breadth. Fallback: NSE indices JSON / `yfinance`. | Official REST API (token-auth). Breadth, sector %, S/R derived in Processing. | Intraday snapshot every **3 min** (09:15–15:30 IST); historical once pre-market. |
| **FII/DII Activity** | NSE provisional FII/DII cash figures (daily); cross-check vs NSDL. | Daily CSV/JSON download. | **Once daily**, EOD ~18:30–19:00 IST. |
| **Bulk Deals** | NSE + BSE bulk-deals reports. | Official **CSV download** (date-parametrized). | **Once daily**, EOD ~18:30 IST. |
| **Block Deals** | NSE + BSE block-deals reports. | Official **CSV download** (date-parametrized). | **Once daily**, EOD ~18:30 IST. |

---

## C. Deliverable 2 — Table Schema Design

SQLAlchemy, dialect-agnostic (SQLite→Postgres = config change). Timestamps stored UTC, converted to IST at the edges. `created_at`/`updated_at` implied on every table.

### C.1 `symbol_master`
| Column | Type | Notes |
|---|---|---|
| `isin` | TEXT | **PK** |
| `nse_symbol` | TEXT | indexed |
| `bse_code` | TEXT | indexed |
| `company_name` | TEXT | |
| `sector` | TEXT | |
| `instrument_token` | INTEGER | Kite token, indexed |
| `is_active` | BOOLEAN | |
- **PK:** `isin` · **Indexes:** `nse_symbol`, `bse_code`, `instrument_token`

### C.2 `index_snapshot`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | **PK** |
| `index_name` | TEXT | |
| `ts` | DATETIME | UTC |
| `last` / `prev_close` / `change` / `pct_change` | REAL | |
| `day_open` / `day_high` / `day_low` | REAL | |
- **PK:** `id` · **Unique:** (`index_name`,`ts`) · **Index:** (`index_name`,`ts` desc)

### C.3 `market_breadth`
| Column | Type | Notes |
|---|---|---|
| `trade_date` | DATE | **PK** |
| `ts` | DATETIME | |
| `advances` / `declines` / `unchanged` / `total` | INTEGER | |
| `breadth_pct` | REAL | adv/(adv+dec)·100 |
- **PK:** `trade_date`

### C.4 `sector_performance`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | **PK** |
| `trade_date` | DATE | |
| `ts` | DATETIME | |
| `sector` | TEXT | |
| `pct_change` | REAL | |
- **PK:** `id` · **Unique:** (`trade_date`,`sector`) · **Index:** `trade_date`

### C.5 `support_resistance`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | **PK** |
| `index_name` | TEXT | |
| `trade_date` | DATE | |
| `s1` / `s2` / `r1` / `r2` | REAL | pivots |
- **PK:** `id` · **Unique:** (`index_name`,`trade_date`)

### C.6 `index_ohlc_history`
| Column | Type | Notes |
|---|---|---|
| `index_name` | TEXT | part of **PK** |
| `trade_date` | DATE | part of **PK** |
| `open`/`high`/`low`/`close` | REAL | |
| `sma20`/`sma50`/`sma200` | REAL | precomputed nightly |
- **PK:** (`index_name`,`trade_date`) · **Index:** (`index_name`,`trade_date` desc)

### C.7 `fii_dii_activity`
| Column | Type | Notes |
|---|---|---|
| `trade_date` | DATE | part of **PK** |
| `segment` | TEXT | 'CASH' (extensible) |
| `fii_buy`/`fii_sell`/`fii_net` | REAL | ₹ Cr |
| `dii_buy`/`dii_sell`/`dii_net` | REAL | ₹ Cr |
| `source` | TEXT | NSE/NSDL |
- **PK:** (`trade_date`,`segment`)

### C.8 `bulk_deals` / C.9 `block_deals` (identical schema, two tables)
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | **PK** |
| `trade_date` | DATE | |
| `exchange` | TEXT | NSE/BSE |
| `symbol` | TEXT | |
| `isin` | TEXT | FK → symbol_master |
| `client_name` | TEXT | buyer/seller |
| `txn_type` | TEXT | BUY/SELL |
| `quantity` | INTEGER | |
| `price` | REAL | |
| `value` | REAL | qty·price (₹) |
| `dedupe_hash` | TEXT | hash of natural key |
- **PK:** `id` · **Unique:** `dedupe_hash` · **Indexes:** (`trade_date`), (`symbol`,`trade_date`)
- *Natural key:* (`exchange`,`trade_date`,`symbol`,`client_name`,`txn_type`,`quantity`,`price`)

### C.10 Operational + Watchlist tables *(scoring tables removed)*
**`daily_watchlist`** — Phase 1 output (rule-based, no scores):
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | **PK** |
| `trade_date` | DATE | |
| `symbol` | TEXT | |
| `isin` | TEXT | FK |
| `reasons` | TEXT (JSON) | list of triggered rule tags, e.g. `["BIG_BULK_BUY","TOP_SECTOR"]` |
| `deal_value` | REAL | supporting raw value (₹) |
| `net_qty` | INTEGER | net BUY−SELL qty that day |
| `sector` | TEXT | |
| `rule_count` | INTEGER | how many rules fired (sort key, NOT a score) |
- **PK:** `id` · **Unique:** (`trade_date`,`symbol`) · **Index:** `trade_date`

**`job_runs`** — `id` PK, `job_name`, `source`, `started_at`, `finished_at`, `duration_s`, `rows_in`, `rows_out`, `status`, `error`. (Powers Data-Health.)
**`dead_letter`** — `id` PK, `source`, `payload_json`, `reason`, `ts`. (Quarantine for invalid rows.)

> **Removed from Phase 1:** the `scores_market` table. It returns in Phase 3 with the Scoring Engine.

---

## D. Deliverable — Data Pipeline (per module)

Generic flow — note the final step is **FLAG (watchlist rules)**, not Score:

```
SOURCE ──▶ EXTRACT ──▶ TRANSFORM ──▶ VALIDATE ──▶ STORE ──▶ FLAG ──▶ DASHBOARD
 (API/CSV) (connector)  (normalize)  (DQ rules)  (upsert)  (rules) (contracts.py)
```

**Market Overview** — Extract index + constituent quotes (3-min) + EOD historical → Transform (change/%, breadth, sector %, pivots, SMAs) → Validate (price>0, %±20% sanity, breadth reconciles, ≥4/5 indices) → Store (`index_snapshot`, `market_breadth`, `sector_performance`, `support_resistance`, `index_ohlc_history`) → Dashboard. *(No scoring; sector list feeds the watchlist TOP_SECTOR rule.)*

**FII/DII** — Extract daily CSV → compute nets → Validate (buy/sell≥0, net=buy−sell, trading day) → upsert `fii_dii_activity` → Dashboard.

**Bulk/Block Deals** — Extract NSE+BSE CSVs → normalize, map ISIN, compute value, build dedupe_hash → Validate (qty>0, price>0, valid symbol, txn∈{BUY,SELL}) → upsert (dedupe) → **FLAG** (feeds deal-based watchlist rules) → Dashboard.

---

## E. Deliverable 3 — Connector Architecture

```
BaseConnector (abstract)
├── KiteConnector     → indices, quotes, historical, instrument master
├── NSEConnector      → FII/DII, bulk deals, block deals, indices fallback, breadth
├── BSEConnector      → bulk deals, block deals (cross-source)
└── NSDLConnector     → FII/FPI flow cross-check
```

**`BaseConnector` interface:** `name`/`source_type` props · `connect()` · `health_check()` · `fetch(resource, **params) -> pd.DataFrame` (single normalized entry point; returns documented columns or raises `ConnectorError`). Built-in: retry+backoff, rate-limiting, `requests-cache`, circuit-breaker, structured logging, raw-payload capture for dead-letter. **Connectors fetch + normalize only — no business logic.**

| Class | Responsibilities | Auth | Reliability |
|---|---|---|---|
| **KiteConnector** | Index/stock quotes, LTP, historical OHLC, instrument dump → symbol_master tokens. Primary price source. | API key + daily access token | 9 |
| **NSEConnector** | FII/DII, bulk/block CSVs, breadth, index fallback. Cookie-primed session + UA headers. | Session priming | 5–6 |
| **BSEConnector** | BSE bulk/block deals; corroborates NSE. | None | 6 |
| **NSDLConnector** | FII/FPI flow cross-validation. | None | 7 |

---

## F. Deliverable 4 — Scheduler Architecture

Engine: **APScheduler** (in-process), IST, trading-calendar aware (skip weekends/holidays). Every job wraps in `job_runs` logging + circuit-breaker check.

| Job | Trigger (IST) | Steps | Depends on |
|---|---|---|---|
| **Pre-Market** | 08:00 Mon–Fri | Refresh Kite token → instrument dump → rebuild `symbol_master` → load prior-day OHLC → compute SMAs & pivots (S/R) | — |
| **Intraday** | every 3 min, 09:15–15:30 | Market Overview extract→transform→validate→store | Pre-Market |
| **Post-Market** | 18:30 Mon–Fri | FII/DII + Bulk + Block deals extract→…→store | trading day complete |
| **Nightly Processing** | 19:30 Mon–Fri | **Build `daily_watchlist` (rule engine)** + data-quality summary + archive snapshots + log rotation | Post-Market |

**Dependency rule:** Nightly waits for Post-Market success; Intraday waits for Pre-Market success. Enforced via `job_runs` status — a missing/failed prerequisite → skip + alert, never run on stale inputs.

> Change from prior version: the Nightly job no longer computes scores. It now only assembles the **rule-based watchlist** and runs housekeeping. Scoring is added to this slot in Phase 3.

---

## G. Deliverable — Data Quality Rules

| Rule | Detection | Handling |
|---|---|---|
| **Missing values** | Required column null | Row → `dead_letter`; empty whole feed → abort job, keep last-good, alert |
| **Duplicate records** | `dedupe_hash` / unique collision | Idempotent **upsert** — deals never double-count |
| **Invalid symbols** | Not resolvable in `symbol_master` | Try ISIN/fuzzy map; else `dead_letter` + exclude from watchlist |
| **Out-of-range** | price≤0, qty≤0, \|%chg\|>20%, net≠buy−sell | Reject → `dead_letter` |
| **Delayed/stale** | `max(ts)` older than SLA (intraday>10 min; EOD missing by 20:00) | Serve last-good + `is_stale` flag in contract; alert |
| **Source outage** | N consecutive connector failures | Circuit breaker opens → cooldown, fall back (NSE→yfinance), mark `source_health=degraded` |
| **Partial index set** | <4/5 indices | Store what arrived, flag incomplete, retry next cycle |

---

## H. Deliverable 5 — Daily Watchlist Generation (rule-based) *(replaces Scoring Engine in Phase 1)*

The Phase 1 watchlist is **100% deterministic and explainable** — threshold rules on raw, verified values. No weights, no composite scores, no predictive claims. Every entry shows *exactly which rule fired and the number behind it*. This is intentionally a placeholder that the Phase 3 Scoring Engine will later refine — but it is genuinely useful on day one and carries zero validation risk.

**Rule set (all thresholds live in `config.py`, easily tuned):**

| Rule tag | Condition | Source |
|---|---|---|
| `BIG_BULK_BUY` | Net BUY value in bulk deals ≥ ₹**X** Cr (default 10) for a symbol that day | `bulk_deals` |
| `BIG_BLOCK_BUY` | Net BUY value in block deals ≥ ₹**X** Cr (default 25) | `block_deals` |
| `MARQUEE_BUYER` | Any BUY deal by a name on the configurable marquee buyer list | bulk+block |
| `REPEAT_BUYING` | Symbol has net BUY deals on ≥ **2** of last **5** sessions | bulk+block history |
| `TOP_SECTOR` | Symbol's sector is in the top-**2** performing sectors today | `sector_performance` |
| `NET_SELL_FLAG` | Net SELL value ≥ ₹**X** Cr (shown as a *caution* tag, not removed) | bulk+block |

**Assembly logic (no scoring — just set logic + sort):**
```
candidates = union of all symbols that fired ≥1 BUY-side rule today
for each candidate:
    reasons   = list of fired rule tags
    rule_count = len(BUY-side reasons)        # used ONLY for display sort
    attach supporting raw values (deal_value, net_qty, sector)
watchlist = candidates sorted by (rule_count desc, deal_value desc)
write → daily_watchlist
```

**What this is NOT:** it is not a prediction or a "score 0–100." `rule_count` is a transparency/sort field, never a quality score. When the Scoring Engine lands in Phase 3 (post-validation), it *augments* this watchlist with proven, weighted signals — the rule tags remain as the human-readable "why."

---

## I. Deliverable 6 — Dashboard Data Contracts

The UI calls **only** `data/contracts.py`, returning the **exact shapes V1 already consumes** (so `pages/*` stay unchanged), wrapped in a freshness envelope. `contracts.py` reads the DB; if `USE_SAMPLE_DATA=True` or DB is empty/stale-beyond-grace, it falls back to `sample_data.py`.

**Envelope:**
```json
{ "data": <payload>,
  "meta": { "as_of": "2026-06-23T15:30:00+05:30", "source": "live|sample",
            "is_stale": false, "freshness_s": 42 } }
```

### Market Overview contracts (unchanged signatures)
- `get_index_snapshot()` → DataFrame `[Index, Last, Change, % Change]`
- `get_market_breadth()` → dict `{advances, declines, unchanged, total, breadth_pct}`
- `get_market_sentiment()` → dict `{score, label, color}` — **Phase 1: derived from breadth only** (simple deterministic map of `breadth_pct` → label/color), *not* from a scoring engine. Upgraded to Market Health in Phase 3.
- `get_advance_decline_history()` → DataFrame `[Date, Advances, Declines]`
- `get_sector_performance()` → DataFrame `[Sector, % Change]`
- `get_support_resistance()` → DataFrame `[Index, S2, S1, R1, R2]`

### New contracts (backend populated now; ready for future tabs)
```json
// get_fii_dii_activity() → list
[{ "trade_date":"2026-06-23","fii_net":-1240.5,"dii_net":2110.3,
   "fii_buy":12450.0,"fii_sell":13690.5,"dii_buy":9800.0,"dii_sell":7689.7 }]

// get_deals(kind="bulk"|"block") → list
[{ "trade_date":"2026-06-23","exchange":"NSE","symbol":"TATAMOTORS",
   "client_name":"<fund>","txn_type":"BUY","quantity":1500000,
   "price":985.4,"value":1478100000 }]

// get_watchlist() → list (rule-based, NO score field)
[{ "trade_date":"2026-06-23","symbol":"TATAMOTORS","sector":"Auto",
   "reasons":["BIG_BULK_BUY","TOP_SECTOR"],"deal_value":1478100000,
   "net_qty":1500000,"rule_count":2 }]
```
> **Removed:** `get_scores()`. Returns in Phase 3.

**Contract guarantees:** stable keys/dtypes, documented sort order, never raises to the UI (returns empty payload + `is_stale=true` on failure). This is the firewall that keeps the dashboard ignorant of sources.

---

## J. Build readiness

### Status: **Phase 1 — READY (with one input pending)**

Removing the Scoring Engine cleared the heaviest blockers (scoring weights, validation dependency). Phase 1 is now a focused data-engineering build.

**Remaining hard input (not a code blocker — has a default):**
1. **Kite Connect access** — paid subscription + API key/secret + daily access-token flow. *Recommended.* If deferred, Market Overview runs on NSE/`yfinance` fallback at lower reliability. **Build can start either way** (connector is swappable).

**Soft decisions (sensible defaults exist — approve or tune later):**
2. **Watchlist thresholds** (§H: bulk ₹10 Cr, block ₹25 Cr, top-2 sectors, 2-of-5 repeat) — tune in `config.py`, no code change.
3. **Marquee buyer list** — optional for Phase 1 (the `MARQUEE_BUYER` rule simply doesn't fire until provided). Ships with a small default.
4. **SQLite for Phase 1** — recommended; no action needed.
5. **Trading-holiday calendar** — hardcode NSE 2026 list or fetch.

**No blockers on:** folder structure, schemas, connector interface, pipelines, DQ rules, watchlist rules, data contracts — all finalized.

### Recommended build order
```
1. core/db (engine, models, repository)        ← foundation
2. core/processing/symbol_master               ← the join key for everything
3. core/connectors/base + KiteConnector        ← prove ingestion end-to-end
4. Market Overview pipeline → contracts wired to live data
5. NSE/BSE connectors → FII/DII + Bulk + Block pipelines
6. core/watchlist/rules + daily_watchlist table
7. jobs/scheduler (Pre / Intraday / Post / Nightly)
8. DQ rules + job_runs/dead_letter + staleness flags
```

---

## Phase 1 Ready / Not Ready

### ✅ **Phase 1 READY**

Implementation can begin. The single pending item (Kite credentials) does **not** block the start — the build proceeds on the data layer (`core/db` → `symbol_master` → `BaseConnector`) and swaps in Kite when credentials arrive, falling back to NSE/`yfinance` until then.

**Remaining items before/while coding (none are stop-blockers):**
- [ ] Kite Connect subscription + credentials *(or accept NSE/yfinance fallback)*
- [ ] Approve / tune watchlist thresholds in `config.py` *(defaults provided)*
- [ ] Provide marquee buyer seed list *(optional; rule stays dormant until then)*
- [ ] Confirm SQLite for Phase 1 *(recommended default)*
- [ ] Provide NSE 2026 holiday list *(or accept hardcoded default)*

**Deferred to later phases:** Scoring Engine + `scores_market` + `get_scores()` → **Phase 3** (after the Validation Framework gate passes).
```
