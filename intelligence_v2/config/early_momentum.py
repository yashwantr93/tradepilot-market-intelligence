"""
Early Momentum Engine — signal definitions, thresholds, categories, and the
FULL documented rule set. Single written source of truth; the classifier in
`processors/momentum_classifier.py` implements exactly this and nothing more.

PURPOSE: detect objective, already-measurable signs that relative strength and
accumulation are IMPROVING in a stock — before it becomes an obvious leader.
This is detection of current fact, NOT prediction of future price.

No AI, no ML, no probability, no cross-market composite score.

DATA SOURCES (all pre-existing — no new connector, no new indicator):
  * V1 `price_history`      (read-only bridge) -> price + volume series
  * V1 `symbol_master`      (read-only bridge) -> universe
  * V1 `daily_watchlist`    (read-only bridge) -> existing V1 Opportunity filter
  * Phase 1 sector_intelligence_daily (market_v2.db) -> sector strength
  * Phase 2 market_cycle_daily        (market_v2.db) -> cycle confirmation

UNIVERSE: exactly the symbols V1 already stores price history for. Not expanded.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Universe / data-sufficiency
# ---------------------------------------------------------------------------
BENCHMARK_SYMBOL = "NIFTY 50"      # already present in V1's price_history
MIN_HISTORY_DAYS = 63              # need at least a 3-month window to judge RS

# ---------------------------------------------------------------------------
# Input data sanitisation (NOT a new indicator — data hygiene on consumed data)
# ---------------------------------------------------------------------------
# V1's stored price_history contains isolated corrupt closes: single days that
# jump far beyond any real move and immediately revert (e.g. NIFTY 50 printing
# 16,848 on 2026-06-26 between two ~24,000 closes — a fake -30%/+42% round trip).
# 28 of 252 symbols are affected, 298 rows in total.
#
# Left unfiltered these destroy relative strength: measured against the corrupt
# benchmark, the AVERAGE stock showed RS of -37%, which is impossible for a
# measure defined relative to that same benchmark.
#
# The guard drops any close that moves more than this threshold from the last
# VALID close. NSE circuit bands top out at 20%, and an index physically cannot
# move this much in a session, so a larger move is corrupt by definition rather
# than a judgement call. This filters V2's in-memory copy only; V1's stored data
# is never modified.
MAX_DAILY_MOVE_PCT = 25.0

# ---------------------------------------------------------------------------
# Horizons (trading days) — same conventions already used in Phases 1 & 2
# ---------------------------------------------------------------------------
HORIZON_DAYS = {"1w": 5, "1m": 21, "3m": 63}
RS_SLOPE_LOOKBACK = 20             # rs_1m(t) vs rs_1m(t-20) -> "RS improving"
SMA_WINDOWS = (20, 50, 200)
HIGH_52W_LOOKBACK = 252

# ---------------------------------------------------------------------------
# Volume expansion (uses volume ALREADY stored in V1 price_history)
# ---------------------------------------------------------------------------
VOL_RECENT_DAYS = 10
VOL_BASE_DAYS = 30
VOL_EXPANSION_MULT = 1.2           # recent avg vol > 1.2x prior base avg

# ---------------------------------------------------------------------------
# Signal thresholds
# ---------------------------------------------------------------------------
RS_POSITIVE_MIN = 0.0              # rs_1m above this = outperforming Nifty
PRICE_MOMENTUM_MIN = 0.0           # perf_1m above this = price rising

# Sector states (Phase 1) that count as sector strength.
SECTOR_STRENGTH_STATES = ("Strong Leader", "Early Momentum", "Improving", "Recovery")

# Market Cycle stages (Phase 2) that confirm a constructive backdrop.
CYCLE_CONFIRMING_STAGES = ("Early Momentum", "Strong Trend", "Accumulation", "Recovery")

# How far back a V1 daily_watchlist appearance still counts as a live
# "V1 Opportunity" signal.
V1_OPPORTUNITY_LOOKBACK_DAYS = 30

# ---------------------------------------------------------------------------
# The nine deterministic signals
# ---------------------------------------------------------------------------
SIGNAL_DEFINITIONS: list[dict] = [
    {"key": "rs_improving", "label": "Relative Strength improving",
     "rule": "rs_1m today is higher than rs_1m 20 sessions ago (RS slope > 0)"},
    {"key": "rs_positive", "label": "Outperforming Nifty (1M)",
     "rule": "rs_1m > 0"},
    {"key": "above_20_sma", "label": "Above 20 SMA",
     "rule": "close > 20-day simple moving average"},
    {"key": "above_50_sma", "label": "Above 50 SMA",
     "rule": "close > 50-day simple moving average"},
    {"key": "price_momentum", "label": "Positive price momentum (1M)",
     "rule": "perf_1m > 0"},
    {"key": "volume_expansion", "label": "Volume expansion",
     "rule": f"avg volume last {VOL_RECENT_DAYS}d > {VOL_EXPANSION_MULT}x avg volume of the prior {VOL_BASE_DAYS}d"},
    {"key": "sector_strength", "label": "Sector strength",
     "rule": f"stock's sector (Phase 1) is in {', '.join(SECTOR_STRENGTH_STATES)}"},
    {"key": "cycle_confirmation", "label": "Market Cycle confirmation",
     "rule": f"stock's sector cycle stage (Phase 2) is in {', '.join(CYCLE_CONFIRMING_STAGES)}"},
    {"key": "v1_opportunity", "label": "Existing V1 Opportunity signal",
     "rule": f"symbol appeared in V1's daily_watchlist within the last {V1_OPPORTUNITY_LOOKBACK_DAYS} days"},
]

SIGNAL_LABELS = {s["key"]: s["label"] for s in SIGNAL_DEFINITIONS}

# ---------------------------------------------------------------------------
# Categories — exactly one per stock, evaluated in this order (first match wins)
# ---------------------------------------------------------------------------
CATEGORIES = ("Emerging Leader", "Building Momentum", "Watch Closely", "Not Qualified")

CATEGORY_RULES_DOC: list[dict] = [
    {
        "category": "Emerging Leader",
        "order": 1,
        "conditions": [
            "Relative Strength improving (RS slope > 0)",
            "Already outperforming Nifty over 1M (rs_1m > 0)",
            "Price above BOTH its 20-SMA and 50-SMA",
            "Positive 1-month price momentum",
            "Confirmed backdrop: sector strength OR market-cycle confirmation",
        ],
        "meaning": "Strength is improving AND already showing through, with a supportive "
                   "sector/cycle backdrop. The most complete evidence set available.",
    },
    {
        "category": "Building Momentum",
        "order": 2,
        "conditions": [
            "Relative Strength improving (RS slope > 0)",
            "Price above its 20-SMA",
            "Either already outperforming Nifty (rs_1m > 0) OR positive 1-month price momentum",
        ],
        "meaning": "Strength is building and price is above short-term trend, but the "
                   "evidence set is not yet complete enough for Emerging Leader.",
    },
    {
        "category": "Watch Closely",
        "order": 3,
        "conditions": [
            "Relative Strength improving (RS slope > 0), OR",
            "Price above its 20-SMA together with positive 1-month price momentum",
        ],
        "meaning": "One credible early sign is present, but not enough corroboration "
                   "to call it momentum yet. Monitor only.",
    },
    {
        "category": "Not Qualified",
        "order": 4,
        "conditions": [
            "None of the above conditions are satisfied.",
        ],
        "meaning": "No objective early-momentum evidence at this time.",
    },
]

CATEGORY_MEANING = {r["category"]: r["meaning"] for r in CATEGORY_RULES_DOC}

# ---------------------------------------------------------------------------
# Ranking — WITHIN a category only
# ---------------------------------------------------------------------------
# Deterministic sort applied separately inside each category. `signal_count` is
# a transparent COUNT of satisfied signals, used purely as an ordering key — it
# is never a market-wide score and is never compared across categories.
RANKING_KEYS_DOC = (
    "1. signal_count (descending) — how many of the nine signals are satisfied\n"
    "2. rs_1m (descending) — stronger 1-month relative strength first\n"
    "3. symbol (ascending) — alphabetical, guarantees a stable, reproducible order"
)
