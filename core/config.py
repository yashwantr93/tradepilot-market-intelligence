"""
Central configuration for the backend.

Every tunable threshold lives here so behaviour can be adjusted without touching
logic. Nothing in this file imports Streamlit or any heavy dependency.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_STORE_DIR = PROJECT_ROOT / "data_store"
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_STORE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# SQLite by default; override with MID_DATABASE_URL for Postgres later.
DATABASE_URL = os.environ.get(
    "MID_DATABASE_URL", f"sqlite:///{DATA_STORE_DIR / 'market.db'}"
)

# ---------------------------------------------------------------------------
# Source toggles
# ---------------------------------------------------------------------------
# When True, connectors skip the network and use deterministic seeded data.
# Useful for offline development and for guaranteeing the pipeline always runs.
OFFLINE_MODE = os.environ.get("MID_OFFLINE", "1") == "1"

# Benchmark index used for relative-strength comparison.
BENCHMARK_SYMBOL = "NIFTY 50"

# ---------------------------------------------------------------------------
# Watchlist rule thresholds (rule-based only — no scoring)
# ---------------------------------------------------------------------------
WATCHLIST = {
    # Triggers use GROSS buy-side value: in real data, bulk/block deals report
    # both sides of crossed trades, so NET value cancels to ~0 and misses real
    # buy-side activity. Net is retained only for the NET_SELL caution tag.
    "big_bulk_buy_cr": 10.0,      # gross bulk BUY value (₹ Cr) to flag BIG_BULK_BUY
    "big_block_buy_cr": 25.0,     # gross block BUY value (₹ Cr) to flag BIG_BLOCK_BUY
    "repeat_lookback_days": 5,    # window for REPEAT_BUYING
    "repeat_min_sessions": 2,     # min BUY sessions within window
    "top_sector_count": 2,        # how many top sectors count as TOP_SECTOR
    "net_sell_caution_cr": 10.0,  # net SELL value (₹ Cr) to flag NET_SELL caution
}

# ---------------------------------------------------------------------------
# Technical-field thresholds (rule-based only)
# ---------------------------------------------------------------------------
TECHNICALS = {
    "sma_period": 20,                 # "Price Above 20 SMA"
    "rs_lookback_days": 50,           # relative-strength comparison window
    "rs_strong_outperf_pct": 5.0,     # stock return - benchmark return >= this -> Strong
    "rs_weak_underperf_pct": -5.0,    # <= this -> Weak (else Neutral)
    "vol_expansion_lookback": 20,     # avg-volume window
    "vol_expansion_mult": 1.5,        # today vol >= mult * avg -> expansion
    "high_52w_lookback": 252,         # trading days in 52 weeks
    # Technical status bands (distance from 52w high, in %)
    "ready_max_dist_52w_high": 15.0,  # within this % of 52w high helps "Ready"
}

# Marquee buyer list (optional). Empty by default — MARQUEE_BUYER stays dormant
# until populated. Names are matched case-insensitively as substrings.
MARQUEE_BUYERS: list[str] = [
    # e.g. "GOVERNMENT PENSION FUND GLOBAL", "SBI MUTUAL FUND", ...
]

# ---------------------------------------------------------------------------
# Sector rotation (rule-based)
# ---------------------------------------------------------------------------
# Each sector maps to a Yahoo index ticker (sector performance) and a basket of
# liquid constituents (the institutional-watchlist candidate pool). Where NSE has
# no usable index series (Defence) the basket average is used; Capital Goods uses
# the Infrastructure index as a documented proxy.
SECTORS: dict[str, dict] = {
    "Banking": {"index": "^NSEBANK",
                "basket": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"]},
    "Financial Services": {"index": "NIFTY_FIN_SERVICE.NS",
                "basket": ["BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SBICARD", "SHRIRAMFIN"]},
    "IT": {"index": "^CNXIT",
                "basket": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"]},
    "Auto": {"index": "^CNXAUTO",
                "basket": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "EICHERMOT"]},
    "Pharma": {"index": "^CNXPHARMA",
                "basket": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN"]},
    "FMCG": {"index": "^CNXFMCG",
                "basket": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR"]},
    "Capital Goods": {"index": "^CNXINFRA", "proxy": True,
                "basket": ["LT", "SIEMENS", "ABB", "BHEL", "CUMMINSIND"]},
    "Defence": {"index": None,  # no reliable index series -> basket average
                "basket": ["HAL", "BEL", "BDL", "MAZDOCK", "COCHINSHIP"]},
    "Realty": {"index": "^CNXREALTY",
                "basket": ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "PHOENIXLTD"]},
    "PSU": {"index": "^CNXPSE",
                "basket": ["ONGC", "COALINDIA", "NTPC", "POWERGRID", "GAIL"]},
    "Energy": {"index": "^CNXENERGY",
                "basket": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "BPCL"]},
    "Metals": {"index": "^CNXMETAL",
                "basket": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL"]},
}
NIFTY_INDEX_TICKER = "^NSEI"

SECTOR_ROTATION = {
    "perf_lookback_days": 20,        # 20-day performance window
    "sma_short": 20,
    "sma_long": 50,
    "rs_strong_pct": 3.0,            # RS vs Nifty >= this -> qualifies for Strong
    "rs_weak_pct": -3.0,             # RS vs Nifty <= this -> qualifies for Weak
    "accel_lookback": 10,            # short window to detect "Improving" acceleration
}

# Stock-level RS thresholds reused for the institutional watchlist.
INSTITUTIONAL = {
    "rs_lookback_days": 50,
    "rs_strong_outperf_pct": 5.0,
    "rs_weak_underperf_pct": -5.0,
    "include_trends": ["Strong", "Improving"],  # which sector trends feed the list
}

# ---------------------------------------------------------------------------
# Corporate actions (rule-based classification)
# ---------------------------------------------------------------------------
# Ordered keyword rules: the FIRST event type whose any-keyword matches the
# announcement text wins. Order matters for overlapping phrases (e.g. check
# "rights"/"preferential" before generic "fund rais"). All matching is lowercase
# substring — fully transparent, no scoring.
EVENT_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("Buyback", ["buy back", "buyback", "buy-back"]),
    ("Bonus Issue", ["bonus"]),
    ("Stock Split", ["stock split", "face value split", "sub-division",
                     "subdivision", "split of"]),
    ("Rights Issue", ["rights issue", "rights basis", "issue of rights"]),
    ("QIP", ["qip", "qualified institutional"]),
    ("Preferential Allotment", ["preferential"]),
    ("Fund Raising", ["fund rais", "raising of funds", "raise funds",
                      "fund-rais", "raising funds"]),
    ("Mergers & Acquisitions", ["merger", "amalgamation", "acquisition", "acquire",
                                "scheme of arrangement", "demerger", "takeover",
                                "stake in", "controlling stake"]),
    ("Regulatory Approval", ["usfda", "us fda", "cdsco", "approval from", "approved by",
                             "regulatory approval", "received approval", "grant of",
                             "certification", "received licen", "marketing authorisation"]),
    ("Large Order Win", ["bagging", "receiving of order", "receipt of order",
                         "order win", "work order", "letter of award", "loa ",
                         "awarded", "secures order", "bags order", "new order",
                         "contract from", "purchase order"]),
    ("Management Change", ["resignation", "appointment", "change in director",
                           "change in management", "company secretary", "cessation",
                           "chief financial officer", "cfo", "managing director",
                           "chief executive", "ceo", "key managerial", "reconstitution"]),
    ("Dividend", ["dividend"]),
]

# Impact tag per event type (transparent, fixed mapping).
EVENT_IMPACT: dict[str, str] = {
    "Buyback": "Bullish",
    "Bonus Issue": "Bullish",
    "Stock Split": "Neutral",
    "Dividend": "Neutral",
    "Rights Issue": "Bearish",
    "QIP": "Neutral",
    "Fund Raising": "Neutral",
    "Preferential Allotment": "Neutral",
    "Large Order Win": "Bullish",
    "Mergers & Acquisitions": "Bullish",
    "Regulatory Approval": "Bullish",
    "Management Change": "Neutral",
}

# Priority per event type (materiality for swing/position research).
EVENT_PRIORITY: dict[str, str] = {
    "Buyback": "High",
    "Bonus Issue": "High",
    "Large Order Win": "High",
    "Mergers & Acquisitions": "High",
    "QIP": "High",
    "Fund Raising": "High",
    "Preferential Allotment": "High",
    "Regulatory Approval": "High",
    "Rights Issue": "Medium",
    "Stock Split": "Medium",
    "Management Change": "Medium",
    "Dividend": "Low",
}

# ---------------------------------------------------------------------------
# Results tracker (rule-based classification)
# ---------------------------------------------------------------------------
RESULTS = {
    "strong_growth_pct": 15.0,   # rev & profit YoY growth >= this -> Strong
    "weak_decline_pct": 0.0,     # rev or profit YoY growth < this -> Weak
    "yoy_quarters_back": 4,      # 4 quarters back = same quarter last year
}

# Universe for the results tracker: the union of all sector baskets (liquid,
# well-covered large/mid caps). Built from SECTORS to avoid a duplicate list.
def results_universe() -> list[str]:
    syms: list[str] = []
    for cfg in SECTORS.values():
        syms.extend(cfg["basket"])
    # de-dup, preserve order
    seen, out = set(), []
    for s in syms:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

# Data-freshness SLA (seconds) used for staleness flags.
FRESHNESS_SLA = {
    "intraday": 10 * 60,
    "eod": 24 * 60 * 60,
}
