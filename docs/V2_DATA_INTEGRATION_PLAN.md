# V2 — Data Integration & Architecture Plan
### Indian Market Intelligence Dashboard

> **Scope of this document:** architecture, data sources, scalability, maintainability and a phased roadmap.
> **No application code** — this is the blueprint that V2 implementation will follow.
> **Status:** V1 (UI skeleton, sample data) complete. This plan converts it into a live intelligence system.

---

## 0. Guiding principles

1. **Kite Connect is the backbone for prices/quotes/historical.** You already trade on Zerodha and have a Kite connection available, so it is the most reliable, lowest-friction source for real-time and historical OHLC. Everything price-driven should route through it.
2. **The dashboard never calls a live source synchronously.** Scheduled jobs pull → store in DB → dashboard reads from DB. This keeps the UI fast, resilient, and immune to source outages during market hours.
3. **Every source sits behind a connector with a common interface.** Sources break, change layout, or get rate-limited. Swapping one out must never touch the dashboard.
4. **Degrade gracefully.** Stale-but-labelled data beats a broken page.

---

## 1. Module-by-Module Source Matrix

Legend — **Cost:** Free / Paid / Freemium · **Method:** Official API / Unofficial JSON / CSV download / Web scrape / RSS / Derived (computed internally) · **Reliability:** 1 (fragile) – 10 (rock solid) · **Difficulty:** Low / Medium / High.

| Module | Best Source(s) | Cost | Collection Method | Refresh Frequency | Rate Limits / Restrictions | Reliability | Implementation Difficulty |
|---|---|---|---|---|---|---|---|
| **Market Overview** (indices, VIX, breadth, sectors, S/R) | **Kite Connect** (primary); NSE indices JSON / `yfinance` (`^NSEI`, `^NSEBANK`, `^INDIAVIX`) as fallback | Paid (Kite ₹2k/mo) / Free fallback | Official API (Kite) + Unofficial JSON (NSE) + Derived (breadth, S/R) | Intraday 1–5 min (market hours) | Kite: ~3 req/s, 200 instruments/quote call. NSE JSON: IP-blocks, needs headers+cookies | **9** (Kite) / 5 (NSE) | **Low–Medium** |
| **Corporate Actions** (buyback, bonus, split, dividend, rights, QIP, M&A, orders) | **BSE** corporate announcements API + RSS; **NSE** corp-actions/announcements | Free | API + RSS + Web scrape (free-text parsing) | Hourly (intraday) + EOD | NSE throttles; BSE more lenient; announcements are free-text → need NLP/keyword classification | 6 (BSE) / 5 (NSE) | **Medium** |
| **Results Tracker** (revenue/profit growth, margins, beat/miss) | **screener.in** (fundamentals); BSE/NSE results filings; **Trendlyne/Tickertape** for consensus estimates | Freemium (screener) / Paid (estimates) | Web scrape + CSV; estimates require paid feed | Daily + heavy during results season | screener ToS limits scraping; **beat/miss needs analyst consensus = paid** (Refinitiv/Trendlyne) | 6 | **High** |
| **FII/DII Activity** | **NSE provisional FII/DII** (daily); **NSDL** FPI flows; Moneycontrol mirror | Free | CSV download / Unofficial JSON | Daily EOD (~6:00–6:30 PM) | Single daily file; low rate-limit risk | **7** | **Low–Medium** |
| **Bulk Deals** | **NSE + BSE bulk-deals** daily report | Free | Official CSV download | Daily EOD | Official, stable schema; one file/day | **8** | **Low** |
| **Block Deals** | **NSE + BSE block-deals** daily report | Free | Official CSV download | Daily EOD | Same as bulk deals | **8** | **Low** |
| **Insider Trading** (SEBI PIT disclosures) | **NSE/BSE insider-trading** disclosure feeds | Free | CSV / Web scrape | Daily EOD | Free-text-ish; map to symbol/ISIN; volume spikes in filings | **7** | **Medium** |
| **Promoter Activity** (SAST acquisitions/disposals + pledge) | **NSE/BSE SAST disclosures**; **NSDL/CDSL** pledge data; quarterly shareholding | Free | Web scrape + CSV | SAST: daily · Pledge/holding: quarterly | Pledge only updates quarterly; SAST is event-driven & noisy | 6 | **Medium–High** |
| **Sector Rotation** | **Derived** from NSE sectoral indices (via Kite) + breadth + FII flows | Free (uses other modules) | Derived / computed (model) | Daily + intraday | Quality depends entirely on input modules | 8 | **Medium** (it is a model, not a feed) |
| **Stock Radar** (daily watchlist / high-conviction picks) | **Derived** — Scoring Engine output across all modules + technicals | Free (internal) | Derived / computed (composite score) | Daily EOD (pre-market list) + optional intraday | None external; depends on all upstream pipelines | 8 | **High** (the "brain") |

