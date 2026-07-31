"""
Position Opportunity signal evaluation + category assignment — pure and
deterministic.

Implements exactly the documented rules in
`intelligence_v2/config/position_opportunity.py`. Every function here is PURE
(no database access), so determinism is directly unit-testable.

A stock lands in exactly one category: the rules are evaluated in documented
order and the first match wins, with "Not Qualified" as the guaranteed
catch-all.
"""

from __future__ import annotations

from intelligence_v2.config.position_opportunity import (
    CATEGORY_MEANING,
    CYCLE_CONFIRMING_STAGES,
    EARLY_MOMENTUM_CONFIRMING_CATEGORIES,
    PRICE_MOMENTUM_MIN,
    RS_POSITIVE_MIN,
    SECTOR_STRENGTH_STATES,
    SIGNAL_LABELS,
)


def evaluate_signals(metrics: dict, sector_state: str | None, cycle_stage: str | None,
                     early_momentum_category: str | None, v1_ready_flag: bool) -> dict[str, bool]:
    """Evaluate all nine signals. A signal whose input is unavailable is False
    (never assumed true) — missing data can only ever weaken a case, not
    strengthen it."""
    rs_slope = metrics.get("rs_slope")
    rs_3m = metrics.get("rs_3m")
    perf_3m = metrics.get("perf_3m")

    # bool(...) coercion is load-bearing: comparisons on values that originate
    # from pandas/numpy yield numpy.bool_, which is not JSON-serialisable and
    # would break persistence of the signals payload (the same Phase 3 fix).
    return {
        "rs_improving": bool(rs_slope is not None and rs_slope > 0),
        "rs_positive": bool(rs_3m is not None and rs_3m > RS_POSITIVE_MIN),
        "above_50_sma": bool(metrics.get("above_50_sma") == "Y"),
        "above_200_sma": bool(metrics.get("above_200_sma") == "Y"),
        "price_momentum": bool(perf_3m is not None and perf_3m > PRICE_MOMENTUM_MIN),
        "sector_strength": bool(sector_state in SECTOR_STRENGTH_STATES),
        "cycle_bullish": bool(cycle_stage in CYCLE_CONFIRMING_STAGES),
        "early_momentum_confirmed": bool(early_momentum_category in EARLY_MOMENTUM_CONFIRMING_CATEGORIES),
        "v1_ready_status": bool(v1_ready_flag),
    }


def assign_category(signals: dict[str, bool]) -> tuple[str, str]:
    """Return (category, category_reason). First matching rule wins."""
    s = signals
    backdrop = s["sector_strength"] or s["cycle_bullish"] or s["early_momentum_confirmed"]

    # 1. High Conviction Position — the complete evidence set.
    if (s["rs_improving"] and s["rs_positive"] and s["above_50_sma"]
            and s["above_200_sma"] and s["price_momentum"] and backdrop):
        return "High Conviction Position", (
            "Relative Strength is improving AND positive over the medium term, price is "
            "above both its 50-SMA and 200-SMA (sustained trend) with healthy 3-month "
            "momentum, and at least one of sector strength / bullish market cycle / "
            "Phase 3 Early Momentum confirmation backs it up.")

    # 2. Position Candidate — strength building, evidence incomplete.
    if s["rs_improving"] and s["above_50_sma"] and (s["rs_positive"] or s["price_momentum"]):
        return "Position Candidate", (
            "Relative Strength is improving and price is above its 50-SMA, with either "
            "positive relative performance or healthy momentum — but the full High "
            "Conviction Position evidence set is not yet present.")

    # 3. Accumulation Watch — one credible early sign.
    if s["rs_improving"] or (s["above_50_sma"] and s["price_momentum"]):
        return "Accumulation Watch", (
            "One credible early sign is present (improving Relative Strength, or price "
            "above its 50-SMA with healthy momentum) but there is not enough "
            "corroboration to call it position-ready yet.")

    # 4. Not Qualified — guaranteed catch-all.
    return "Not Qualified", "No objective position-suitability evidence at this time."


def build_reasons(signals: dict[str, bool]) -> tuple[list[str], list[str]]:
    """(satisfied_labels, unsatisfied_labels) in the documented signal order."""
    satisfied = [SIGNAL_LABELS[k] for k, v in signals.items() if v]
    missing = [SIGNAL_LABELS[k] for k, v in signals.items() if not v]
    return satisfied, missing


def signal_count(signals: dict[str, bool]) -> int:
    """Transparent COUNT of satisfied signals. Displayed for explainability —
    never used as a ranking key here (see RANKING_KEYS_DOC) and never a
    market-wide score."""
    return sum(1 for v in signals.values() if v)


def category_meaning(category: str) -> str:
    return CATEGORY_MEANING.get(category, "")
