"""
Sector/Theme lifecycle state classification — Phase 6.

Deliberately named to avoid colliding with V2's per-STOCK "Early Momentum"
engine (`intelligence_v2.processors.momentum_classifier`) — this module
classifies a SECTOR/THEME as a whole; V2's engine, unchanged, classifies
individual stocks. `EARLY_MOMENTUM` as a sector-level state name is kept
(matches the task brief's own vocabulary) but the two are unrelated
computations over different universes.

States (HEURISTIC, ordered strictest-evidence-first, mirroring V2's own
`sector_classifier.classify_raw` evaluation-order pattern for consistency):

  CONFIRMED_STRONG — already broad AND still accelerating
  MATURE           — already broad but no longer accelerating (extended,
                     not necessarily about to fall — just not "early")
  EARLY_MOMENTUM    — breadth moderate-to-high AND both breadth and RS
                     actively expanding
  DEVELOPING        — breadth still low-to-moderate but expanding, RS
                     improving — the earliest state with real, if thin,
                     confirming evidence
  EMERGING          — breadth still low, but RS turning up and at least one
                     other independent signal (event density or nascent
                     breadth tick-up) supports it — the thinnest, most
                     tentative state; requires hysteresis to confirm before
                     being reported (see below)
  WEAKENING         — RS negative AND declining AND breadth contracting —
                     was stronger, now deteriorating (this sector/theme's
                     bearish-context state — see DIRECTION_CONTEXT)
  SIDEWAYS          — default; no directional conviction either way

Breadth/RS-change thresholds are calibrated from the REAL measured
cross-sectional distribution of the ~13 sectors/themes in local data at
this phase's audit date — see `core/config.py::SECTOR_THEME` for the exact
values and the measurement they came from. With only ~13 sectors/themes
total, this is an explicitly SMALL sample — a reasoned starting point, not
a statistically fit model (same status as every other threshold set built
this session).

Persistence (noise control): raw state → confirmed state goes through the
EXACT SAME hysteresis function V2's Sector Intelligence already uses
(`intelligence_v2.processors.sector_classifier.apply_hysteresis`) — reused,
not reimplemented, per the phase brief's explicit "do not create duplicate
calculations" instruction.
"""

from __future__ import annotations

from core.config import SECTOR_THEME as T
from intelligence_v2.processors.sector_classifier import apply_hysteresis  # reused, not duplicated

STATES = ("CONFIRMED_STRONG", "MATURE", "EARLY_MOMENTUM", "DEVELOPING",
         "EMERGING", "WEAKENING", "SIDEWAYS")
DIRECTION_CONTEXT = {
    "CONFIRMED_STRONG": "BULLISH", "MATURE": "BULLISH", "EARLY_MOMENTUM": "BULLISH",
    "DEVELOPING": "BULLISH", "EMERGING": "BULLISH",
    "WEAKENING": "BEARISH", "SIDEWAYS": "NEUTRAL",
}
# Dwell-days-before-confirming is NOT redefined here — `apply_hysteresis`
# (imported above) uses V2's own MIN_DWELL_DAYS (=3, intelligence_v2/config/
# sectors.py) internally. Reusing it means this engine's persistence
# requirement is identical to, not merely inspired by, V2's own.


