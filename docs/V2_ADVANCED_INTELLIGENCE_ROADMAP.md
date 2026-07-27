# V2 Roadmap — Advanced Market Intelligence
### Design Document Only · No Implementation Code

> **Status:** Architecture proposal for review. Nothing in this document has been built.
> **V1 status:** Frozen (TradePilot AI — Market Intelligence Platform). This roadmap does not touch it.

---

## 0. Non-Negotiable Boundary: V1 Isolation

Every V1 component named in the brief is treated as **read-only, untouched, and unaware that V2 exists**:

| V1 component | V2's relationship to it |
|---|---|
| Connectors (`core/connectors/`) | Never imported. V2 has its own connectors. |
| Pipelines (`core/pipelines/`) | Never imported. V2 has its own pipelines. |
| Database (`data_store/market.db`) | Never opened for writing. V2 uses a **separate file**. |
| Selection Engine (`core/watchlist/rules.py`) | Never imported or extended. |
| Priority Logic (`data/contracts.py` hub functions) | Never imported or extended. |
| Validation Engine (`core/validation/`) | Never imported or extended. V2 gets its **own** validation module. |

### 0.1 Physical isolation, not just logical

Rather than "please don't write to V1's tables," V2 gets a **separate SQLite file**: `data_store/market_v2.db`. This makes interference structurally impossible, not just a convention:

- V2 pipelines never obtain a write-handle to `market.db`.
- Where V2 needs V1 data (e.g. results classifications, corporate actions, deal records, sector trend), it opens `market.db` through a **strictly read-only connection** (SQLAlchemy engine on a `mode=ro` SQLite URI). A read-only connection cannot execute `INSERT`/`UPDATE`/`ALTER` even by accident.
- This also solves a real operational problem: V1's daily pipelines already run ~8–9 minutes with heavy writes (confirmed in production runs). A second write-heavy process sharing the same file risks `database is locked` errors. Separate files remove that risk entirely.

### 0.2 A new, separate top-level package

```
market_intelligence_dashboard/
├── core/                      # V1 — UNTOUCHED
├── data/                      # V1 contracts — UNTOUCHED
├── pages/                     # V1 dashboard pages — UNTOUCHED
│
└── intelligence_v2/           # NEW — entirely independent
    ├── config.py               # own thresholds, own SECTORS copy (not imported from V1)
    ├── db/
    │   ├── engine.py            # engine for market_v2.db
    │   ├── models.py            # new tables only
    │   ├── repository.py
    │   └── v1_reference.py      # THE ONLY file allowed to open market.db, read-only
    ├── connectors/               # new sources (see §6)
    ├── processing/                # multi-horizon calcs, state machines
    ├── pipelines/
    ├── sector_intelligence/       # Module 1
    ├── market_cycle/               # Module 2
    ├── momentum/                    # Module 3
    ├── position_trading/             # Module 4
    ├── bearish/                       # Module 5
    ├── validation_v2/                  # new, separate validation (mirrors core/validation pattern)
    └── contracts_v2.py                  # read-only bridge for new dashboard pages
```

`intelligence_v2/db/v1_reference.py` is the **single narrow door** into V1's data — every other V2 module reads V1 facts only through it, never via ad hoc imports of `core.db.repository`. This keeps the coupling auditable: one file, one purpose, read-only.

**One necessary touch to a V1 file:** `app.py`'s `PAGES` dict gets new entries for the new pages, exactly the way the Daily Opportunity Hub was added earlier — this is navigation wiring, not logic, and is the same pattern already used throughout V1's life. If you'd prefer **zero** touches to any V1 file, the alternative is a second, standalone Streamlit app (`app_v2.py`) run on a different port — flagged as a decision in §8.

### 0.3 Design philosophy carried forward

Every classification below is **deterministic and rule-based** — thresholds in config, if/else logic, no scoring, no ML, no composite weighted ranking. This continues V1's DNA rather than introducing a new paradigm. Where a percentage or count is computed (e.g. "% of last 120 sessions a sector spent in Strong state"), it is a **transparent measurement**, never blended into an opaque score.

---

## 1. MODULE 1 — Advanced Sector Rotation Intelligence

