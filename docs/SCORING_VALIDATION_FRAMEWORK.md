# Scoring Engine — Validation Framework
### Indian Market Intelligence Dashboard · Pre-Implementation Gate

> **Purpose:** prove (or disprove) that Market Health, Institutional Flow, and Smart Money scores carry **predictive value** *before* any dashboard is built around them.
> **No implementation code.** Methodology, test design, metrics, and decision rules only.
> **Governing principle:** a factor earns its place on the dashboard only if it measurably improves forward decision quality. Everything else is removed.

---

## 0. Validation Philosophy

1. **Falsifiable first.** Every score is stated as a hypothesis with explicit **failure conditions**. We try to *break* each score, not confirm it.
2. **Point-in-time, no peeking.** Use only data that was knowable at the decision timestamp. Look-ahead bias is the #1 way backtests lie.
3. **Out-of-sample is the verdict.** In-sample tuning proves nothing; the holdout period decides.
4. **Economic significance > statistical significance.** A factor can be statistically real and still too weak (after costs) to act on.
5. **Benchmark-relative.** "Did it go up?" is the wrong question. "Did it beat Nifty / its sector, net of costs?" is the right one.

---

## 1. Hypotheses Under Test

| # | Score | Core Hypothesis (H1) | Null Hypothesis (H0) |
|---|---|---|---|
| 1 | **Market Health** | When Market Health is high, the *next-period* market (Nifty) forward return is positive and risk-adjusted return is higher than when it is low. | Market Health has no relationship with forward Nifty returns. |
| 2 | **Institutional Flow** | High net FII+DII inflow predicts positive forward market returns and **sector-level** outperformance where flows concentrate. | FII/DII flow has no forward predictive value (it is coincident, not leading). |
| 3 | **Smart Money** | Stocks with high Smart Money score (bulk/block accumulation by quality buyers) outperform Nifty over 1/5/20 days. | Bulk/block deals are noise; high Smart Money ≠ outperformance. |

---

## 2. Per-Score Specification

### 2.1 Market Health Score
- **Inputs:** Nifty trend (vs SMA20/50/200 + day momentum), market breadth, India VIX (inverted), sector participation.
- **Assumptions:** breadth and trend are *leading-to-coincident*; VIX low = complacency-but-stable in normal regimes; daily EOD inputs are stable and revision-free.
- **Expected behavior (if predictive):** High score → positive 1/5/20-day Nifty return, higher Sharpe, lower drawdown frequency. Low score → flat/negative forward returns, higher realized vol.
- **Failure conditions:**
  - No monotonic relationship between score quintiles and forward returns.
  - VIX component **inverts** (low VIX precedes drawdowns — complacency trap) often enough to flip the sign.
  - Score is purely **coincident** (correlates with *same-day* return but not *forward* return).
  - Works only in trending markets, fails (or harms) in choppy/range regimes.

### 2.2 Institutional Flow Score
- **Inputs:** FII net (today), DII net (today), 5-day combined flow trend.
- **Assumptions:** provisional EOD FII/DII figures are accurate and available before next session; cash-segment flow proxies overall positioning; FII and DII are not always offsetting.
- **Expected behavior (if predictive):** Sustained net inflows → positive forward market return; sectors receiving concentrated inflow outperform the broad index over 5–20 days.
- **Failure conditions:**
  - FII and DII chronically **offset** (FII sell / DII buy) → net signal is noise.
  - Flow is **mean-reverting contrarian** (heavy buying marks local tops) rather than trend-confirming.
  - Single-day flow has no edge and only multi-day trend matters (then drop the daily components).
  - Sector attribution impossible from cash provisional data (granularity blocker).

### 2.3 Smart Money Score
- **Inputs:** bulk-deal net value, block-deal net value, total deal value, buyer quality (marquee list share).
- **Assumptions:** disclosed deals reflect informed intent; buyer-quality list is meaningful; deal value is comparable across names (normalize by free-float/ADV).
- **Expected behavior (if predictive):** Stocks flagged as accumulation outperform Nifty and their sector over 5–20 days; quality-buyer deals outperform anonymous deals.
- **Failure conditions:**
  - Deal often = **liquidity event / exit**, not accumulation → high score precedes underperformance.
  - Signal already **priced in** by disclosure time (deals reported post-close, gap fully discounts it).
  - Buyer-quality adds no lift over raw deal value (drop the 15% component).
  - Survivorship/selection: only large-cap deals show up, edge vanishes after liquidity normalization.

---

## 3. Validation Metrics

### 3.1 Forward-return metrics (per signal event)
| Metric | Definition |
|---|---|
| **1-Day Forward Return** | (close[t+1] − close[t]) / close[t] |
| **5-Day Forward Return** | (close[t+5] − close[t]) / close[t] |
| **20-Day Forward Return** | (close[t+20] − close[t]) / close[t] |
All computed both **absolute** and **excess** (minus Nifty over the same window) — excess is the one that matters.

