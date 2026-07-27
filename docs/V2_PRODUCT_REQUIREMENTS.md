# TradePilot AI — V2 Product Requirements Document (PRD)
### Market Intelligence Platform

> **Status:** Documentation only. No code in this document; nothing here has been built.
> **V1 status:** Frozen and unmodified. V2 is additive — see §4.4 for how V1 folds into this PRD as the "Swing Engine."
> **Companion documents:** [V2_ADVANCED_INTELLIGENCE_ROADMAP.md](V2_ADVANCED_INTELLIGENCE_ROADMAP.md) (deep technical architecture for Sector Intelligence / Market Cycle / Position / Bearish engines) and [BRAND_GUIDELINES.md](BRAND_GUIDELINES.md) (visual identity). This PRD is the **product-definition layer** that sits above both — it defines *what* to build and *why*; the roadmap defines *how*.

---

# 1. Vision

### Who is the target user?
An **individual Indian retail trader/investor** who already has a personal trading strategy (price action, Fibonacci, 20-SMA, volume, RSI, Bollinger Bands) and needs a **daily filter** — a way to reduce 5,000+ NSE-listed stocks down to a handful of names worth actually pulling up a chart for. Not a novice looking to be told what to buy; a self-directed trader who wants their research time spent on the right 5–15 names instead of everything.

### What problems does the platform solve?
1. **Signal overload.** Bulk deals, block deals, FII/DII flows, corporate actions, quarterly results, and sector rotation all matter — but no single free source combines them, and manually checking six places every morning doesn't scale.
2. **Opaque screeners.** Most retail screener tools return a ranked list with no explanation of *why* a stock ranks where it does. TradePilot AI's core differentiator is that **every single output can be traced back to the exact rule that produced it.**
3. **Mixed timeframes in one bucket.** Ordinary screeners conflate "stock is near a 52-week high" with "stock is a good long-term hold" with "stock might be a short." TradePilot AI keeps Swing, Position, and Bearish opportunities in **structurally separate engines** so a trader never mistakes a 3-week swing setup for a 6-month position idea.
4. **No feedback loop.** Screeners rarely tell you whether their own past signals actually worked. The **Validation Dashboard** measures every engine's historical signals against real forward returns, so confidence in the system is earned, not assumed.

### How is it different from ordinary stock screeners?
| Ordinary screener | TradePilot AI |
|---|---|
| One ranked list, opaque scoring | Multiple independent engines, each fully rule-based and explainable |
| "Why is this here?" — unanswered | Every stock shows **which rule fired, which catalyst triggered it, what to verify on the chart** |
| Backtest claims (if any) are marketing copy | A dedicated Validation Dashboard tracks *this system's own* forward-return performance, visible to the user |
| Screens once, no memory | Historical Replay lets a user reconstruct exactly what the platform showed on any past date |
| Implicit "trust the model" | Explicit "Human makes the final decision" — the platform never says buy/sell |

### Long-term vision
TradePilot AI becomes the single morning stop for a rule-based Indian-market trader: one place that tells you **which sectors are leading, which stocks are moving into them, which of those fit a swing trade vs. a position trade vs. a short, and whether the system's own past calls have actually held up** — all in under five minutes, all fully explainable, none of it a black box.

---

# 2. Core Philosophy

These principles are non-negotiable design constraints, not aspirations. Every feature in §4 is checked against them before it ships.

| Principle | What it means in practice |
|---|---|
| **Rule-based** | Every classification (Priority, Action, sector state, cycle stage) is an explicit if/else threshold defined in a config file. No weighted composite scores. |
| **Explainable** | Every output carries a "why" — the specific rule(s) satisfied — not just a label. If a user can't trace a result back to a rule, it doesn't ship. |
| **No Black Box AI** | No machine learning, no probabilistic models, no neural nets, anywhere in the ranking or classification path. "AI" in the brand name is a naming choice, not a methodology (see BRAND_GUIDELINES.md §1). |
| **Evidence-driven** | Claims about what works are backed by the Validation Dashboard's forward-return tracking, not intuition. A classification scheme that fails validation gets flagged, not defended. |
| **Read-only intelligence** | The platform observes and reports. It never places orders, never stores brokerage credentials, never executes anything. Architecture: `Connectors → Processing → Database → Contracts → Dashboard`, with the dashboard layer strictly read-only. |
| **Human makes the final decision** | No feature ever renders a "Buy" or "Sell" button or label. The platform's job ends at "here is what to verify on the chart" — the trade decision is always the user's. |
| **Data before opinions** | Every number shown is either directly sourced (NSE archives, yfinance) or a transparent derived calculation with its formula documented. No field is ever a subjective judgment call presented as fact. |

