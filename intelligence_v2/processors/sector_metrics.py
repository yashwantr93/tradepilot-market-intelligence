"""
Pure multi-horizon metric calculations — no database access, so these are
directly unit-testable against synthetic series (see tests/test_phase1_*).

All formulas are exactly as specified in
docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §1.4.

REFACTORED (shared Relative Strength Engine, mandatory defect fix): `rs_over`
previously computed the sector leg and the Nifty leg by POSITION offset
independently within each series. Since the sector series and the benchmark
series have different date coverage (thin baskets, staggered listing/gap
dates), "N sessions back" resolved to a different CALENDAR date in each
series — silently comparing performance over different windows and calling
the difference "relative strength." This is the exact defect Phase 3 already
found and fixed for stocks; `rs_over`/`compute_metrics` now delegate to the
same shared, calendar-aligned engine instead of repeating the bug here.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from intelligence_v2.config.sectors import (
    HORIZON_TRADING_DAYS,
    IMPROVING_SLOPE_LOOKBACK_DAYS,
    INFLECTION_LOOKBACK_DAYS,
    MOMENTUM_LOOKBACK_DAYS,
    SMA_WINDOWS,
)
from intelligence_v2.processors.shared_relative_strength import (
    above_moving_average,
    calculate_rs_trend,
    performance_over,
    position_at_or_before,
    rs_as_of,
)


def perf_over(series: pd.Series, as_of: dt.date, trading_days: int) -> float | None:
    """% change from `trading_days` sessions before `as_of` to `as_of`."""
    pos = position_at_or_before(series.index, as_of)
    if pos is None:
        return None
    return performance_over(series, pos, trading_days)


def rs_over(sector_series: pd.Series, nifty_series: pd.Series, as_of: dt.date,
           trading_days: int) -> tuple[float | None, float | None, float | None]:
    """Returns (sector_perf, nifty_perf, relative_strength) for one horizon,
    calendar-aligned via the shared engine (see module docstring)."""
    return rs_as_of(sector_series, nifty_series, as_of, trading_days)


def above_sma(series: pd.Series, as_of: dt.date, window: int) -> str | None:
    """Y/N — None if there isn't `window` days of history yet."""
    return above_moving_average(series, as_of, window)


def compute_metrics(sector_series: pd.Series, nifty_series: pd.Series,
                    as_of: dt.date) -> dict:
    """All performance/RS/momentum/trend fields for one sector as of one date.

    Every value that cannot be computed from available history is None (never
    guessed) — the same honest-gap convention used throughout this project.
    """
    out: dict = {}
    rs_values: dict[str, float | None] = {}

    for horizon, days in HORIZON_TRADING_DAYS.items():
        sp, np_, rs = rs_over(sector_series, nifty_series, as_of, days)
        out[f"perf_{horizon}"] = sp
        out[f"nifty_perf_{horizon}"] = np_
        out[f"rs_{horizon}"] = rs
        rs_values[horizon] = rs

    pos = position_at_or_before(sector_series.index, as_of)

    # momentum_1m = rs_1m(t) - rs_1m(t - MOMENTUM_LOOKBACK_DAYS sessions)
    out["momentum_1m"] = (
        calculate_rs_trend(sector_series, nifty_series, as_of,
                           HORIZON_TRADING_DAYS["1m"], MOMENTUM_LOOKBACK_DAYS)
        if rs_values["1m"] is not None else None)

    # Inflection helpers: RS_3M / RS_6M as they stood N sessions ago (used by
    # the classifier for "was it different recently" checks — Weakening / Early Momentum).
    for horizon in ("3m", "6m"):
        val = None
        if pos is not None and pos - INFLECTION_LOOKBACK_DAYS >= 0:
            earlier_date = sector_series.index[pos - INFLECTION_LOOKBACK_DAYS]
            _, _, rs_earlier = rs_as_of(sector_series, nifty_series, earlier_date,
                                        HORIZON_TRADING_DAYS[horizon])
            val = rs_earlier
        out[f"rs_{horizon}_{INFLECTION_LOOKBACK_DAYS}d_ago"] = val

    # Improving slope: rs_1m(t) - rs_1m(t - IMPROVING_SLOPE_LOOKBACK_DAYS)
    out["rs_1m_slope"] = (
        calculate_rs_trend(sector_series, nifty_series, as_of,
                           HORIZON_TRADING_DAYS["1m"], IMPROVING_SLOPE_LOOKBACK_DAYS)
        if rs_values["1m"] is not None else None)

    for window in SMA_WINDOWS:
        out[f"above_{window}_sma"] = above_sma(sector_series, as_of, window)

    if pos is not None:
        out["close"] = float(sector_series.iloc[pos])
    else:
        out["close"] = None

    return out