### 3.2 Outcome metrics (per cohort / strategy)
| Metric | Definition | Pass guidance |
|---|---|---|
| **Win Rate** | % of events with positive **excess** return | > 50% (ideally ≥55%) |
| **Average Gain** | mean excess return of winners | — |
| **Average Loss** | mean excess return of losers | — |
| **Payoff / Expectancy** | (WinRate·AvgGain) − (LossRate·\|AvgLoss\|) | > 0, net of costs |
| **Maximum Drawdown** | largest peak-to-trough of the signal-following equity curve | lower than buy-&-hold Nifty |
| **Sharpe (ann.)** | mean/σ of strategy excess returns ×√252 | > Nifty Sharpe |
| **Hit consistency** | win rate stability across years/regimes | no single year carries it |

### 3.3 Predictive-power metrics (the real test)
| Metric | What it measures |
|---|---|
| **IC (Information Coefficient)** | Pearson corr(score, forward excess return) per date, averaged. \|IC\|>0.03 weak, >0.05 useful, >0.10 strong (daily cross-section). |
| **Rank-IC (Spearman)** | rank correlation — robust to outliers; primary metric for stock-level (Smart Money). |
| **IC IR** | mean(IC)/std(IC) — consistency of the signal; >0.5 is good. |
| **t-stat of IC** | statistical significance of the average IC. |
| **Quantile spread** | Q5 (top) minus Q1 (bottom) forward excess return — monotonic ladder = healthy factor. |

---

## 4. Backtesting Framework

