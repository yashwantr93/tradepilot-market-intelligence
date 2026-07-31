"""
Bearish Opportunity signal evaluation + category assignment — pure and
deterministic.

Implements exactly the documented rules in
`intelligence_v2/config/bearish_opportunity.py`. Every function here is PURE
(no database access), so determinism is directly unit-testable.

A stock lands in exactly one category: the rules are evaluated in documented
order and the first match wins, with "Not Qualified" as the guaranteed
catch-all.
"""

from __future__ import annotations

from intelligence_v2.config.bearish_opportunity import (
    CATEGORY_MEANING,
    CYCLE_WEAKNESS_STAGES,
    PRICE_MOMENTUM_MAX,
    RS_NEGATIVE_MAX,
    SECTOR_WEAKNESS_STATES,
    SIGNAL_LABELS,
    VOL_EXPANSION_MULT,
)


def evaluate_signals(metrics: dict, sector_state: str | None,
                     cycle_stage: str | None, v1_avoid_flag: bool) -> dict[str, bool]:
    """Evaluate all nine signals. A signal whose input is unavailable is False
    (never assumed true) — missing data can only ever weaken a case, not
    strengthen it."""
    rs_1m = metrics.get("rs_1m")
    rs_slope = metrics.get("rs_slope")
    perf_1m = metrics.get("perf_1m")
    vol_ratio = metrics.get("volume_ratio")

    # bool(...) coercion is load-bearing: comparisons on values that originate
    # from pandas/numpy yield numpy.bool_, which is not JSON-serialisable and
    # would break persistence of the signals payload (the same Phase 3 fix).
    return {
        "rs_weakening": bool(rs_slope is not None and rs_slope < 0),
        "rs_negative": bool(rs_1m is not None and rs_1m < RS_NEGATIVE_MAX),
        "below_20_sma": bool(metrics.get("above_20_sma") == "N"),
        "below_50_sma": bool(metrics.get("above_50_sma") == "N"),
        "price_momentum_negative": bool(perf_1m is not None and perf_1m < PRICE_MOMENTUM_MAX),
        "volume_expansion": bool(vol_ratio is not None and vol_ratio > VOL_EXPANSION_MULT),
        "sector_weakness": bool(sector_state in SECTOR_WEAKNESS_STATES),
        "cycle_weakness": bool(cycle_stage in CYCLE_WEAKNESS_STAGES),
        "v1_avoid_flag": bool(v1_avoid_flag),
    }


def assign_category(signals: dict[str, bool]) -> tuple[str, str]:
    """Return (category, category_reason). First matching rule wins."""
    s = signals
    backdrop = s["sector_weakness"] or s["cycle_weakness"]

    # 1. High Conviction Bearish — the complete evidence set.
    if (s["rs_weakening"] and s["rs_negative"] and s["below_20_sma"]
            and s["below_50_sma"] and s["price_momentum_negative"] and backdrop):
        return "High Conviction Bearish", (
            "Relative Strength is weakening AND already negative, price is below both "
            "its 20-SMA and 50-SMA with negative 1-month momentum, and the sector/market-"
            "cycle backdrop confirms.")

    # 2. Building Weakness — weakness building, evidence incomplete.
    if s["rs_weakening"] and s["below_20_sma"] and (s["rs_negative"] or s["price_momentum_negative"]):
        return "Building Weakness", (
            "Relative Strength is weakening and price is below its 20-SMA, with either "
            "underperformance or negative price momentum — but the full High Conviction "
            "Bearish evidence set is not yet present.")

    # 3. Watch for Breakdown — one credible early sign.
    if s["rs_weakening"] or (s["below_20_sma"] and s["price_momentum_negative"]):
        return "Watch for Breakdown", (
            "One credible early sign is present (weakening Relative Strength, or price "
            "below its 20-SMA with negative momentum) but there is not enough "
            "corroboration to call it a breakdown yet.")

    # 4. Not Qualified — guaranteed catch-all.
    return "Not Qualified", "No objective bearish evidence at this time."


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
