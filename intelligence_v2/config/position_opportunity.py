"""
Position Opportunity Engine — signal definitions, thresholds, categories, and
the FULL documented rule set. Single written source of truth; the classifier
in `processors/position_classifier.py` implements exactly this and nothing more.

PURPOSE: detect objective, already-measurable signs that a stock is suitable
for MEDIUM-TO-LONG-TERM position trading (multi-week to multi-month) — a
research and opportunity-discovery lens, not an execution engine. This is
detection of current fact, NOT prediction of future price.

No AI, no ML, no probability, no cross-market composite score.

DELIBERATE REUSE, NOT REINVENTION: this module is the final piece of the V2
intelligence stack and touches every prior phase as a data source:
  - Stock-level metrics (relative strength, moving averages, price momentum,
    volume) come unmodified from `processors.momentum_metrics.compute_stock_metrics()`
    (itself built on `processors.shared_relative_strength`) — the SAME function
    Phase 3 and Phase 4 already use. No new metric is computed anywhere here.
  - Sector-strength and cycle-confirmation states are the SAME documented sets
    Phase 3 already uses (`config.early_momentum.SECTOR_STRENGTH_STATES` /
    `CYCLE_CONFIRMING_STAGES`), imported directly rather than duplicated.
  - Phase 3's own Early Momentum category is read as an INPUT signal — the one
    genuinely new data source this phase adds, and it is a read of an existing
    table, not a new computation.
  - V1's existing `daily_watchlist.technical_status` field ("Ready" = uptrend
    & leadership, see `core/processing/technicals.py`) is reused as the
    "Existing V1 Opportunity Status" signal the Phase 5 brief calls for.

DATA SOURCES (all pre-existing — no new connector, no new indicator):
  * V1 `price_history`      (read-only bridge, via momentum_metrics) -> price + volume series
  * V1 `symbol_master`      (read-only bridge) -> universe
  * V1 `daily_watchlist`    (read-only bridge) -> existing V1 technical_status="Ready" flag
  * Phase 1 sector_intelligence_daily (market_v2.db) -> sector strength
  * Phase 2 market_cycle_daily        (market_v2.db) -> cycle confirmation
  * Phase 3 early_momentum_daily      (market_v2.db) -> Early Momentum confirmation

UNIVERSE: exactly the symbols V1 already stores price history for (the same
F&O-derived universe Phase 3/4 scan). Not expanded.
"""

from __future__ import annotations

from intelligence_v2.config.early_momentum import (  # noqa: F401 (re-export / direct reuse)
    CYCLE_CONFIRMING_STAGES,
    MIN_HISTORY_DAYS,
    SECTOR_STRENGTH_STATES,
)

# ---------------------------------------------------------------------------
# Signal thresholds
# ---------------------------------------------------------------------------
RS_POSITIVE_MIN = 0.0              # rs_3m above this = positive medium-term relative performance
PRICE_MOMENTUM_MIN = 0.0           # perf_3m above this = healthy medium-term price momentum

# Early Momentum (Phase 3) categories that count as confirmation for position
# suitability — the two categories with a "complete" or "building" evidence
# set; "Watch Closely" is deliberately excluded (one early sign only, not
# enough for a multi-week/month conviction call).
EARLY_MOMENTUM_CONFIRMING_CATEGORIES = ("Emerging Leader", "Building Momentum")

# How far back a V1 daily_watchlist appearance with technical_status="Ready"
# still counts as a live "V1 Opportunity" signal. Mirrors Phase 3/4's own
# V1-lookback conventions.
V1_READY_LOOKBACK_DAYS = 30

# ---------------------------------------------------------------------------
# The nine deterministic signals
# ---------------------------------------------------------------------------
SIGNAL_DEFINITIONS: list[dict] = [
    {"key": "rs_improving", "label": "Relative Strength improving",
     "rule": "rs_1m today is higher than rs_1m 20 sessions ago (RS slope > 0)"},
    {"key": "rs_positive", "label": "Positive Relative Performance (3M)",
     "rule": "rs_3m > 0 — medium-term outperformance vs Nifty, the horizon relevant to "
             "multi-week/month position holding"},
    {"key": "above_50_sma", "label": "Above 50 SMA",
     "rule": "close > 50-day simple moving average"},
    {"key": "above_200_sma", "label": "Above 200 SMA (sustained trend)",
     "rule": "close > 200-day simple moving average — the long-term trend line"},
    {"key": "price_momentum", "label": "Healthy price momentum (3M)",
     "rule": "perf_3m > 0"},
    {"key": "sector_strength", "label": "Strong sector context",
     "rule": f"stock's sector (Phase 1) is in {', '.join(SECTOR_STRENGTH_STATES)}"},
    {"key": "cycle_bullish", "label": "Bullish market cycle",
     "rule": f"stock's sector cycle stage (Phase 2) is in {', '.join(CYCLE_CONFIRMING_STAGES)}"},
    {"key": "early_momentum_confirmed", "label": "Early Momentum confirmation (Phase 3)",
     "rule": f"stock's Phase 3 Early Momentum category is in "
             f"{', '.join(EARLY_MOMENTUM_CONFIRMING_CATEGORIES)}"},
    {"key": "v1_ready_status", "label": "Existing V1 Opportunity Status (Ready)",
     "rule": f"symbol appeared in V1's daily_watchlist with technical_status='Ready' "
             f"within the last {V1_READY_LOOKBACK_DAYS} days"},
]