---

# 3. User Journey

### A complete trading day with TradePilot AI

```
Market opens (09:15 IST)
   ↓
Platform data refresh (post-market pipelines ran the evening before;
   see run_daily.py — the platform is a pre-market research tool, not
   an intraday execution feed)
   ↓
USER CHECKS: Market Intelligence
   "What's the overall regime today? Nifty trend, breadth, FII/DII flow,
    how many sectors are Strong vs Weak?"
   ↓
USER CHECKS: Sector Intelligence
   "Which sectors are leading — and have they been leading for months,
    or is this brand new rotation? Which are just starting to turn up
    (Early Momentum / Recovery)? Which are rolling over (Weakening)?"
   ↓
USER CHECKS: Swing Opportunities  (Today's Focus, Priority A/B/C)
   "Given the sectors above, which 3-5 stocks are the highest-conviction
    swing research candidates today? What catalyst triggered each one —
    a deal, an institutional sector rotation, a corporate action, strong
    results?"
   ↓
USER CHECKS: Position Opportunities  (if looking beyond swing timeframe)
   "Which names have long-term trend + sector leadership + genuinely
    strong fundamentals, suitable for a multi-month hold?"
   ↓
USER CHECKS: Bearish Opportunities  (if hedging or looking to short)
   "Which F&O names show weak results + weak sector + broken technicals
    — and which look weak on price but are contradicted by fundamentals
    (Avoid Shorts — a trap warning, not a candidate)?"
   ↓
USER OPENS 3-5 CHARTS
   For each shortlisted name, the platform has already stated its
   "Chart Check" — the specific breakout level, volume confirmation,
   and invalidation level to verify.
   ↓
USER APPLIES THEIR OWN STRATEGY
   Price Action + Fibonacci + 20-SMA + Volume + RSI + Bollinger Bands
   — the platform does not attempt this analysis; it hands off to the
   trader's own method at exactly this point.
   ↓
TRADE DECISION
   Take the trade only if the personal-strategy setup is confirmed.
   The platform never told the user to buy or sell — it told them
   where to look and why.
```

**Post-trade (optional, ties to §4.9 Portfolio Insights):** the user can log the position in Portfolio Insights so that future daily runs flag if that holding later shows a Weak-results quarter, a sector rolling over, or an Avoid-classified technical state — a rule-based "should I still be holding this" check, not a sell signal.

---

# 4. Feature Specifications

Every module below follows the same template: **Purpose · Inputs · Outputs · Rules · Dependencies · Future Expansion.**

---

## 4.1 Market Intelligence

**Purpose.** The single macro snapshot a trader checks before anything else — is the market, in aggregate, risk-on or risk-off today, and by how much has that been true recently (not just today).