### 4.1 Data requirements (point-in-time)
- **History:** ≥ 5 years daily (target 2019–2024) to cover bull, COVID crash, recovery, 2022 drawdown, 2023–24 rally → multiple regimes.
- **Universe:** Nifty 500 constituents **as they existed each day** (avoid survivorship — use historical index membership, not today's).
- **Inputs:** EOD index OHLC, breadth, VIX, sectoral indices, daily FII/DII, full bulk/block deal history with buyer names.
- **Corporate-action adjusted** prices (splits/bonus) — else returns are garbage.

### 4.2 Bias controls (mandatory)
| Bias | Control |
|---|---|
| **Look-ahead** | Signal at date *t* uses only data timestamped ≤ *t* close; deals reported post-close are actionable only from *t+1* open. |
| **Survivorship** | Historical universe membership; include delisted/merged names. |
| **Restatement/revision** | Use first-reported (provisional) FII/DII, not later revisions. |
| **Selection** | No cherry-picking events; test the full population of signals. |
| **Multiple-testing** | Pre-register hypotheses (this doc). Penalize p-values for the number of variants tried. |

### 4.3 Test designs
1. **Cross-sectional IC test** (stock-level: Smart Money) — each day rank all stocks by score, correlate with forward excess return.
2. **Quantile portfolios** — sort into Q1–Q5, hold 1/5/20 days, measure spread and monotonicity. Long-Q5 / short-Q1 spread = factor payoff.
3. **Regime / time-series test** (market-level: Market Health, Institutional Flow) — condition next-period Nifty return on score buckets (High/Mid/Low).
4. **Event study** (deals) — align all bulk/block events at t=0, plot average cumulative abnormal return (CAR) −5 to +20 days; test if CAR>0 and significant.
5. **Sector-flow test** (Institutional Flow Q1) — regress sector forward return on prior-period flow concentration.

### 4.4 Protocol
- **Split:** in-sample (2019–2022) for any threshold/weight tuning; **out-of-sample holdout (2023–2024)** never touched until final.
- **Walk-forward** validation across rolling windows to confirm stability.
- **Transaction costs:** apply realistic Indian costs (brokerage + STT + slippage, ~0.1–0.3% round trip) — a factor that only works gross is dead.
- **Benchmark:** Nifty 50 TR (market scores) and sector index / Nifty (stock & sector scores).

---

## 5. Answering the 5 Key Questions

| # | Question | Test that answers it | Pass criterion |
|---|---|---|---|
| 1 | Does high Institutional Flow predict **sector outperformance**? | §4.3 #5 sector-flow regression + quantile sectors | Top-flow sectors beat Nifty over 5–20d, IC>0.03, significant |
| 2 | Do large Bulk/Block deals predict **positive returns**? | §4.3 #4 event study (CAR) | CAR(+5,+20) > 0, t-stat significant, survives costs |
| 3 | Does **Smart Money** beat Nifty? | §4.3 #2 Q5 long portfolio vs Nifty | Q5 excess return > 0, Sharpe > Nifty, after costs |
| 4 | Which score has **highest predictive power**? | Compare IC / IC-IR / quantile spread across all 3 | Ranked by IC-IR (consistency-weighted) |
| 5 | Which score deserves **highest weight**? | Weight ∝ IC-IR, subject to low cross-correlation | See §6 |

---

## 6. Factor Ranking Process

For every factor (and sub-component — e.g. FII-today vs 5-day-trend vs VIX vs breadth), produce:

```
FACTOR → CORRELATION (IC/Rank-IC) → HIT RATE → AVG RETURN → RANKING
```

**Output table (one row per factor):**

| Factor | IC (Rank-IC) | IC-IR | Hit Rate | Avg Excess Ret (5d) | Q5–Q1 Spread | Cost-Adj? | Rank |
|---|---|---|---|---|---|---|---|
| Market Health (composite) | … | … | … | … | … | Y/N | … |
| — Breadth sub | … | | | | | | |
| — Nifty Trend sub | … | | | | | | |
| — VIX sub | … | | | | | | |
| — Sector Participation sub | … | | | | | | |
| Institutional Flow (composite) | … | | | | | | |
| — FII net (today) | … | | | | | | |
| — DII net (today) | … | | | | | | |
| — 5-day flow trend | … | | | | | | |
| Smart Money (composite) | … | | | | | | |
| — Bulk net | … | | | | | | |
| — Block net | … | | | | | | |
| — Buyer quality | … | | | | | | |

**Ranking rule:** sort by **IC-IR** (predictive *consistency*) as primary, IC magnitude as tiebreaker, then penalize for redundancy (factors with >0.7 mutual correlation count once — keep the stronger).

**Recommended weighting (data-driven, replaces the hand-set §H weights):**
```
weight_i = max(IC_IR_i, 0) / Σ max(IC_IR_j, 0)
```
i.e. only positive-edge factors get weight, proportional to consistency. Re-derive after each backtest; this turns the V1 guessed weights into earned weights.

---

## 7. Keep / Remove / Add Decision Rules

### Thresholds (out-of-sample, cost-adjusted)
- **KEEP** — Rank-IC ≥ 0.03 **and** IC-IR ≥ 0.3 **and** Win Rate ≥ 52% **and** monotonic quantile ladder **and** positive expectancy after costs.
- **WATCH** (keep but down-weight) — borderline (e.g. IC 0.02–0.03, or strong in-sample but weak OOS). Quarantine to a "experimental" panel, not the headline score.
- **REMOVE** — IC ≈ 0, non-monotonic quantiles, sign flips across regimes, or edge disappears after costs. Cut it regardless of intuition.

### Likely candidates to REMOVE (to be confirmed by data)
- **VIX sub** if it inverts (low VIX → drawdowns) — common failure.
- **Single-day FII or DII** if only the 5-day trend carries signal.
- **Buyer-quality** if it adds no lift over raw deal value.

### New factors to ADD & test (cheap, high-expected-value)
| Candidate | Rationale |
|---|---|
| **Delivery % / delivery-volume spike** | Real accumulation vs intraday churn — strong India-specific signal. |
| **Net flow *trend acceleration*** (2nd derivative) | Inflection often leads price better than level. |
| **Advance/Decline trend (not just level)** | Breadth thrust / deterioration as leading signal. |
| **Deal value normalized by ADV / free-float** | Makes Smart Money comparable across small vs large caps. |
| **Repeat-buyer flag** (same marquee buyer accumulating over weeks) | Conviction signal vs one-off block. |
| **Sector relative strength (RS) momentum** | Direct sector-rotation factor for Q1 question. |
| **F&O FII positioning (index/stock futures OI)** | Often more *leading* than cash flow. |

---

## 8. Validation Workflow (gate before Phase 1 coding)

```
1. Assemble point-in-time historical dataset (5y, Nifty 500, deals, flows, VIX)
2. Compute each score & sub-component daily (no look-ahead)
3. Compute 1/5/20d absolute + excess forward returns
4. Run §4.3 tests: IC, quantiles, event study, regime, sector-flow
5. Split in-sample / OOS holdout; walk-forward
6. Produce §6 factor ranking table (cost-adjusted, OOS)
7. Apply §7 keep/remove/add rules → finalize factor set + data-driven weights
8. Re-run final composite scores on OOS → confirm Sharpe & DD beat Nifty
9. GATE: only factors that pass enter the Phase 1 dashboard
```

---

## 9. Outcome of this framework

This framework produces three concrete artifacts that feed back into the build:
1. **A vetted factor list** — only predictive factors survive into the dashboard.
2. **Data-driven weights** — replacing the hand-set weights in the Phase 1 spec §H.
3. **A confidence statement per score** — so the Stock Radar (Phase 4) only acts on signals with proven edge.

> **Hard rule:** if a score fails the keep criteria out-of-sample, it does **not** get a dashboard panel — no matter how good it looks. This is exactly the "don't build a complex dashboard around useless metrics" guardrail you asked for.

**Note:** running this validation requires the **historical dataset** (the same Kite/NSE/BSE history Phase 1 will ingest). The framework is final and ready; execution is blocked only on that data — which Phase 1's connectors will provide. Recommended sequencing: build the data layer + connectors first (read-only, no scoring), backfill 5y history, run this validation, *then* commit to the scoring engine and any score-driven UI.
```