### 1.1 Architecture

```
Connectors → Processing (multi-horizon calc) → sector_intelligence_daily (append-only, V2 DB)
           → State classifier (7 states) → Contracts → Dashboard
```

Unlike V1's `sector_rotation` table (which **overwrites** a single "today" row per sector), Module 1 is **append-only** — one row per (sector, date), growing daily. This is the key structural difference: answering *"has it been leading for six months?"* requires looking back across months of stored classifications, which V1's snapshot design cannot do.

### 1.2 Data Requirements

| Need | Source | Status |
|---|---|---|
| Sector index / basket daily closes, ~2 years back | yfinance NSE sector indices (`^NSEBANK`, `^CNXIT`, etc.) — **same tickers V1 already validated live** | ✅ Proven working (V1 uses these) |
| Nifty 50 benchmark, ~2 years | yfinance `^NSEI` | ✅ Proven working |
| Sector universe definition | **Duplicated, frozen copy** of V1's 12-sector list (Banking, Financial Services, IT, Auto, Pharma, FMCG, Capital Goods, Defence, Realty, PSU, Energy, Metals) in `intelligence_v2/config.py` — not imported from `core.config` to avoid coupling | New file, same content |

No new connector needed for this module — it reuses the exact source pattern V1 already proved reliable, just with a longer lookback window (2 years vs V1's 90 days) and its own storage.

### 1.3 Processing Flow

```
1. EXTRACT   per sector: 2y daily close series (index or basket average, same
             index/proxy/basket fallback logic V1 uses — reimplemented, not imported)
2. COMPUTE   for each horizon in [1W, 1M, 3M, 6M, 1Y]:
                 sector_return   = pct change over horizon
                 nifty_return    = pct change over horizon (same dates)
                 relative_strength = sector_return − nifty_return
3. COMPUTE   momentum   = RS_1M(today) − RS_1M(20 trading days ago)   [is RS accelerating?]
             trend      = price vs 20/50/200-day SMA stack (Up / Down / Sideways)
4. COMPUTE   consistency = % of trailing 120 sessions classified "Strong Leader"
             (a transparent count, not a score — see §1.5)
5. CLASSIFY  → one of 7 states (§1.5), using today's values + recent history
6. STORE     append row to sector_intelligence_daily
7. DASHBOARD contracts_v2.py reads the latest date + trailing history for trend charts
```

### 1.4 Required Calculations

| Field | Formula |
|---|---|
| `perf_Nh` (N ∈ {1W,1M,3M,6M,1Y}) | `close[t] / close[t-N] − 1`, in % |
| `rs_Nh` | `perf_Nh(sector) − perf_Nh(nifty)` |
| `momentum_1m` | `rs_1m(t) − rs_1m(t−20d)` (rate of change of RS itself) |
| `above_20/50/200_sma` | Y/N, same style as V1 |
| `consistency_pct` | `count(state == "Strong Leader" over trailing 120d) / 120 × 100` |
| `days_in_state` | consecutive sessions in the current classification (hysteresis — see §1.5) |

### 1.5 The 7-state classification (deterministic)

To avoid single-day noise flipping a sector's label, a transition requires the condition to hold for **N consecutive sessions** (config: `min_dwell_days`, default 3) — same anti-flip-flop discipline as V1's rule engine.

| State | Rule (illustrative — exact thresholds in config) |
|---|---|
| **Strong Leader** | RS positive across 1M, 3M, **and** 6M · above 20/50/200-SMA · consistency ≥ 60% |
| **Early Momentum** | RS_1W & RS_1M strongly positive, but RS_3M/6M were flat/negative as recently as 40 sessions ago (genuine inflection) · price just reclaimed 50-SMA |
| **Improving** | RS trending up over 20–40 sessions but not yet crossing "Strong" thresholds |
| **Sideways** | RS ≈ 0 across all horizons · price oscillating around SMAs |
| **Weakening** | Was "Strong Leader" within the last 40 sessions · RS_1W/1M now negative · RS_6M still positive (rolling over, not yet broken) |
| **Downtrend** | RS negative across 1M, 3M, **and** 6M · below all major SMAs |
| **Recovery** | RS_6M/1Y still negative (long-term laggard) · RS_1M/1W turning positive · price reclaiming 20/50-SMA |

### 1.6 Dashboard Layout

**New page: "Sector Intelligence"**
- Top: 12-sector grid, one card per sector — current state (color-coded), consistency %, days-in-state.
- Multi-horizon table: Sector | 1W % | 1M % | 3M % | 6M % | 1Y % | RS(1M) | Momentum | State.
- A **"Leadership Timeline"** chart per sector (state changes over the trailing year) — this is what visually answers "strong only today, or for six months?"
- Filter: show only sectors currently in Early Momentum / Recovery (the rotation-entry signals).

### 1.7 Direct answers to the posed questions

| Question | Where it's answered |
|---|---|
| Strong only today? | `consistency_pct` low (e.g. <20%) despite today = Strong → flagged "New / Unconfirmed" |
| Leading for 6 months? | RS_6M positive **and** `consistency_pct` high (>70%) |
| Money just rotating in? | State = **Early Momentum** or a fresh Accumulation→Early-Momentum transition (Module 2) |
| Leadership ending? | State = **Weakening** |

---

## 2. MODULE 2 — Market Cycle Engine

### 2.1 Architecture

```
Module 1 outputs (RS, momentum, trend, consistency)
   → Cycle state machine (7 stages, with dwell-time + transition rules)
   → market_cycle_daily (append-only, V2 DB, per sector)
   → Contracts → Dashboard
```

Module 2 **consumes** Module 1's daily outputs (read from the V2 DB it just wrote — no V1 involvement) and layers a *cyclical* interpretation on top: not just "what is the sector doing" but "where is it in the wheel, and how long has it been there."

### 2.2 Data Requirements

No new data. Entirely derived from Module 1's stored `sector_intelligence_daily` table plus volume data already fetched during Module 1's extraction step (up-day vs down-day volume, for the Distribution/Accumulation signal).

### 2.3 Processing Flow

```
1. READ    yesterday's cycle stage + days_in_stage for the sector
2. READ    today's Module-1 outputs (RS, momentum, trend, SMA stack)
3. COMPUTE volume signal: avg volume on up-days vs down-days over trailing 20 sessions
4. EVALUATE transition rules (§2.4) against (yesterday's stage, today's conditions)
5. APPLY   hysteresis: a transition only commits after min_dwell_days confirmation
6. STORE   append (sector, date, stage, days_in_stage, prior_stage)
```

### 2.4 The 7-stage wheel (deterministic transition rules)

```
Accumulation → Early Momentum → Strong Trend → Mature Trend → Distribution → Weak Trend → Recovery → (back to Accumulation)
```

| Stage | Entry condition (from prior stage) |
|---|---|
| **Accumulation** | From Recovery/Weak Trend: price below 200-SMA but flattening, RS_6M less negative than 40 sessions ago, up-day volume beginning to exceed down-day volume |
| **Early Momentum** | From Accumulation: price reclaims 50-SMA, RS_1M/1W strongly positive, volume expansion confirmed |
| **Strong Trend** | From Early Momentum: full bullish SMA stack (20>50>200), RS positive across 1M–6M, sustained ≥ min_dwell_days |
| **Mature Trend** | From Strong Trend: SMA stack still bullish but RS momentum (§1.4) decelerating while RS itself still positive |
| **Distribution** | From Mature Trend: price near highs but RS deteriorating, down-day volume beginning to exceed up-day volume |
| **Weak Trend** | From Distribution: price breaks below 50-SMA, RS_1M negative |
| **Recovery** | From Weak Trend: RS_6M/1Y still negative but RS_1M/1W inflecting positive, price reclaiming 20-SMA → cycles back toward Accumulation |

### 2.5 Dashboard Layout

**New page: "Market Cycle"** (or a tab within Sector Intelligence)
- A **cycle wheel diagram** (7 positions) with each sector plotted at its current stage.
- Table: Sector | Current Stage | Days in Stage | Prior Stage | Transition Date.
- "Sectors that just transitioned" callout — the highest-value row, since a fresh transition is the earliest actionable signal.

---

## 3. MODULE 3 — Early Momentum Stock Detector

### 3.1 Architecture

```
Broader universe (Nifty 500) → price/volume processing → RS trend + volume trend
   → filter: above SMA stack, NOT near breakout → momentum_watchlist_daily
   → enrich (read-only): V1 results_tracker classification
   → label (Accumulation / Early Momentum) → Contracts → Dashboard
```

### 3.2 Data Requirements

| Need | Source | Status |
|---|---|---|
| Broad stock universe (~500 names) | **New connector**: NSE index-constituent archive CSV (same `archives.nseindia.com` domain/pattern already proven for bulk/block deals) | To be confirmed live at build time — same low-risk source family |
| Daily OHLCV per stock, ~1 year | yfinance | ✅ Proven pattern (V1 uses this extensively) |
| Quarterly results classification | **Read-only** from V1's `results_tracker` via `v1_reference.py` | ✅ Already exists in V1, zero new engineering |

This is the **first module that needs a broader universe than V1 ever built** — V1's Deal Flow universe is deal-driven (small/mid-cap biased) and the Institutional universe is a fixed 5-per-sector basket (~60 names). A genuine "early momentum scanner" needs to look across hundreds of names, which is why the Nifty 500 constituent connector is a prerequisite.

### 3.3 Processing Flow

```
1. EXTRACT  Nifty 500 constituent list (refreshed periodically, e.g. monthly)
2. EXTRACT  1y OHLCV per constituent (yfinance, batched)
3. COMPUTE  rs_trend      = RS_1M(today) > RS_1M(20 sessions ago)          [improving?]
4. COMPUTE  volume_trend  = avg_vol(10d) > 1.2 × avg_vol(prior 30d)         [expanding?]
5. COMPUTE  above_sma     = above 20-SMA AND above 50-SMA
6. COMPUTE  dist_52w_high = same formula V1 already uses
7. FILTER   above_sma == Y AND rs_trend == Y AND volume_trend == Y
            AND dist_52w_high BETWEEN 5% and 25%   (explicitly NOT near-breakout —
            that territory belongs to V1's Deal Flow "Ready" classification)
8. ENRICH   join V1 results_tracker (read-only) for results_status
9. LABEL    Accumulation vs Early Momentum (§3.4)
10. STORE   append to momentum_watchlist_daily
```

### 3.4 Labels

| Label | Rule |
|---|---|
| **Accumulation** | Below 200-SMA but above 20/50-SMA (early basing) · RS improving · volume improving |
| **Early Momentum** | Above full 20/50/200-SMA stack · RS improving · volume improving · still 5–25% from 52W high |

### 3.5 Dashboard Layout

**New page: "Early Momentum Scanner"**
- Table: Symbol | Sector | Label | RS Trend | Volume Trend | Dist. from 52W High | Results Status.
- Sector filter (cross-links to Module 1's Strong/Early-Momentum sectors — "show me early-momentum stocks *inside* early-momentum sectors" is the highest-conviction intersection, itself just a filter, not a new scoring layer).
- Explicit caption: *"These are NOT breakout signals. They are future breakout candidates to watch — confirm your own breakout trigger before acting."*

---

## 4. MODULE 4 — Position Trading Engine

**Completely separate from Swing (V1).** No shared tables, no shared priority logic, no shared page. A stock can appear in both V1's Opportunity Hub and this module's watchlist — that's fine and expected; they are answering different questions on different timeframes.

### 4.1 Architecture

```
Universe (Nifty 500) → Weekly/Monthly price processing (long-term trend, RS)
   → enrich (read-only): V1 results_tracker (quarterly/sales/profit growth)
   → enrich (read-only): Module 1 (sector leadership)
   → enrich (best-effort, new connector): shareholding pattern, debt, ROCE
   → position_watchlist_daily → NEW priority classifier (A/B/Watchlist) → Contracts → Dashboard
```

### 4.2 Data Requirements — and an honest reliability split

| Need | Source | Reliability |
|---|---|---|
| Weekly/monthly OHLCV, long-term trend, RS | yfinance (`interval='1wk'`/`'1mo'`) | ✅ High — same provider already proven for daily data |
| Quarterly / sales / profit growth | **Read-only** V1 `results_tracker` | ✅ High — already built, zero new engineering |
| Sector leadership | **Read-only** Module 1 output | ✅ High — new but same reliable source chain |
| Institutional ownership %, Promoter holding % | **New connector**: NSE/BSE shareholding-pattern filings (quarterly XBRL/tabular disclosures) | ⚠️ **Medium-low.** No clean CSV like bulk/block deals — these are structured filings requiring per-filing parsing, materially higher engineering effort than any V1 connector. Genuinely new work, not a reuse. |
| Debt, ROCE | yfinance `.balance_sheet` / `.financials` (best-effort) | ⚠️ **Low and inconsistent.** Works reasonably for large-caps (RELIANCE, TCS-scale), frequently **missing for mid/small-caps** — this exact gap was already flagged in the original V2 planning doc under Results Tracker (paid feeds like Screener/Trendlyne cover it better, but carry the same ToS/scraping caveats noted back then). |

**Design response to the gap:** these two fields are explicitly **Tier 2 / best-effort**. Where unavailable, the field shows **"Not Available"** (the same honest-gap pattern V1 already uses for "management guidance") rather than silently defaulting to a value that could mislead. Priority classification (§4.4) is built so that **missing Tier-2 fields degrade a stock to a lower tier, never disqualify it outright** — the engine stays useful even before the shareholding-pattern connector is built.

### 4.3 Processing Flow

```
1. EXTRACT  weekly/monthly OHLCV per Nifty-500 constituent
2. COMPUTE  long_term_trend = weekly close vs 40-week / 200-day-equivalent SMA
3. COMPUTE  rs_long = relative strength vs Nifty over 6M/1Y (reuses Module 1's math,
            recomputed at stock level — not imported from Module 1's sector code)
4. ENRICH   quarterly/sales/profit growth ← V1 results_tracker (read-only)
5. ENRICH   sector_leadership ← Module 1 (read-only, same V2 DB)
6. ENRICH   institutional_pct, promoter_pct ← new shareholding connector (or "Not Available")
7. ENRICH   debt, roce ← yfinance best-effort (or "Not Available")
8. CLASSIFY → Priority A / B / Watchlist (§4.4)
9. STORE    append to position_watchlist_daily
```

### 4.4 Priority rules (deterministic; Tier-2 gaps degrade, never disqualify)

| Tier | Rule |
|---|---|
| **Priority A** | Long-term uptrend **and** RS_long positive **and** sector leadership = Strong/Early-Momentum **and** results Strong **and** (if available) promoter holding stable/rising **and** (if available) reasonable debt/ROCE |
| **Priority B** | Long-term uptrend **and** RS_long positive **and** (sector leadership OR results Strong) — Tier-2 fields unavailable or neutral |
| **Watchlist** | Meets some but not most conditions; or a Priority-A/B candidate with a caution flag (declining promoter holding, weak results) |

### 4.5 Dashboard Layout

**New page: "Position Trading Watchlist"** (fully separate nav item, visually distinct from the Swing pages — different accent color to reinforce "different timeframe, different workflow")
- KPI row: Priority A count, Priority B count, Watchlist count.
- Table: Symbol | Sector | Sector Leadership | Long-Term Trend | RS (6M/1Y) | Sales Growth | Profit Growth | Promoter % (or "Not Available") | Debt/ROCE (or "Not Available") | Priority.
- Explicit banner: *"Position Trading — weekly/monthly timeframe. Independent from the Swing Trading watchlists."*

---

## 5. MODULE 5 — Bearish Opportunity Engine

**Completely separate short-selling engine.** F&O universe only (shorting cash-market stocks without derivatives is a different risk profile and out of scope).

### 5.1 Architecture

```
F&O universe (new connector) → weak-signal processing
   → enrich (read-only): V1 results_tracker (Weak), Module 1 (Weak sectors),
                           V1 corporate_actions (Bearish tag), V1 bulk/block deals (net sell)
   → gap-down detection (derived from OHLCV around results dates)
   → bearish_watchlist_daily → NEW short-priority classifier → Contracts → Dashboard
```

### 5.2 Data Requirements

| Need | Source | Status |
|---|---|---|
| F&O-eligible stock list | **New connector**: NSE F&O securities/lot-size archive CSV (same public-archive domain pattern) | To be confirmed live at build time |
| Daily OHLCV | yfinance | ✅ Proven |
| Weak quarterly results | **Read-only** V1 `results_tracker` (classification = Weak) | ✅ Already exists |
| Weak/Downtrend/Weakening sector | **Read-only** Module 1 | ✅ New but reliable chain |
| Negative corporate developments | **Read-only** V1 `corporate_actions` filtered `impact_tag = Bearish` | ✅ Already exists |
| Institutional selling | **Read-only** V1 `bulk_deals`/`block_deals` — **new** SELL-side classification logic lives entirely in the Bearish module (V1's `rules.py` is never touched; this just reads the same raw tables with different, new logic) | ✅ Data exists; logic is new |
| Gap Down after results | **Derived**: `open[t] vs close[t-1]` where `t` follows a results announcement date (from read-only results_tracker/corporate_actions) | ✅ Fully derivable, no new source |
| Distribution pattern | Down-day volume > up-day volume over trailing window (same technique as Module 2 §2.3) | ✅ No new source |

### 5.3 Processing Flow

```
1. EXTRACT  F&O eligible universe
2. FILTER   to F&O names only (hard gate — non-F&O names never enter this module)
3. COMPUTE  below_sma      = below 20-SMA AND below 50-SMA
4. COMPUTE  rs_weak        = RS negative vs Nifty (mirrors V1's RS calc, inverted)
5. COMPUTE  gap_down_flag  = gap down ≥ threshold within N days of a results date
6. COMPUTE  distribution   = down-volume > up-volume over trailing 20 sessions
7. ENRICH   results_status ← V1 results_tracker (read-only)
8. ENRICH   sector_status  ← Module 1 (read-only)
9. ENRICH   corp_action_bearish ← V1 corporate_actions (read-only, Bearish tag)
10. ENRICH  institutional_selling ← V1 bulk/block deals (read-only, new SELL-side rule)
11. CLASSIFY → Priority Short A / B / Watchlist / Avoid Shorts (§5.4)
12. STORE   append to bearish_watchlist_daily
```

### 5.4 Priority rules (deterministic)

| Tier | Rule |
|---|---|
| **Priority Short A** | Weak results **and** weak/downtrend sector **and** below SMA stack **and** (gap-down OR institutional selling OR bearish corporate action) |
| **Priority Short B** | Below SMA stack **and** RS weak, with only one of {weak results, weak sector, distribution} confirming |
| **Watchlist** | Below SMA stack but no confirming catalyst yet — monitor only |
| **Avoid Shorts** | Below SMA stack but results Strong, or sector Strong/Improving — technicals weak but fundamentals/sector contradict; explicitly flagged as a **trap-risk** case, not a short candidate |

The **"Avoid Shorts"** tier mirrors V1's "Avoid" philosophy exactly: it exists specifically to stop a trader from shorting a name that merely *looks* weak on price but has contradicting fundamentals — the same "why not selected" transparency principle from V1's Opportunity Hub.

### 5.5 Dashboard Layout

**New page: "Bearish Opportunities"** (distinct red/amber accent theme, clearly separated from long-side pages)
- KPI row: Priority Short A, Priority Short B, Watchlist, Avoid Shorts.
- Table: Symbol | Sector | Sector Status | Results | Gap Down? | Institutional Selling? | Corp Action | Priority.
- Same "Why" / "Do Now" style columns as V1's Opportunity Hub, reworded for shorts (e.g. "Do Now: Wait for rally to resistance before entry" / "Confirm breakdown below support with volume").
- Mandatory disclaimer banner: *"F&O short-selling carries margin and unlimited-loss risk. This module surfaces candidates for research only — position sizing and risk management are the trader's responsibility."*

---

## 6. Cross-Module Summary: New Connectors Required

| Connector | Used by | Risk/Effort | Pattern |
|---|---|---|---|
| Nifty 500 (or 200) constituent list | Modules 3, 4 | **Low** | Same `archives.nseindia.com` CSV domain already proven for bulk/block deals |
| F&O securities list | Module 5 | **Low** | Same archive-CSV pattern |
| NSE/BSE shareholding pattern (promoter/institutional %) | Module 4 (Tier 2) | **Medium-High** | Structured filing parsing, not a flat CSV — genuinely new engineering, not a reuse |
| Weekly/monthly OHLCV | Module 4 | **Low** | Same yfinance provider, different `interval` parameter |

No new connector touches V1's `core/connectors/` — all are new files under `intelligence_v2/connectors/`.

---

## 7. Integration Strategy

### 7.1 Database
Single new file `data_store/market_v2.db`, own SQLAlchemy models, own migrations. V1's `market.db` is opened **only** through `intelligence_v2/db/v1_reference.py` in read-only mode.

### 7.2 Validation (extending the evidence-based ethos, without touching V1's engine)
Per this project's established discipline (the original Scoring Validation Framework), every new classification scheme here — 7 sector states, 7 cycle stages, momentum labels, Position tiers, Short tiers — should eventually be measured the same way V1's five engines are: capture the signal, track forward returns, report win rate. Because "do not change the Validation Engine" is a hard constraint, this is built as **`intelligence_v2/validation_v2/`** — a new module that mirrors `core/validation/signal_tracker.py`'s pattern (capture → evaluate → report) but is entirely separate code, reading from `market_v2.db`. V1's validation is never imported, extended, or modified.

### 7.3 Dashboard wiring
Four new pages (Sector Intelligence, Market Cycle — or merged into one — Early Momentum Scanner, Position Trading Watchlist, Bearish Opportunities), each reading only from `intelligence_v2/contracts_v2.py`. The one touch to a V1 file is adding these entries to `app.py`'s `PAGES` dict — identical in kind to how the Opportunity Hub was added. If even that is unwanted, `app_v2.py` as a fully separate Streamlit process is the zero-touch alternative (different port, same `intelligence_v2/` backend).

### 7.4 Recommended build sequence

```
1. Module 1 (Sector Intelligence)   — foundation; Modules 2, 4, 5 all consume it
2. Module 2 (Market Cycle)          — direct extension of Module 1's outputs
3. Module 3 (Early Momentum)        — high near-term value, only needs the new
                                       Nifty-500 connector (low effort)
4. Module 5 (Bearish Engine)        — needs the F&O connector (low effort);
                                       otherwise fully reuses V1 read-only data
5. Module 4 (Position Trading)      — last, because Tier-2 fundamentals
                                       (shareholding, debt, ROCE) are the highest-
                                       effort, lowest-reliability piece; ship with
                                       "Not Available" fallbacks first, add the
                                       shareholding connector as a fast-follow
```

Modules 1–3 and 5 can realistically ship as a functioning MVP without any new *hard* data-source risk (only low-risk archive-CSV connectors). Module 4 is the one place this roadmap is asking you to accept a genuine, flagged data gap.

---

## 8. Decisions Needed Before Build

1. **Dashboard touch-point** — one new-entry edit to V1's `app.py` PAGES dict (recommended), or a fully separate `app_v2.py`?
2. **Sector/Cycle pages** — one merged "Sector Intelligence" page with a Cycle tab, or two separate pages?
3. **Module 4 fundamentals** — ship with "Not Available" fallbacks now and build the shareholding-pattern connector later (recommended), or delay Module 4 entirely until that connector exists?
4. **F&O and Nifty-500 connectors** — confirm exact NSE archive URLs live at build time (same validation step done for every V1 connector before coding it).
5. **Build order** — confirm the sequence in §7.4, or reprioritize (e.g. Bearish Engine before Early Momentum)?

---

## 9. What This Roadmap Deliberately Does Not Do

- No scoring, no ML, no composite weighted ranking anywhere.
- No modification, import, or extension of any V1 rule, table, connector, or pipeline.
- No promise that Module 4's fundamentals will be fully reliable — flagged honestly, with a graceful degrade path.
- No code. This is the design to review before any of it is built.
```
