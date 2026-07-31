"""
Bearish Opportunity Engine — signal definitions, thresholds, categories, and
the FULL documented rule set. Single written source of truth; the classifier
in `processors/bearish_classifier.py` implements exactly this and nothing more.

PURPOSE: detect objective, already-measurable signs that relative strength and
trend are DETERIORATING in a stock — before a breakdown becomes obvious. This
is detection of current fact, NOT prediction of a future decline.

No AI, no ML, no probability, no cross-market composite score.

DELIBERATE MIRROR OF PHASE 3: this module is the weakness-side counterpart of
Early Momentum. It reuses the SAME raw metrics (relative strength, moving
averages, price momentum, volume) computed by the SAME shared machinery —
`processors.momentum_metrics.compute_stock_metrics()` (itself built on
`processors.shared_relative_strength`) — and interprets them with inverted,
independently-documented thresholds. No new indicator is computed anywhere in
this module; every field consumed here already exists in Phase 3's metrics
dict.

DATA SOURCES (all pre-existing — no new connector, no new indicator):
  * V1 `price_history`      (read-only bridge, via momentum_metrics) -> price + volume series
  * V1 `symbol_master`      (read-only bridge) -> universe
  * V1 `daily_watchlist`    (read-only bridge) -> existing V1 technical_status="Avoid" flag
  * Phase 1 sector_intelligence_daily (market_v2.db) -> sector weakness
  * Phase 2 market_cycle_daily        (market_v2.db) -> cycle weakness

UNIVERSE: exactly the symbols V1 already stores price history for (the same
F&O-derived universe Phase 3 scans). Not expanded.
"""

from __future__ import annotations

from intelligence_v2.config.early_momentum import MIN_HISTORY_DAYS, VOL_EXPANSION_MULT  # noqa: F401 (re-export)

# ---------------------------------------------------------------------------
# Signal thresholds
# ---------------------------------------------------------------------------
RS_NEGATIVE_MAX = 0.0              # rs_1m below this = underperforming Nifty
PRICE_MOMENTUM_MAX = 0.0           # perf_1m below this = price falling

# Sector states (Phase 1) that count as sector weakness. Deliberately the
# complement of Phase 3's SECTOR_STRENGTH_STATES — "Sideways" is left neutral
# in both directions, exactly as Phase 3 leaves it neutral.
SECTOR_WEAKNESS_STATES = ("Downtrend", "Weakening")

# Market Cycle stages (Phase 2) that confirm a deteriorating backdrop.
# "Distribution" = topping (strength leaving while price still elevated);
# "Weak Trend" = confirmed downward drift. "Mature Trend" is deliberately
# excluded — RS is still positive there over 3M, so it reads as an aging
# uptrend, not yet objective weakness.
CYCLE_WEAKNESS_STAGES = ("Distribution", "Weak Trend")

# How far back a V1 daily_watchlist appearance with technical_status="Avoid"
# still counts as a live "V1 Avoid" signal. V1's technical_status is an
# existing, already rule-based field (core/processing/technicals.py:
# "Avoid — clear weakness: below 20 SMA and Weak RS") — reused here exactly
# as Phase 3 reused daily_watchlist itself for its "V1 Opportunity" signal.
V1_AVOID_LOOKBACK_DAYS = 30

