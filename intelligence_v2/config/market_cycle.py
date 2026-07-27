"""
Market Cycle Engine — stage definitions, thresholds, and the FULL documented
rule set. This file is the single written source of truth for how a sector is
placed on the cycle wheel; `processors/cycle_classifier.py` implements exactly
what is documented here and nothing more.

No AI, no ML, no scoring, no probability. Every stage is decided by explicit
if/else threshold comparisons on values already computed and stored by Phase 1
(`sector_intelligence_daily`).

THE WHEEL
---------
    Accumulation -> Early Momentum -> Strong Trend -> Mature Trend
         ^                                                  |
         |                                                  v
     Recovery <- Weak Trend <- Distribution <---------------+

INPUT DIMENSIONS (exactly the five the Phase 2 brief specifies)
---------------------------------------------------------------
  1. Multi-timeframe performance  -> perf_1w / perf_1m / perf_3m / perf_6m / perf_1y
  2. Relative Strength            -> rs_1w / rs_1m / rs_3m / rs_6m / rs_1y
  3. Trend Direction              -> above_20_sma / above_50_sma / above_200_sma
  4. Momentum                     -> momentum_1m  (rate-of-change of RS itself)
  5. Consistency                  -> consistency_pct

NOTE ON VOLUME: the Phase 2 architecture note in
docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §2.3 also mentioned an up-day/down-day
volume signal for Accumulation/Distribution. The Phase 2 build brief enumerates
the five dimensions above and restricts the data source to
`sector_intelligence_daily`, which does not carry volume. Distribution is
therefore detected structurally instead — price still above its 50-SMA (i.e.
still elevated) while short-term RS has already rolled over and momentum is
negative. This is a deliberate, documented simplification, not an oversight;
adding volume confirmation is recorded as a future refinement.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# The seven stages (exactly one is assigned per sector per day)
# ---------------------------------------------------------------------------
CYCLE_STAGES = (
    "Accumulation",
    "Early Momentum",
    "Strong Trend",
    "Mature Trend",
    "Distribution",
    "Weak Trend",
    "Recovery",
)

# Canonical forward order around the wheel (used only for display ordering and
# to describe whether a transition advanced or regressed — never for scoring).
CYCLE_WHEEL_ORDER = {stage: i for i, stage in enumerate(CYCLE_STAGES)}

# ---------------------------------------------------------------------------
# Thresholds — every number the classifier uses lives here
# ---------------------------------------------------------------------------
RS_STRONG = 3.0          # % — RS above this counts as "strongly positive"
RS_FLAT_BAND = 3.0       # % — |RS| within this band is treated as "not established"
MOMENTUM_FLAT = 0.0      # momentum_1m >= this = not decelerating

# ---------------------------------------------------------------------------
# Hysteresis — "N of the last M sessions", NOT "M consecutive identical"
# ---------------------------------------------------------------------------
# A stage change commits only when the candidate stage appears in at least
# MIN_CYCLE_CONFIRMATIONS of the last MIN_CYCLE_DWELL_DAYS readings (today
# included).
#
# WHY NOT "consecutive identical": that was the first implementation and it
# failed on real data. Raw readings legitimately alternate near a threshold
# (e.g. Defence oscillated Strong/Recovery/Accumulation almost every session),
# so a run of 3 identical raw stages never occurred and the confirmed stage
# stayed frozen on the first-ever reading for the entire history — the
# dashboard would have shown "Strong Trend" for a sector whose every recent
# reading said otherwise. A "2 of last 3" majority is equally deterministic,
# still blocks single-session flips, but cannot get permanently stuck.
MIN_CYCLE_DWELL_DAYS = 3       # size of the confirmation window (sessions, incl. today)
MIN_CYCLE_CONFIRMATIONS = 2    # how many of that window must show the candidate stage

# Confidence-note thresholds (transparency about data sufficiency, NOT a score).
SHORT_HISTORY_DAYS = 20          # below this, cycle history is called "short"
LOW_CONSISTENCY_PCT = 20.0       # below this, consistency is called "not yet meaningful"

# ---------------------------------------------------------------------------
# Documented rules, in strict evaluation order.
# The FIRST rule that matches wins — this is what guarantees exactly one stage
# per sector. The final fallback guarantees no sector is ever left unclassified.
# ---------------------------------------------------------------------------
STAGE_RULES_DOC: list[dict] = [
    {
        "stage": "Early Momentum",
        "order": 1,
        "conditions": [
            "Price above 50-SMA",
            "RS strongly positive short-term: RS 1W > +3% AND RS 1M > +3%",
            "Leadership NOT yet established (RS 3M or RS 6M still within/below the +3% band)",
            "Momentum improving (momentum_1m > 0)",
        ],
        "behaviour": "Fresh upturn — money appears to be rotating in; leadership not yet confirmed.",
        "note": "Evaluated BEFORE Strong Trend on purpose: a sector whose 3M/6M RS is "
                "only marginally positive is a fresh mover, not an established leader. "
                "The 'not yet established' condition means genuine long-standing "
                "leaders fall through to Strong Trend instead.",
    },
    {
        "stage": "Strong Trend",
        "order": 2,
        "conditions": [
            "Price above 20-SMA AND above 50-SMA",
            "RS positive over 1M, 3M and 6M",
            "Momentum not decelerating (momentum_1m >= 0)",
        ],
        "behaviour": "Trend continuation likely while strength and momentum persist.",
    },
    {
        "stage": "Distribution",
        "order": 3,
        "conditions": [
            "Price still above 50-SMA (still elevated)",
            "Short-term RS has rolled over: RS 1W < 0 AND RS 1M < 0",
            "Momentum decelerating (momentum_1m < 0)",
        ],
        "behaviour": "Topping behaviour — strength is leaving while price is still high.",
    },
    {
        "stage": "Mature Trend",
        "order": 4,
        "conditions": [
            "Price above 50-SMA",
            "RS still positive over 3M",
            "Momentum decelerating (momentum_1m < 0) OR short-term RS now lagging medium-term (RS 1M < RS 3M)",
        ],
        "behaviour": "Trend intact but slowing — late-stage participation, tighter risk warranted.",
    },
    {
        "stage": "Recovery",
        "order": 5,
        "conditions": [
            "Long-term laggard (RS 6M < 0 OR RS 1Y < 0)",
            "Short/medium term turning up (RS 1M > 0)",
            "Price has reclaimed its 20-SMA",
        ],
        "behaviour": "Laggard inflecting upward — early, needs confirmation before it becomes a trend.",
    },
    {
        "stage": "Accumulation",
        "order": 6,
        "conditions": [
            "Price below 50-SMA (still under trend)",
            "RS 1M still negative",
            "But deterioration has stopped (momentum_1m >= 0)",
        ],
        "behaviour": "Basing — decline is stalling; no trend yet, watch for a 50-SMA reclaim.",
    },
    {
        "stage": "Weak Trend",
        "order": 7,
        "conditions": [
            "Price below 50-SMA",
            "RS 1M negative",
        ],
        "behaviour": "Downward drift persists — avoid long exposure until strength returns.",
    },
    {
        "stage": "FALLBACK",
        "order": 8,
        "conditions": [
            "No rule above matched (rare, directionless readings).",
            "If price is above its 50-SMA -> Mature Trend, otherwise -> Accumulation.",
        ],
        "behaviour": "Directionless — treated as the nearest neutral stage for its trend position.",
    },
]

# Per-stage plain-English "possible behaviour" note shown on the dashboard.
STAGE_BEHAVIOUR = {r["stage"]: r["behaviour"] for r in STAGE_RULES_DOC if r["stage"] != "FALLBACK"}