### Notes on the trickiest sources
- **NSE unofficial JSON:** No official public API. Endpoints work but require a browser-like session (User-Agent + cookies primed by hitting the homepage first), break without notice, and block aggressive IPs. Wrap in libraries like `jugaad-data` / `nsepython` and treat as **best-effort**, never critical-path.
- **Beat / In-Line / Missed** classification is the single hardest data point — it needs **analyst consensus estimates**, which are paid. V2 can ship a *proxy*: classify on **YoY + QoQ growth thresholds + guidance tone** until a consensus feed is budgeted.
- **screener.in** has no official API; scraping is tolerated lightly but rate-limit yourself and cache hard. A paid alternative is **Tickertape/Trendlyne**.

---

## 2. What can go live *immediately* vs later

| Tier | Modules | Why |
|---|---|---|
| **Immediate (low friction, official data)** | Market Overview (via Kite), Bulk Deals, Block Deals, FII/DII | Official APIs/CSVs, stable schemas, you already have Kite |
| **Short-term (medium parsing effort)** | Corporate Actions, Insider Trading | Free but need text parsing + classification |
| **Medium-term (high effort / partial data)** | Results Tracker (proxy beat/miss), Promoter Activity | Fundamentals scraping + quarterly/event data |
| **Last (depends on everything above)** | Sector Rotation, Stock Radar | Derived models — only as good as their inputs |

---

## 3. Target Architecture

```
                ┌──────────────────────────────────────────────┐
                │                 SCHEDULER                      │
                │  APScheduler (V2) → Prefect/Airflow (later)    │
                │  pre-market · intraday · EOD · weekly jobs     │
                └───────────────────────┬──────────────────────┘
                                        │ triggers
                                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 1. DATA LAYER  (connectors / adapters — one per source)                 │
│    KiteConnector · NSEConnector · BSEConnector · ScreenerConnector ...   │
│    • common interface: fetch() -> normalized DataFrame                   │
│    • retries, rate-limiting, session handling per source                 │
│    • writes RAW/STAGING tables (append-only, audit trail)                │
└───────────────────────────────┬───────────────────────────────────────┘
                                 ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 2. PROCESSING LAYER                                                      │
│    • cleaning, dedup, type coercion, timezone normalization             │
│    • SYMBOL MASTER mapping (ISIN ↔ NSE symbol ↔ BSE code ↔ name)         │
│    • derived metrics: adv/decline, sector returns, deltas, % changes    │
│    • announcement classification (keyword/NLP)                          │
│    • schema validation (pandera/pydantic) → CURATED tables              │
└───────────────────────────────┬───────────────────────────────────────┘
                                 ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 3. SCORING ENGINE                                                       │
│    • per-stock signal scores: corporate-action impact, results,         │
│      smart-money (deals/FII/insider/promoter), technical                │
│    • weighted composite "conviction score"                              │
│    • sector-rotation signals · daily watchlist generation               │
│    • writes SCORES / WATCHLIST / SIGNALS tables                         │
└───────────────────────────────┬───────────────────────────────────────┘
                                 ▼
┌───────────────────────────────────────────────────────────────────────┐
│ 4. DASHBOARD LAYER  (Streamlit — V1 UI, now reading real data)          │
│    • reads ONLY curated/score tables (fast, no live calls)              │
│    • st.cache_data with TTL · staleness badges · drill-downs            │
└───────────────────────────────────────────────────────────────────────┘
```

