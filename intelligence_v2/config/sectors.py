"""
Sector universe + Sector Intelligence thresholds.

The 12 sectors and their basket constituents are a DUPLICATED, frozen copy of
V1's `core.config.SECTORS` baskets (per the isolation principle in
docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §0.3) — not imported from V1. Only
the basket lists are reused (not V1's index tickers): Phase 1 computes every
sector's series as an equal-weighted, rebased average of its basket
constituents' closes, read from V1's `price_history` table via the read-only
bridge. This is deliberately the same fallback method V1 itself uses when a
direct index series isn't available — reused here because it already covers
~20 months of real history for every sector, which is longer than what V1's
own transient index-fetch ever persists.
"""

from __future__ import annotations

NIFTY_BENCHMARK_SYMBOL = "NIFTY 50"  # matches the symbol V1 already stores in price_history

SECTOR_BASKETS: dict[str, list[str]] = {
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"],
    "Financial Services": ["BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SBICARD", "SHRIRAMFIN"],
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "Auto": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "EICHERMOT"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR"],
    "Capital Goods": ["LT", "SIEMENS", "ABB", "BHEL", "CUMMINSIND"],
    "Defence": ["HAL", "BEL", "BDL", "MAZDOCK", "COCHINSHIP"],
    "Realty": ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "PHOENIXLTD"],
    "PSU": ["ONGC", "COALINDIA", "NTPC", "POWERGRID", "GAIL"],
    "Energy": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "BPCL"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL"],
}

# Minimum basket members with real data required to compute a sector series at
# all. Below this, the sector is skipped for that run rather than silently
# reporting a one-stock "average" as if it were representative.
MIN_BASKET_MEMBERS = 1

# ---------------------------------------------------------------------------
# Multi-horizon lookback windows (trading days)
# ---------------------------------------------------------------------------
HORIZON_TRADING_DAYS: dict[str, int] = {
    "1w": 5,
    "1m": 21,
    "3m": 63,
    "6m": 126,
    "1y": 252,
}

MOMENTUM_LOOKBACK_DAYS = 20     # rs_1m(t) vs rs_1m(t - 20 sessions)
SMA_WINDOWS = (20, 50, 200)     # trend/SMA stack

# ---------------------------------------------------------------------------
# Classification thresholds (7-state, per docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §1.5)
# ---------------------------------------------------------------------------
RS_STRONG_THRESHOLD = 3.0       # % — RS must exceed this to count as "strongly positive"
RS_NEAR_ZERO_BAND = 2.0         # % — band around zero used for Sideways / inflection checks
CONSISTENCY_STRONG_MIN_PCT = 60.0
CONSISTENCY_LOOKBACK_DAYS = 120  # trailing sessions used to compute consistency_pct
INFLECTION_LOOKBACK_DAYS = 40    # "as recently as N sessions ago" checks (Early Momentum / Weakening)
IMPROVING_SLOPE_LOOKBACK_DAYS = 30

# Hysteresis: a state change only commits after the raw (threshold) classification
# has agreed for this many consecutive sessions — prevents single-day flip-flopping.
MIN_DWELL_DAYS = 3

SECTOR_STATES = (
    "Strong Leader", "Early Momentum", "Improving", "Sideways",
    "Weakening", "Downtrend", "Recovery",
)
