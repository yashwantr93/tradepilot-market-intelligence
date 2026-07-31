"""
Early Momentum signal evaluation + category assignment — pure and deterministic.

Implements exactly the documented rules in
`intelligence_v2/config/early_momentum.py`. Every function here is PURE (no
database access), so determinism is directly unit-testable.

A stock lands in exactly one category: the rules are evaluated in documented
order and the first match wins, with "Not Qualified" as the guaranteed
catch-all.
"""

from __future__ import annotations

from intelligence_v2.config.early_momentum import (
    CATEGORY_MEANING,
    CYCLE_CONFIRMING_STAGES,
    PRICE_MOMENTUM_MIN,
    RS_POSITIVE_MIN,
    SECTOR_STRENGTH_STATES,
    SIGNAL_LABELS,
    VOL_EXPANSION_MULT,
)


def evaluate_signals(metrics: dict, sector_state: str | None,
                     cycle_stage: str | None, in_v1_watchlist: bool) -> dict[str, bool]:
    """Evaluate all nine signals. A signal whose input is unavailable is False
    (never assumed true) — missing data can only ever weaken a case, not
    strengthen it."""
    rs_1m = metrics.get("rs_1m")
    rs_slope = metrics.get("rs_slope")
    perf_1m = metrics.get("perf_1m")
    vol_ratio = metrics.get("volume_ratio")

    # bool(...) coercion is load-bearing: comparisons on values that originate
    # from pandas/numpy yield numpy.bool_, which is not JSON-serialisable and
    # would break persistence of the signals payload.
    return {
        "rs_improving": bool(rs_slope is not None and rs_slope > 0),
        "rs_positive": bool(rs_1m is not None and rs_1m > RS_POSITIVE_MIN),
        "above_20_sma": bool(metrics.get("above_20_sma") == "Y"),
        "above_50_sma": bool(metrics.get("above_50_sma") == "Y"),
        "price_momentum": bool(perf_1m is not None and perf_1m > PRICE_MOMENTUM_MIN),
        "volume_expansion": bool(vol_ratio is not None and vol_ratio > VOL_EXPANSION_MULT),
        "sector_strength": bool(sector_state in SECTOR_STRENGTH_STATES),
        "cycle_confirmation": bool(cycle_stage in CYCLE_CONFIRMING_STAGES),
        "v1_opportunity": bool(in_v1_watchlist),
    }


def assign_category(signals: dict[str, bool]) -> tuple[str, str]:
    """Return (category, category_reason). First matching rule wins."""
    s = signals
    backdrop = s["sector_strength"] or s["cycle_confirmation"]

    # 1. Emerging Leader — the complete evidence set.
    if (s["rs_improving"] and s["rs_positive"] and s["above_20_sma"]
            and s["above_50_sma"] and s["price_momentum"] and backdrop):
        return "Emerging Leader", (
            "Relative Strength is improving AND already positive, price is above both "
            "its 20-SMA and 50-SMA with positive 1-month momentum, and the sector/market-"
            "cycle backdrop confirms.")

    # 2. Building Momentum — strength building, evidence incomplete.
    if s["rs_improving"] and s["above_20_sma"] and (s["rs_positive"] or s["price_momentum"]):
        return "Building Momentum", (
            "Relative Strength is improving and price is above its 20-SMA, with either "
            "outperformance or positive price momentum — but the full Emerging Leader "
            "evidence set is not yet present.")

    # 3. Watch Closely — one credible early sign.
    if s["rs_improving"] or (s["above_20_sma"] and s["price_momentum"]):
        return "Watch Closely", (
            "One credible early sign is present (improving Relative Strength, or price "
            "above its 20-SMA with positive momentum) but there is not enough "
            "corroboration to call it momentum yet.")

    # 4. Not Qualified — guaranteed catch-all.
    return "Not Qualified", "No objective early-momentum evidence at this time."


def build_reasons(signals: dict[str, bool]) -> tuple[list[str], list[str]]:
    """(satisfied_labels, unsatisfied_labels) in the documented signal order."""
    satisfied = [SIGNAL_LABELS[k] for k, v in signals.items() if v]
    missing = [SIGNAL_LABELS[k] for k, v in signals.items() if not v]
    return satisfied, missing


def signal_count(signals: dict[str, bool]) -> int:
    """Transparent COUNT of satisfied signals. Used only as a within-category
    ordering key — never a market-wide score, never compared across categories."""
    return sum(1 for v in signals.values() if v)


def category_meaning(category: str) -> str:
    return CATEGORY_MEANING.get(category, "")
