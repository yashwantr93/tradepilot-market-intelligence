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
# MID_DATA_DIR / MID_LOGS_DIR relocate data_store/ and logs/ as a whole — e.g.
# to a Render persistent disk mount point. Unset, both default to exactly
# where they've always lived (relative to the project root), so local/Windows
# usage is completely unaffected.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_STORE_DIR = Path(os.environ.get("MID_DATA_DIR", str(PROJECT_ROOT / "data_store")))
LOGS_DIR = Path(os.environ.get("MID_LOGS_DIR", str(PROJECT_ROOT / "logs")))
DATA_STORE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

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
# Deployment context — Phase 15
# ---------------------------------------------------------------------------
# Render sets `RENDER=true` in every service's runtime environment (Render's
# own documented convention, not something this project invented) — read-only
# detection, no side effects. Used ONLY by the UI freshness display (see
# data/contracts.py::refresh_status() callers) to state plainly that
# production is a git-shipped, point-in-time SQLite snapshot (per
# DEPLOYMENT.md's "git-shipped read-only database snapshot" pattern), never
# a live-refreshing instance — so a trader on the deployed site is never left
# assuming "CURRENT" means the same thing there as it does on the local,
# Task-Scheduler-refreshed instance. Never used to change any trading logic,
# threshold, or calculation — presentation-only.
IS_RENDER = os.environ.get("RENDER", "").lower() == "true"

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
# announcement text wins. Order matters for overlapping phrases — most specific
# / most adverse-signaling rules are placed BEFORE broader, positive-leaning
# ones so a specific negative meaning is never swallowed by a generic positive
# keyword (see the two Phase-1 fixes below). All matching is lowercase
# substring — fully transparent, no scoring.
#
# PHASE 1 FIXES (root-caused against real stored `corporate_actions` text,
# not assumed):
#   1. ESOP/stock-option grant disclosures ("ESOP/ESOS/ESPS ... grant of
#      options") were matching Regulatory Approval's bare "grant of" keyword.
#      Root cause: keyword overlap, not ordering — "grant of" is generic
#      enough to match both "grant of approval" and "grant of options". Fix:
#      (a) a new, more specific "Employee Stock Options" rule ahead of
#      Regulatory Approval, and (b) "grant of" narrowed to "grant of
#      approval"/"grant of licen"/"grant of certificate" in Regulatory
#      Approval so it can no longer match ESOP text at all.
#   2. Adverse FDA/regulator text ("... received a Warning Letter from
#      USFDA") was matching Regulatory Approval's "usfda"/"us fda" keyword —
#      a warning letter MENTIONS the regulator but is an adverse action, not
#      an approval. Root cause: same keyword-overlap pattern. Fix: a new
#      "Regulatory / Legal Action" rule, containing the adverse-signal
#      phrases ("warning letter", "import alert", "form 483", "show cause"),
#      placed BEFORE Regulatory Approval so the adverse meaning is caught
#      first.
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

    # --- Employee Stock Options — checked BEFORE Regulatory Approval so
    #     "grant of options"/ESOP disclosures never reach that rule. ---
    ("Employee Stock Options", ["esop", "esos", "esps", "employee stock option",
                                "grant of option", "grant of stock option",
                                "exercise of option", "allotment of option"]),

    # --- Regulatory / Legal Action (NEGATIVE) — checked BEFORE Regulatory
    #     Approval so adverse regulator text is never read as an approval. ---
    ("Regulatory / Legal Action", ["warning letter", "import alert", "form 483",
                                   "show cause notice", "adjudication order",
                                   "sebi order", "sebi action", "penalty imposed",
                                   "regulatory penalty", "license cancel",
                                   "licence cancel", "license suspend",
                                   "licence suspend", "search and seizure",
                                   "raided by", "fraud investigation",
                                   "accounting irregularit", "restatement of"]),

    ("Auditor Resignation", ["resignation of statutory auditor",
                             "resignation of the statutory auditor",
                             "resignation of auditor", "auditor resign",
                             "auditor has resigned", "auditor tendered resignation"]),

    ("Order Cancellation", ["cancellation of order", "order cancellation",
                            "order cancelled", "termination of contract",
                            "contract terminated", "loss of order",
                            "order withdrawn", "order has been cancelled"]),

    ("Credit Rating Downgrade", ["rating downgrade", "downgraded the rating",
                                 "downgraded its rating", "rating action: downgrade",
                                 "rating revised downward", "revised the rating downward"]),
    ("Credit Rating Upgrade", ["rating upgrade", "upgraded the rating",
                               "upgraded its rating", "rating action: upgrade",
                               "rating revised upward", "revised the rating upward"]),

    ("Debt Default", ["default in payment", "delay in payment of interest",
                      "delay in payment of principal", "classified as npa",
                      "debt default", "default on borrowing"]),

    ("Promoter Pledge Change", ["pledge of shares", "increase in pledge",
                                "shares pledged", "invocation of pledge",
                                "release of pledge", "encumbrance"]),

    ("Operations Disruption", ["fire at", "plant fire", "fire broke out",
                              "temporary suspension of operations",
                              "force majeure", "production halt",
                              "plant shutdown", "plant accident"]),

    ("Product Recall", ["product recall", "voluntary recall", "recall of",
                        "market withdrawal"]),

    # --- Regulatory Approval (POSITIVE) — narrowed from bare "grant of" to
    #     specific approval-grant phrases so it no longer catches ESOP text. ---
    ("Regulatory Approval", ["usfda approv", "us fda approv", "cdsco", "approval from",
                             "approved by", "regulatory approval", "received approval",
                             "grant of approval", "grant of licen", "grant of certificat",
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

# Impact tag per event type (transparent, fixed mapping). Four values are
# valid: Bullish / Bearish / Neutral / Ambiguous. "Ambiguous" is used where
# keyword matching alone cannot reliably infer direction — e.g. "Mergers &
# Acquisitions" collapses acquirer and target (opposite trade implications)
# into one keyword rule, and "Management Change" collapses a routine
# appointment with an unexplained senior resignation. Forcing either into
# Bullish/Bearish would be inventing a direction the evidence doesn't
# support (Phase 1 explicitly requires NEUTRAL/AMBIGUOUS/UNKNOWN instead).
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
    "Mergers & Acquisitions": "Ambiguous",     # CHANGED from Bullish — see docstring above
    "Regulatory Approval": "Bullish",
    "Management Change": "Ambiguous",           # CHANGED from Neutral — see docstring above
    "Employee Stock Options": "Neutral",
    "Regulatory / Legal Action": "Bearish",
    "Auditor Resignation": "Bearish",
    "Order Cancellation": "Bearish",
    "Credit Rating Downgrade": "Bearish",
    "Credit Rating Upgrade": "Bullish",
    "Debt Default": "Bearish",
    "Promoter Pledge Change": "Ambiguous",       # a pledge RELEASE is Bullish-leaning,
                                                  # an INCREASE is Bearish-leaning; the
                                                  # keyword rule can't yet tell them apart
    "Operations Disruption": "Bearish",
    "Product Recall": "Bearish",
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
    "Employee Stock Options": "Low",
    "Regulatory / Legal Action": "High",
    "Auditor Resignation": "High",
    "Order Cancellation": "High",
    "Credit Rating Downgrade": "High",
    "Credit Rating Upgrade": "Medium",
    "Debt Default": "High",
    "Promoter Pledge Change": "Medium",
    "Operations Disruption": "Medium",
    "Product Recall": "Medium",
}

# All valid direction values an event classification may take. Kept as an
# explicit set (rather than inferred from EVENT_IMPACT's values) so tests and
# future consumers can validate against it directly.
EVENT_DIRECTIONS = {"Bullish", "Bearish", "Neutral", "Ambiguous"}

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

# ---------------------------------------------------------------------------
# Expectation baseline — Phase 1 Event Intelligence Foundation (rule-based,
# no analyst-consensus feed). See core/processing/expectation.py.
# ---------------------------------------------------------------------------
EXPECTATION = {
    # How many of the most recent prior YoY prints to average into the
    # trailing-expectation baseline. Deliberately small — this is an internal
    # proxy, not a statistically validated forecast (see module docstring).
    "trailing_lookback": 3,
    "min_samples_for_expectation": 1,   # below this, expectation stays UNKNOWN
    "min_samples_for_medium_confidence": 2,  # 1 sample -> LOW, 2+ -> MEDIUM (never HIGH
                                              # in Phase 1 — see expectation.py docstring)
}

# ---------------------------------------------------------------------------
# Materiality — Phase 1 foundation (results-surprise only; corporate-action
# ratio-based materiality is explicitly deferred, see Phase 1 report).
# These are a documented STARTING POINT, not evidence-derived precise
# cutoffs — reuses the existing RESULTS strong_growth_pct bar as the anchor
# rather than inventing a new number. Expected to be recalibrated once the
# Validation phase can backtest against real surprise/forward-return data.
# ---------------------------------------------------------------------------
MATERIALITY = {
    "results_surprise_low_pct": 5.0,     # |surprise| below this -> LOW
    "results_surprise_medium_pct": 10.0,  # below this -> MEDIUM
    "results_surprise_high_pct": 20.0,    # below this -> HIGH, at/above -> TRANSFORMATIONAL
}

# ---------------------------------------------------------------------------
# Corporate-action materiality — Phase 2. Two categories production-wired
# (see core/processing/corp_action_materiality.py); both threshold sets are
# EVIDENCE-DERIVED, not invented:
#
#   dividend_yield_*: calibrated from the empirical distribution of 59 real,
#   computable single-event dividend yields (per-share amount / latest close)
#   in the local corporate_actions x price_history data, measured during
#   this phase's audit: p25=0.29%, median=0.64%, p75=1.09%, p90=1.44%,
#   max=2.61%. LOW/MEDIUM boundaries are set at approximately the median and
#   p75; the HIGH/TRANSFORMATIONAL boundary (3.0%) is set just ABOVE the
#   observed maximum (2.61%) so the largest real dividend seen locally
#   (ITC) lands in HIGH, not TRANSFORMATIONAL — that tier is reserved for
#   something genuinely beyond anything observed so far.
#
#   large_order_value_*: order value as % of trailing 4-quarter revenue.
#   Only ONE real corporate-action row (LT) currently has both an
#   extractable order value AND `results_quarterly` revenue coverage — not
#   enough to calibrate empirically. These reuse the Results-surprise
#   thresholds by REASONED ANALOGY (both are "how big is this relative to
#   the company, as a %"), not measurement. Documented explicitly as a
#   starting point to recalibrate once more order-win events land on
#   results_quarterly-covered symbols.
# ---------------------------------------------------------------------------
CORP_ACTION_MATERIALITY = {
    "dividend_yield_low_pct": 0.5,
    "dividend_yield_medium_pct": 1.0,
    "dividend_yield_high_pct": 3.0,
    "large_order_value_low_pct": 5.0,
    "large_order_value_medium_pct": 10.0,
    "large_order_value_high_pct": 20.0,
}

# ---------------------------------------------------------------------------
# Market Reaction — Phase 3 (event_intelligence/). Calibrated from the
# empirical distribution of 76 real, currently-computable 5-session relative
# returns in local data (see event_intelligence/reaction_classifier.py's
# docstring for the full quartile measurement): p10=-5.5%, p25=-2.0%,
# median=+0.3%, p75=+2.5%, p90=+6.7%. NEUTRAL band and the moderate
# threshold sit at ~p25/p75 (2.5%); the strong threshold sits at ~p10/p90
# (7%, rounded). A starting point to recalibrate as coverage grows, not a
# statistically final cutoff — same status as CORP_ACTION_MATERIALITY.
# ---------------------------------------------------------------------------
MARKET_REACTION = {
    "moderate_pct": 2.5,   # |relative 5-session return| beyond this -> POSITIVE/NEGATIVE
    "strong_pct": 7.0,     # beyond this -> STRONG POSITIVE/STRONG NEGATIVE
}

# ---------------------------------------------------------------------------
# Sector/Theme Emergence — Phase 6 (event_intelligence/sector_state.py).
# Calibrated from the real cross-sectional distribution of the ~13 GICS
# sectors + curated themes measured at this phase's audit date — see the
# Phase 6 report's STATE MODEL section for the exact measured values. With
# only ~13 sectors/themes total this is a genuinely small sample; treat
# these as a reasoned starting point, same status as every other threshold
# set built this session, NOT a statistically fit model.
# ---------------------------------------------------------------------------
SECTOR_THEME = {
    "breadth_moderate_pct": 40.0,   # % above 20-SMA to count as "moderate" breadth
    "breadth_high_pct": 65.0,       # % above 20-SMA to count as "high/broad" breadth
    "breadth_change_noise_floor_pct": 5.0,   # min breadth-percentage-point change to call it a real trend
    "rs_change_noise_floor": 1.0,   # min avg-RS-percentage-point change to call it a real trend
    "min_events_for_emerging": 2,   # min positive material events (in-window) to support EMERGING
                                     # absent a breadth uptick
    "event_lookback_days": 30,      # rolling window for event/catalyst density
    "trend_lookback_sessions": 20,  # sessions back for the breadth/RS "prior" comparison point
}