### Layer responsibilities (one-line each)
- **Data Layer** — *get it in, raw and faithfully.* Each connector is dumb, isolated, and replaceable.
- **Processing Layer** — *make it clean, consistent, and joined on a single symbol master.*
- **Scoring Engine** — *turn data into opinions:* scores, ranks, watchlists, sector calls.
- **Dashboard Layer** — *present, never compute heavy or fetch live.*

The current `data/sample_data.py` becomes the **Dashboard Layer's read API** — its functions keep the same signatures but read from the DB instead of returning dummy frames. **The V1 UI does not change.**

---

## 4. Storage: SQLite vs PostgreSQL

| Factor | SQLite | PostgreSQL |
|---|---|---|
| Setup / ops | Zero (single file) | Server to run/host |
| Concurrency | Single writer (locks) | Many concurrent readers/writers |
| Time-series scale | Fine to ~GBs | Better; + **TimescaleDB** for tick/OHLC |
| Multi-user / hosted | No | Yes |
| Best for | **V2 single-user local** | Production / cloud / multi-user |

**Recommendation:**
- **Start V2 on SQLite.** Single user, local machine, zero ops — perfect for a personal dashboard.
- **Abstract all DB access through SQLAlchemy** from day one. Migration to PostgreSQL is then a connection-string change, not a rewrite.
- **Trigger to migrate to PostgreSQL:** the scheduler and the dashboard start writing/reading concurrently and you hit lock contention, OR you host it on a server, OR historical OHLC grows large (then add **TimescaleDB**).
- Keep **raw price history** (if storing ticks/minute bars) in its own table/partition so it can later move to a time-series store independently.

---

## 5. Scheduled Jobs

| Job | Cadence | Window | Sources |
|---|---|---|---|
| Symbol master refresh | Daily | Pre-market 08:00 | Kite instruments dump |
| Real-time snapshot | Every 1–5 min | Market hours 09:15–15:30 | Kite quotes/LTP (indices, watchlist) |
| Corporate announcements | Hourly | 09:00–18:00 | BSE/NSE |
| EOD deals & flows | Daily | After 18:30 | Bulk/Block deals, FII/DII, insider, SAST |
| Fundamentals/results | Daily (heavy in results season) | After 20:00 | screener / filings |
| Sector rotation + scoring + watchlist | Daily | After 19:00 (post-EOD) | internal (Scoring Engine) |
| Weekly fundamentals deep refresh | Weekly (Sun) | Off-hours | screener / shareholding |

**Tooling path:**
- **V2:** `APScheduler` in-process (or Windows Task Scheduler / cron) — simplest, no extra infra.
- **Later:** **Prefect** or **Dagster** (modern, Python-native, good retries/observability) or Airflow once you have real DAG dependencies (e.g. Scoring must wait for all EOD ingests). Prefect is the recommended next step — lightweight and dependency-aware.

---

## 6. Caching Strategy

- **DB = the primary cache** for the dashboard. The UI reads pre-computed tables, never live sources.
- **`st.cache_data(ttl=...)`** on every dashboard read (e.g. TTL 60s intraday, 1h EOD tables).
- **`requests-cache`** on connectors to dedupe identical source calls within a run and survive transient flaps.
- **In-memory LRU** for the symbol master (read constantly, changes daily).
- **Redis** only when you go multi-process / hosted (shared cache across scheduler + app). Not needed for V2.

---

## 7. Error Handling