**Inputs**
- Nifty 50 / Bank Nifty daily OHLCV (yfinance — already proven reliable in V1)
- Market breadth (advances/declines across the tracked universe — reuses the same computation V1's original design used)
- FII/DII net flow (**already built in V1**, read-only reuse via `v1_reference.py`)
- Aggregate roll-up of Sector Intelligence (§4.2) and Market Cycle (§4.3) states across all 12 tracked sectors

**Outputs**
- Nifty/Bank Nifty level, change, and trend (above/below 20/50/200-SMA)
- Breadth ratio (advances / (advances+declines))
- FII/DII net (today + rolling trend, as already reported in V1's Institutional page)
- **Market Regime** classification (rule-based, not a new score): e.g. "Risk-On" when breadth > threshold AND FII/DII net positive AND majority of sectors in Strong/Improving/Early-Momentum states; "Risk-Off" on the inverse; "Mixed" otherwise
- Support/resistance levels for Nifty (pivot calculation off real OHLC — the same concept V1's original sample UI sketched, now backed by real data)

**Rules.** All thresholds (breadth cutoffs, sector-majority cutoffs for regime) live in config, deterministic, no scoring — same discipline as every other module.

**Dependencies.** Reads V1's FII/DII table (read-only) and Sector Intelligence's daily output (§4.2, itself new in V2). No new connector required.

**Future Expansion.** India VIX (or a volatility proxy) is a known data gap — no reliable free real-time source has been confirmed; flagged for future investigation, not assumed to exist.

---

## 4.2 Sector Intelligence

**Purpose.** Answer, for every one of the 12 tracked NSE sectors: is it strong only today, or has it led for six months, is money just rotating in, or is leadership ending?

**Inputs.** Sector index/basket daily closes (~2 years), Nifty benchmark closes, the same 12-sector universe already defined in V1 (Banking, Financial Services, IT, Auto, Pharma, FMCG, Capital Goods, Defence, Realty, PSU, Energy, Metals) — duplicated into V2's own config, never imported from V1.

**Outputs.** Per sector, per day (append-only history, not an overwritten snapshot): performance across 1W/1M/3M/6M/1Y, relative strength vs. Nifty, momentum (RS rate-of-change), trend (SMA stack), consistency % (share of the last 120 sessions spent in "Strong Leader"), and one of **7 states**: Strong Leader, Early Momentum, Improving, Sideways, Weakening, Downtrend, Recovery.

**Rules.** Exact thresholds and the full state-transition table are specified in [V2_ADVANCED_INTELLIGENCE_ROADMAP.md §1](V2_ADVANCED_INTELLIGENCE_ROADMAP.md#1-module-1--advanced-sector-rotation-intelligence). Transitions require multi-session confirmation (hysteresis) to avoid single-day flip-flopping — the same anti-noise discipline used everywhere else in the system.

**Dependencies.** No V1 dependency for its core calculation (reuses the same yfinance sector-index pattern V1 already validated, just with a longer lookback and its own storage). Feeds Market Intelligence (§4.1), Market Cycle (§4.3), Position Engine (§4.5), and Bearish Engine (§4.6).

**Future Expansion.** Sub-sector / thematic baskets (e.g. splitting "IT" into large-cap vs. mid-cap IT) if the 12-sector granularity proves too coarse.

---

## 4.3 Market Cycle

**Purpose.** Layer a *cyclical* read on top of Sector Intelligence — not just "what state is a sector in" but "where is it in the wheel, and how long has it been there."

**Inputs.** Sector Intelligence's own daily output (§4.2) plus up/down-day volume ratios computed during the same extraction step.

**Outputs.** Per sector, per day: one of **7 cycle stages** (Accumulation → Early Momentum → Strong Trend → Mature Trend → Distribution → Weak Trend → Recovery → back to Accumulation), days-in-current-stage, and the prior stage — enabling a "sectors that just transitioned" view, the earliest actionable rotation signal the platform can offer.

**Rules.** Full transition-condition table in [V2_ADVANCED_INTELLIGENCE_ROADMAP.md §2](V2_ADVANCED_INTELLIGENCE_ROADMAP.md#2-module-2--market-cycle-engine). Same hysteresis discipline as Sector Intelligence.

**Dependencies.** Consumes Sector Intelligence (§4.2) only — no other module, no V1 data.

**Future Expansion.** Per-stock (not just per-sector) cycle tagging, once Sector Intelligence and Market Cycle have been validated at the sector level (see §7 — validate before extending scope).

---

## 4.4 Swing Engine

**Purpose.** Identify high-quality **swing** research candidates (~1–8 week horizon). This module is not new — **it is V1 (TradePilot AI's frozen, already-shipped system), carried forward into V2's unified navigation as one branded module**, enhanced with the Early Momentum Detector.

**Inputs.** Deal Flow (bulk/block deals), Institutional Activity (FII/DII + sector rotation), Corporate Actions, Quarterly Results, Technical Confirmation (price/20-SMA/52-week range/breakout distance) — the same six independent sources already live in V1 — plus the **new** Early Momentum Detector (broader Nifty-500-scale universe scan for stocks with improving RS/volume that are *not yet* near breakout — Accumulation/Early Momentum labels, feeding candidates *into* Swing research before they become Deal-Flow/Institutional hits).

**Outputs.** Everything V1 already ships: the Combined Watchlist (Tier 1/2/3 confluence), the Daily Opportunity Hub (Priority A/B/C, Action, Setup-quality stars, Today's Focus, Why-Not explanations, Chart-Check guidance) — plus Early Momentum candidates as a new feeder list.

**Rules.** Unchanged from V1 — see V1's own `data/contracts.py` priority/action logic (frozen, not modified) — plus the new Early Momentum rules in [V2_ADVANCED_INTELLIGENCE_ROADMAP.md §3](V2_ADVANCED_INTELLIGENCE_ROADMAP.md#3-module-3--early-momentum-stock-detector).

**Dependencies.** V1's entire existing pipeline stack (read-only from V2's perspective — V2 never writes to V1's database) plus the new Nifty-500 connector required for Early Momentum's broader universe.

**Future Expansion.** Extending the six existing sources with a seventh independent signal was explicitly deferred in V1 (per the "stop adding new candidate sources" instruction that froze V1) — any seventh source is a V3+ conversation, not V2.

---

## 4.5 Position Engine

**Purpose.** A **completely separate** long-timeframe (weekly/monthly) engine for position trades — never mixed with Swing Engine tables, priority logic, or pages.

**Inputs.** Weekly/monthly OHLCV, long-term trend + RS, quarterly/sales/profit growth (read-only reuse of V1's `results_tracker`), sector leadership (read-only reuse of §4.2), and — flagged honestly — promoter/institutional holding %, debt, and ROCE, which have **no reliable free source** confirmed yet (see Roadmap §4.2's honest reliability table). These degrade to "Not Available" rather than blocking the module.

**Outputs.** Position Trading Watchlist — Priority A / Priority B / Watchlist — its own independent tiering, visually distinct (different accent) from Swing.

**Rules.** Full tier rules in [V2_ADVANCED_INTELLIGENCE_ROADMAP.md §4.4](V2_ADVANCED_INTELLIGENCE_ROADMAP.md#44-priority-rules-deterministic-tier-2-gaps-degrade-never-disqualify) — missing Tier-2 data degrades a tier, never disqualifies a stock outright.

**Dependencies.** V1's `results_tracker` (read-only), §4.2 Sector Intelligence (read-only), a new Nifty-500 connector (shared with §4.4's Early Momentum), and — as a fast-follow, not a launch blocker — a new NSE/BSE shareholding-pattern connector.

**Future Expansion.** Once the shareholding-pattern connector exists, upgrade promoter-holding tracking from "Not Available" to a real signal (e.g. flagging *declining* promoter holding as a caution, mirroring Bearish Engine's "Avoid" philosophy).

---

## 4.6 Bearish Engine

**Purpose.** A **completely separate** short-opportunity engine, F&O-universe only.

**Inputs.** F&O-eligible stock list (new connector), weak quarterly results (read-only V1 reuse), weak/downtrend sector (read-only §4.2 reuse), bearish corporate actions (read-only V1 reuse), institutional selling (read-only reuse of V1's raw bulk/block deal tables, with **new** sell-side classification logic that never touches V1's own `rules.py`), gap-down-after-results and distribution-volume patterns (both fully derivable from existing OHLCV, no new source).

**Outputs.** Priority Short A / Priority Short B / Watchlist / **Avoid Shorts** — the last tier existing specifically to warn against shorting a name that looks technically weak but is contradicted by strong fundamentals or a strong sector (the short-side mirror of Swing Engine's "Why Not Selected" transparency).

**Rules.** Full tier rules in [V2_ADVANCED_INTELLIGENCE_ROADMAP.md §5.4](V2_ADVANCED_INTELLIGENCE_ROADMAP.md#54-priority-rules-deterministic).

**Dependencies.** New F&O-list connector (low risk, same NSE-archive-CSV pattern already proven). Otherwise built almost entirely from existing V1 read-only data.

**Future Expansion.** Options-specific signals (unusual F&O OI buildup, put-call ratio shifts) — explicitly a V3+ idea (§8), not committed here.

---

## 4.7 Validation Dashboard

**Purpose.** The evidence layer — measure whether every engine's signals actually work, using real forward returns. This already exists in V1 (per-engine win rate, average/median return across 1/5/20-day horizons) and V2 **extends its coverage, without modifying V1's validation code.**

**Inputs.** V1's existing `signals` table (read-only) for Swing Engine coverage, **plus a new, separate `validation_v2` module** (mirrors V1's capture→evaluate→report pattern in new code) tracking Sector Intelligence classifications, Market Cycle stage transitions, and Position/Bearish tier assignments against their own forward outcomes.

**Outputs.** Everything V1 already shows (win rate / avg / median / best / worst by engine and horizon) **plus** new rows for each V2 classification scheme — e.g. "did a sector classified 'Early Momentum' actually outperform Nifty over the next month?", "did 'Priority Short A' names actually decline?"

**Rules.** No new rules — this module only measures, never ranks or weights. A classification scheme that fails validation is flagged for review (§2 "Evidence-driven"), not silently kept.

**Dependencies.** V1's `signals` table (read-only) and every other V2 module's daily output tables (read-only, same DB). Never imports or modifies `core/validation/`.

**Future Expansion.** Cross-engine comparison (e.g., "does Tier-1 Combined-Watchlist confluence + a Strong sector out-validate either signal alone?") once enough history has accumulated to test it honestly.

---

## 4.8 Historical Replay

**Purpose.** Let a user pick any past trading date and see **exactly** what the platform showed that day — Today's Focus, Priority A/B/C, sector states, cycle stages — as a trust-building tool ("did the system actually flag this before it moved?") and a learning tool (reviewing past setups without look-ahead bias).

**Inputs.** This is substantially a **UI feature over data that already exists**: V1's per-date tables (`daily_watchlist`, `institutional_watchlist`, `combined_watchlist`, `corporate_actions`, `results_tracker`, `signals` — all already keyed by date and preserved historically, not overwritten) plus V2's new append-only Sector Intelligence and Market Cycle tables (§4.2, §4.3), which are append-only *by design specifically to make this feature possible.*

**Outputs.** A date picker that reconstructs the full daily view — same layout as the live Dashboard/Swing/Sector pages, but reading a historical date instead of "latest."

**Rules.** None — this is a pure read/replay feature, no new classification logic.

**Dependencies.** Read-only access to every other module's dated tables (V1 via `v1_reference.py`, V2 modules directly). This is the **lowest-risk, highest-trust-value** feature in the entire PRD — no new data source, no new rule engine, just a new lens on data that already exists.

**Future Expansion.** Side-by-side "replay vs. actual outcome" overlays (e.g., show the flagged breakout level next to what price actually did over the following weeks) — a natural pairing with the Validation Dashboard.

---

## 4.9 Portfolio Insights

**Purpose.** Let a user maintain a simple list of their current holdings and get a rule-based, read-only cross-reference against everything the platform already tracks — **not** a portfolio tracker with live P&L, and explicitly **not** a broker-connected feature.

**Inputs.** A **manually maintained** holdings list — symbol, quantity, buy price, buy date — entered directly in the UI or imported from a user-provided CSV. **No brokerage API integration, no credential storage, no automatic sync** — consistent with the platform's read-only, no-execution philosophy and with the standing rule that financial credentials are never handled by this system.

**Outputs.** For each held symbol: its current Sector Intelligence state, Market Cycle stage, Swing Engine technical status, latest Results classification, and any recent Corporate Action — i.e., "is anything in my portfolio now flagged Weakening / Avoid / Weak Results" — a rule-based **review prompt**, never a sell recommendation (§2 "Human makes the final decision" applies here most directly).

**Rules.** No new classification — this module only *joins* the user's symbol list against outputs already produced by §4.2–§4.6.

**Dependencies.** Read-only joins against every other module's latest-date output. A small new local table for the user's own holdings (the only "write" in this module, and it's the user's own manually-entered data, not fetched from anywhere).

**Future Expansion.** Position-level historical Replay (§4.8) — "show me what the system said about this stock on the day I bought it." **Explicitly out of scope even for V3:** any live brokerage connection, order history import via broker API, or automated portfolio sync — if ever considered, it would need its own dedicated security review given the credential-handling implications.

---

# 5. Dashboard Navigation

```
📊 Dashboard                    Cross-engine executive summary + unified Today's Focus
                                 (pulls the top candidates across Swing/Position/Bearish
                                  into one landing view — the "open these first" page)

🌐 Market Intelligence          Nifty/Bank Nifty trend, breadth, FII/DII, Market Regime

🔥 Sector Intelligence          12-sector 7-state grid, multi-horizon table, leadership
                                 timeline, Market Cycle wheel (tab within this page)

📈 Swing Opportunities          The current V1 experience, nested as sub-tabs:
      ├─ Opportunity Hub          Today's Focus, Priority A/B/C (unchanged from V1)
      ├─ Combined Watchlist       Tier 1/2/3 confluence (unchanged from V1)
      ├─ Deal Flow                Bulk/block deals + technicals (unchanged from V1)
      ├─ Institutional            FII/DII + sector rotation (unchanged from V1)
      ├─ Corporate Actions        Classified announcements (unchanged from V1)
      └─ Results                  Quarterly results (unchanged from V1)

📐 Position Opportunities       Position Trading Watchlist (Priority A/B/Watchlist)

🔻 Bearish Opportunities        Priority Short A/B, Watchlist, Avoid Shorts (F&O only)

✅ Validation                   Per-engine win rate / avg / median, V1 + all V2 engines

🕰️ Historical Replay            Date picker; reconstructs any past day's full view

💼 Portfolio Insights           User's holdings cross-referenced against all engines

🗂️ Reports                      Browse/download the markdown & CSV reports already
                                 generated by the pipelines (read-only file browser)

⚙️ Settings                     VIEW-ONLY: current config thresholds, data freshness
                                 per source, system/version info. No live threshold
                                 editing — changing a rule requires a config-file edit
                                 and redeploy, preserving auditability (§2).

ℹ️ About                        Brand, purpose, data sources, disclaimers (promoted
                                 from V1's sidebar expander to its own full page)
```

**Design intent:** "Dashboard" and "Swing Opportunities" are deliberately distinct — Dashboard is the 2-minute cross-engine glance; Swing Opportunities is the full V1 depth for anyone who wants to dig into *why* a Swing candidate ranks where it does.

---

# 6. User Experience

### 6.1 Color coding (formalized from BRAND_GUIDELINES.md — no new palette)
| Use | Color |
|---|---|
| Priority A / Strong / Ready / Bullish | Growth Green `#22C55E` |
| Priority B / Improving / Research | Amber `#CA8A04` |
| Watch / Neutral / informational | Primary Blue `#2563EB` |
| Priority C / Weak / Avoid / Bearish | Negative Red `#DC2626` |
| Muted / secondary text | Slate `#64748B` / `#94A3B8` |

### 6.2 Icons
One emoji per nav item (see §5), reused consistently across page titles, sidebar, and section headers — never swapped between pages for the same concept (e.g. ✅ always means Validation, never repurposed elsewhere).

### 6.3 Priority & warning colors
- **Priority tags** (A/B/C, Short A/B) use a badge system already built in `components.py` (`badge()`, `COLUMN_HELP` tooltips) — extended to new modules, not redesigned.
- **Warning colors** (stale data, Avoid states) reuse the existing freshness-badge pattern (green ≤4 days, amber ≤10, red beyond) already shipping on the Opportunity Hub.

### 6.4 Table layouts
- Every data table gets a **tooltip on every non-obvious column header** (extending V1's `COLUMN_HELP` dictionary — §6.6 in the improvement request that shaped V1's polish phase already established this pattern; V2 continues it for every new module's tables, not just Swing).
- Sort order is always meaningful (Priority A→C, tier 1→3, etc.) — never alphabetical-by-default on a ranked table.

### 6.5 Card layouts
KPI cards follow V1's existing high-contrast spec: dark surface `#161B26`, colored left accent border, bright value text, muted uppercase label (`components.py::kpi_card`) — reused verbatim for every new module's headline metrics.

### 6.6 Responsive behavior
**Honest current-state note:** Streamlit's native responsive control is limited — multi-column KPI rows will stack on narrow viewports (Streamlit's default behavior), and the sidebar auto-collapses below a width threshold. V2 does not promise custom mobile layouts beyond what Streamlit provides natively; this is a real platform constraint, not a design choice, and should not be oversold in any release notes.

### 6.7 Dark Mode / Light Mode
**Honest current-state note:** V1's actual implementation is **dark-first with hardcoded hex colors** in `components.py` — it does not currently react to Streamlit's light/dark theme toggle (the CSS uses fixed values, not CSS custom properties keyed to `data-theme`). This is a **real gap**, not a solved requirement:
- **V2 requirement:** rework `inject_global_css()` to use CSS custom properties (`--tp-surface`, `--tp-text`, etc.) with both a `@media (prefers-color-scheme: light)` block and explicit dark-theme defaults, so the app genuinely adapts rather than always rendering dark.
- Until that rework ships, "Light Mode" should not be advertised as supported — BRAND_GUIDELINES.md's logo variants (`logo-full-light`/`logo-full-dark`) are already prepared for this, but the *app chrome* is not yet theme-reactive.

---

# 7. Success Metrics

| Metric | How it's measured | Status today |
|---|---|---|
| **Validation accuracy** | Win rate / avg return by engine and horizon, from the Validation Dashboard | ✅ **Already measurable** — this is V1's existing Validation Dashboard, extended in §4.7 |
| **System stability** | Pipeline success rate, from the existing `job_runs` audit table (every pipeline run already logs status/duration/row-counts) | ✅ **Already measurable** — zero new instrumentation needed |
| **Number of quality opportunities** | Count of Priority A / 5-star Setup-Quality names per day, across Swing/Position/Bearish | ✅ **Already measurable** from existing tables |
| **Daily active usage** | Dashboard page-load / session count | ⚠️ **Not yet instrumented** — the app has no usage-logging today; this requires a small new (local, non-invasive) logging addition before it can be reported |
| **Average research time** | Time from dashboard open to chart-check completion | ⚠️ **Not measurable without new telemetry** — flagged as aspirational; would need session-level event logging, a real scope addition, not assumed to exist |

This table exists specifically to prevent success-metric claims that outrun what the system can actually report — consistent with §2's "evidence-driven" principle applied to the PRD itself.

---

# 8. Future Roadmap

### V2 (this document's scope)
Market Intelligence · Sector Intelligence · Market Cycle · Swing Engine (V1 + Early Momentum) · Position Engine · Bearish Engine · Validation Dashboard (extended) · Historical Replay · Portfolio Insights · Reports · Settings (view-only) · About · Dark/Light theme rework.

### V3 (candidate ideas, not committed)
- Per-stock (not just per-sector) Market Cycle tagging, once the sector-level version is validated.
- Options/F&O-specific signals for the Bearish Engine (unusual OI buildup, PCR shifts).
- Promoter-holding trend tracking once the shareholding-pattern connector (flagged in §4.5) is built.
- Cross-engine validation studies (e.g. does Tier-1 confluence + Strong sector out-validate either alone).
- A read-only, natural-language **summarizer** over already-computed rule outputs — explicitly **not** a new scoring or ranking layer; if ever built, it must only rephrase deterministic outputs in prose, never replace them (guardrail against philosophy drift, §2).

### Future Ideas (unscoped, speculative — parking lot only)
- Alerting/notifications (email/push) for new Priority-A entries — deferred because it introduces always-on infrastructure and opt-in/consent design that hasn't been scoped.
- Multi-user accounts / cloud hosting — the platform is explicitly single-user/local by design today.
- Broker-connected, read-only order-history import for Portfolio Insights — would require its own dedicated security review before any credential-adjacent design is even discussed.

### Explicitly out of scope (all versions, unless a future decision deliberately revisits it)
- **Automated trade execution or order placement of any kind.**
- **Storing, requesting, or handling brokerage credentials or API keys.**
- **AI/ML-based scoring, prediction, or black-box ranking** — the core philosophy (§2) is not a V2-only constraint; it applies to every future version.
- **Real-time intraday tick data or HFT-style feeds** — the platform is a pre-market/EOD research tool, not an execution feed.
- **Options Greeks or derivatives pricing models.**
- Live threshold-editing UI (§5 Settings is view-only by design — rule changes go through config + redeploy, not a live dashboard control, to preserve the auditability promised in §2).