SIGNAL_LABELS = {s["key"]: s["label"] for s in SIGNAL_DEFINITIONS}

# ---------------------------------------------------------------------------
# Categories — exactly one per stock, evaluated in this order (first match wins)
# ---------------------------------------------------------------------------
CATEGORIES = ("High Conviction Position", "Position Candidate", "Accumulation Watch", "Not Qualified")

CATEGORY_RULES_DOC: list[dict] = [
    {
        "category": "High Conviction Position",
        "order": 1,
        "conditions": [
            "Relative Strength improving (RS slope > 0)",
            "Positive medium-term relative performance (rs_3m > 0)",
            "Price above BOTH its 50-SMA and 200-SMA (sustained trend)",
            "Healthy 3-month price momentum (perf_3m > 0)",
            "Confirmed backdrop: sector strength OR bullish market cycle OR "
            "Phase 3 Early Momentum confirmation",
        ],
        "meaning": "Strength is improving AND already sustained across the medium/long-term "
                   "trend, with a confirming backdrop from at least one independent source "
                   "(sector, cycle, or momentum). The most complete evidence set available.",
    },
    {
        "category": "Position Candidate",
        "order": 2,
        "conditions": [
            "Relative Strength improving (RS slope > 0)",
            "Price above its 50-SMA",
            "Either positive relative performance (rs_3m > 0) OR healthy price momentum (perf_3m > 0)",
        ],
        "meaning": "Strength is building and price holds the medium-term trend, but the "
                   "full High Conviction Position evidence set is not yet present.",
    },
    {
        "category": "Accumulation Watch",
        "order": 3,
        "conditions": [
            "Relative Strength improving (RS slope > 0), OR",
            "Price above its 50-SMA together with healthy 3-month price momentum",
        ],
        "meaning": "One credible early sign is present, but not enough corroboration to "
                   "call it a position-ready setup yet. Monitor only.",
    },
    {
        "category": "Not Qualified",
        "order": 4,
        "conditions": [
            "None of the above conditions are satisfied.",
        ],
        "meaning": "No objective position-suitability evidence at this time.",
    },
]

CATEGORY_MEANING = {r["category"]: r["meaning"] for r in CATEGORY_RULES_DOC}

# ---------------------------------------------------------------------------
# Ranking — WITHIN a category only (per the Phase 5 brief's suggested priority)
# ---------------------------------------------------------------------------
# "Sector Strength" and "Market Cycle" are categorical states, not numbers.
# Rather than invent a new score, each is ordered by an already-computed
# proxy: sector strength by the stock's own sector's rs_1m (Phase 1's stored
# field), and market cycle by a documented, FIXED display ordering of the
# seven wheel stages from most to least bullish-favourable for THIS ranking
# only — never combined arithmetically with anything else, never compared
# across categories, and never used by the classifier itself (which only
# checks stage MEMBERSHIP in CYCLE_CONFIRMING_STAGES).
CYCLE_RANK_ORDER: dict[str, int] = {
    "Strong Trend": 0, "Early Momentum": 1, "Recovery": 2, "Accumulation": 3,
    "Mature Trend": 4, "Distribution": 5, "Weak Trend": 6,
}

RANKING_KEYS_DOC = (
    "1. rs_3m (descending) — the strongest medium-term relative strength first\n"
    "2. sector_rs_1m (descending) — the stock's sector's own 1M RS (Phase 1), strongest first\n"
    "3. cycle_rank (ascending, via CYCLE_RANK_ORDER) — the most bullish-favourable "
    "market cycle stage first\n"
    "4. perf_3m (descending) — the strongest 3-month price momentum first\n"
    "5. symbol (ascending) — alphabetical, guarantees a stable, reproducible order"
)