- **Retries with exponential backoff** (`tenacity`) on every network call.
- **Per-source circuit breaker:** after N consecutive failures, skip the source for a cooldown and flag it — one dead source must not stall the whole pipeline.
- **Graceful degradation:** serve **last-known-good** data with a visible **staleness badge** (`as of <timestamp>`) rather than erroring the page.
- **Schema/data validation** (`pandera` or `pydantic`) at the Processing Layer boundary — reject/quarantine malformed rows to a **dead-letter table** instead of corrupting curated data.
- **Idempotent writes** (upsert on natural keys) so re-running a failed job is always safe.
- **Source-health table** the dashboard can surface ("NSE feed degraded").

## 8. Logging & Observability

- **Structured logging** (`loguru` or stdlib `logging` + JSON) with per-connector context.
- **Job-run metadata table:** `job_name, source, started_at, duration, rows_in, rows_out, status, error` — your audit trail and the basis for a "Data Health" panel in the dashboard.
- **Data-quality metrics:** row counts vs expected, null rates, freshness lag per module.
- **Log rotation** + retention.
- **Alerting on failure:** Telegram bot / email when a critical EOD job fails or data is stale past threshold (you already have messaging tooling available).

---

## 9. Implementation Priority & Trading-Value Ranking

Ranking blends **trading value** (how much edge it gives the daily watchlist) against **implementation difficulty** (how fast it ships reliably).

| Rank | Module | Trading Value | Difficulty | Reliability | Phase |
|---|---|---|---|---|---|
| **1** | **Market Overview** | High (context for everything) | Low | 9 | P1 |
| **2** | **FII/DII Activity** | High (macro flow direction) | Low–Med | 7 | P1 |
| **3** | **Bulk Deals** | Med–High (smart-money footprints) | Low | 8 | P1 |
| **4** | **Block Deals** | Med–High (institutional intent) | Low | 8 | P1 |
| **5** | **Corporate Actions** | High (event-driven catalysts) | Medium | 6 | P2 |
| **6** | **Insider Trading** | High (strong conviction signal) | Medium | 7 | P2 |
| **7** | **Promoter Activity** | High (buying/pledge = key tell) | Med–High | 6 | P3 |
| **8** | **Results Tracker** | Very High (but hard w/o estimates) | High | 6 | P3 |
| **9** | **Sector Rotation** | Very High (where to fish) | Medium | 8 | P4 |
| **10** | **Stock Radar** | **Highest (the end goal)** | High | 8 | P4 |

> Note: Results Tracker has the **highest raw value** but is deferred because reliable beat/miss needs a paid consensus feed; ship the **growth+guidance proxy** in P3, upgrade later.

### Phased Roadmap

**Phase 1 — Foundations + Quick Wins (Weeks 1–2)**
Build Data Layer skeleton, SQLite + SQLAlchemy, symbol master, APScheduler. Go live: **Market Overview (Kite)**, **Bulk/Block Deals**, **FII/DII**. Dashboard reads real data for these tabs.

**Phase 2 — Catalysts (Weeks 3–4)**
**Corporate Actions** + **Insider Trading** pipelines with classification. Add source-health logging + staleness badges. Harden retries/circuit breakers.

**Phase 3 — Conviction Signals (Weeks 5–6)**
**Promoter Activity** (SAST + pledge) and **Results Tracker** (growth/guidance proxy for beat/miss). Add data-quality validation.

**Phase 4 — Intelligence (Weeks 7–8)**
Build **Scoring Engine** → **Sector Rotation** model and **Stock Radar** daily watchlist. This is where modules combine into high-conviction picks — the stated goal.

**Phase 5 — Productionize (ongoing)**
Migrate to PostgreSQL/Prefect if/when concurrency or hosting demands it; add consensus-estimate feed to upgrade Results Tracker; alerting.

---

## 10. Decisions needed before P1 build

1. **Kite Connect subscription** — confirm the paid Kite Connect API (~₹2,000/mo) vs relying on free NSE/`yfinance` (lower reliability). Recommended: **subscribe** — it is the backbone.
2. **Results beat/miss** — accept the **growth+guidance proxy** for V2, or budget a paid estimates feed (Trendlyne/Refinitiv)?
3. **Hosting** — stays local (SQLite is enough) or eventually cloud-hosted (plan PostgreSQL earlier)?
```