def classify_raw(current: dict, prior: dict, positive_event_count: int,
                 negative_event_count: int) -> str:
    """`current`/`prior` — aggregate_sector_metrics() results (today, and
    ~20 sessions ago). Returns the RAW (pre-hysteresis) state."""
    breadth = current.get("pct_above_20sma")
    rs = current.get("avg_rs_1m")
    if breadth is None or rs is None:
        return "SIDEWAYS"  # insufficient data to classify — default, not fabricated

    prior_breadth = prior.get("pct_above_20sma") if prior else None
    prior_rs = prior.get("avg_rs_1m") if prior else None
    breadth_change = (breadth - prior_breadth) if prior_breadth is not None else None
    rs_change = (rs - prior_rs) if prior_rs is not None else None

    breadth_expanding = breadth_change is not None and breadth_change >= T["breadth_change_noise_floor_pct"]
    breadth_contracting = breadth_change is not None and breadth_change <= -T["breadth_change_noise_floor_pct"]
    rs_improving = rs_change is not None and rs_change >= T["rs_change_noise_floor"]
    rs_declining = rs_change is not None and rs_change <= -T["rs_change_noise_floor"]

    high_breadth = breadth >= T["breadth_high_pct"]
    moderate_breadth = breadth >= T["breadth_moderate_pct"]

    # 1. CONFIRMED_STRONG — already broad, still accelerating
    if high_breadth and rs > 0 and rs_improving:
        return "CONFIRMED_STRONG"
    # 2. MATURE — already broad, no longer accelerating
    if high_breadth and rs > 0:
        return "MATURE"
    # 3. EARLY_MOMENTUM — moderate-plus breadth, both expanding
    if moderate_breadth and breadth_expanding and rs_improving:
        return "EARLY_MOMENTUM"
    # 4. DEVELOPING — breadth still building but trending the right way
    if breadth_expanding and rs_improving:
        return "DEVELOPING"
    # 5. EMERGING — earliest, thinnest: RS turning up plus SOME other signal
    if rs_improving and (breadth_expanding or positive_event_count >= T["min_events_for_emerging"]):
        return "EMERGING"
    # 6. WEAKENING — declining from wherever it was
    if rs < 0 and rs_declining and breadth_contracting:
        return "WEAKENING"
    return "SIDEWAYS"


def classify_participation(constituent_metrics: dict[str, dict],
                           sector_avg_rs_1m: float | None) -> dict[str, list[str]]:
    """Leaders / early participants / laggards / non-participants — per
    the task's explicit definitions. Relative to the SECTOR's own average,
    not an absolute cutoff, so this is meaningful regardless of the
    sector's overall state."""
    leaders, early, lagging, non_participants = [], [], [], []
    if sector_avg_rs_1m is None:
        return {"leaders": [], "early_participants": [], "laggards": [], "non_participants": []}

    for symbol, m in constituent_metrics.items():
        if m is None or m.get("rs_1m") is None:
            non_participants.append(symbol)
            continue
        rs1m, rs1w = m["rs_1m"], m.get("rs_1w")
        above_sma = m.get("above_20sma") == "Y"
        if rs1m > sector_avg_rs_1m and above_sma:
            leaders.append(symbol)
        elif rs1w is not None and rs1w > 0 and rs1m <= sector_avg_rs_1m:
            early.append(symbol)  # short-term turning up, not yet leading on the longer window
        elif rs1m < 0:
            lagging.append(symbol)
        else:
            non_participants.append(symbol)

    return {"leaders": sorted(leaders), "early_participants": sorted(early),
           "laggards": sorted(lagging), "non_participants": sorted(non_participants)}


def build_evidence(state: str, current: dict, prior: dict, positive_event_count: int,
                   negative_event_count: int, participation: dict[str, list]) -> tuple[list, list]:
    """Human-readable evidence_for / evidence_against — never invents a
    number not already in `current`/`prior`/the counts passed in."""
    evidence_for, evidence_against = [], []
    breadth, rs = current.get("pct_above_20sma"), current.get("avg_rs_1m")

    if breadth is not None:
        evidence_for.append(f"{breadth:.0f}% of constituents above their 20-session SMA "
                            f"({current['measurable_count']}/{current['constituent_count']} measurable).")
    if rs is not None:
        evidence_for.append(f"Average 1-month relative strength vs. benchmark: {rs:+.2f}%.")
    prior_breadth = prior.get("pct_above_20sma") if prior else None
    if breadth is not None and prior_breadth is not None:
        change = breadth - prior_breadth
        (evidence_for if change > 0 else evidence_against).append(
            f"Breadth {'expanded' if change > 0 else 'contracted'} {abs(change):.1f}pp "
            f"over the trend-lookback window."
        )
    if positive_event_count > 0:
        evidence_for.append(f"{positive_event_count} positive material event(s) among constituents "
                            "in the recent window.")
    if negative_event_count > 0:
        evidence_against.append(f"{negative_event_count} negative material event(s) among "
                                "constituents in the recent window.")
    if len(participation.get("leaders", [])) <= 2 and state not in ("SIDEWAYS", "WEAKENING"):
        evidence_against.append(f"Leadership is narrow ({len(participation['leaders'])} leader(s)) — "
                                "not yet broad participation.")
    if not evidence_for:
        evidence_for.append("No confirming evidence currently available.")
    if not evidence_against:
        evidence_against.append("No specific contrary evidence identified — data completeness "
                                "for this sector/theme should still be checked independently.")
    return evidence_for, evidence_against