# ---------------------------------------------------------------------------
# The nine deterministic signals
# ---------------------------------------------------------------------------
SIGNAL_DEFINITIONS: list[dict] = [
    {"key": "rs_weakening", "label": "Relative Strength weakening",
     "rule": "rs_1m today is lower than rs_1m 20 sessions ago (RS slope < 0)"},
    {"key": "rs_negative", "label": "Underperforming Nifty (1M)",
     "rule": "rs_1m < 0"},
    {"key": "below_20_sma", "label": "Below 20 SMA",
     "rule": "close < 20-day simple moving average"},
    {"key": "below_50_sma", "label": "Below 50 SMA",
     "rule": "close < 50-day simple moving average"},
    {"key": "price_momentum_negative", "label": "Negative price momentum (1M)",
     "rule": "perf_1m < 0"},
    {"key": "volume_expansion", "label": "Volume expansion",
     "rule": f"avg volume last 10d > {VOL_EXPANSION_MULT}x avg volume of the prior 30d "
             "(expansion on a weakening stock reads as distribution, not accumulation)"},
    {"key": "sector_weakness", "label": "Sector weakness",
     "rule": f"stock's sector (Phase 1) is in {', '.join(SECTOR_WEAKNESS_STATES)}"},
    {"key": "cycle_weakness", "label": "Market Cycle weakness",
     "rule": f"stock's sector cycle stage (Phase 2) is in {', '.join(CYCLE_WEAKNESS_STAGES)}"},
    {"key": "v1_avoid_flag", "label": "Existing V1 Avoid signal",
     "rule": f"symbol appeared in V1's daily_watchlist with technical_status='Avoid' "
             f"within the last {V1_AVOID_LOOKBACK_DAYS} days"},
]

SIGNAL_LABELS = {s["key"]: s["label"] for s in SIGNAL_DEFINITIONS}

# ---------------------------------------------------------------------------
# Categories — exactly one per stock, evaluated in this order (first match wins)
# ---------------------------------------------------------------------------
CATEGORIES = ("High Conviction Bearish", "Building Weakness", "Watch for Breakdown", "Not Qualified")

CATEGORY_RULES_DOC: list[dict] = [
    {
        "category": "High Conviction Bearish",
        "order": 1,
        "conditions": [
            "Relative Strength weakening (RS slope < 0)",
            "Already underperforming Nifty over 1M (rs_1m < 0)",
            "Price below BOTH its 20-SMA and 50-SMA",
            "Negative 1-month price momentum",
            "Confirmed backdrop: sector weakness OR market-cycle weakness",
        ],
        "meaning": "Weakness is deepening AND already showing through, with a deteriorating "
                   "sector/cycle backdrop. The most complete evidence set available.",
    },
    {
        "category": "Building Weakness",
        "order": 2,
        "conditions": [
            "Relative Strength weakening (RS slope < 0)",
            "Price below its 20-SMA",
            "Either already underperforming Nifty (rs_1m < 0) OR negative 1-month price momentum",
        ],
        "meaning": "Weakness is building and price is below short-term trend, but the "
                   "evidence set is not yet complete enough for High Conviction Bearish.",
    },
    {
        "category": "Watch for Breakdown",
        "order": 3,
        "conditions": [
            "Relative Strength weakening (RS slope < 0), OR",
            "Price below its 20-SMA together with negative 1-month price momentum",
        ],
        "meaning": "One credible early sign of weakness is present, but not enough "
                   "corroboration to call it a breakdown yet. Monitor only.",
    },
    {
        "category": "Not Qualified",
        "order": 4,
        "conditions": [
            "None of the above conditions are satisfied.",
        ],
        "meaning": "No objective bearish evidence at this time.",
    },
]

CATEGORY_MEANING = {r["category"]: r["meaning"] for r in CATEGORY_RULES_DOC}

# ---------------------------------------------------------------------------
# Ranking — WITHIN a category only (per Phase 4 brief's suggested priority)
# ---------------------------------------------------------------------------
# Deterministic sort applied separately inside each category. Every key is an
# already-computed field (no new indicator) — never a market-wide score, and
# never compared across categories.
RANKING_KEYS_DOC = (
    "1. rs_1m (ascending) — the most negative (weakest) relative strength first\n"
    "2. sector_rs_1m (ascending) — the stock's sector's own 1M RS (Phase 1), weakest first\n"
    "3. perf_1m (ascending) — the most negative price momentum first\n"
    "4. symbol (ascending) — alphabetical, guarantees a stable, reproducible order"
)
