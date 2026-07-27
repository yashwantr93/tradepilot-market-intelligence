"""
Pure multi-horizon metric calculations — no database access, so these are
directly unit-testable against synthetic series (see tests/test_phase1_*).

All formulas are exactly as specified in
docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §1.4.
"""

from __future__ import annotations

import bisect
import datetime as dt

import pandas as pd

from intelligence_v2.config.sectors import (
    HORIZON_TRADING_DAYS,
    IMPROVING_SLOPE_LOOKBACK_DAYS,
    INFLECTION_LOOKBACK_DAYS,
    MOMENTUM_LOOKBACK_DAYS,
    SMA_WINDOWS,
)


def _position_at_or_before(series: pd.Series, as_of: dt.date) -> int | None:
    """Index position of the latest date in `series` that is <= as_of."""
    if series.empty:
        return None
    dates = list(series.index)
    pos = bisect.bisect_right(dates, as_of) - 1
    return pos if pos >= 0 else None


def perf_over(series: pd.Series, as_of: dt.date, trading_days: int) -> float | None:
    """% change from `trading_days` sessions before `as_of` to `as_of`."""
    pos = _position_at_or_before(series, as_of)
    if pos is None or pos - trading_days < 0:
        return None
    curr = series.iloc[pos]
    prior = series.iloc[pos - trading_days]
    if prior in (0, None) or pd.isna(prior) or pd.isna(curr):
        return None
    return round((curr / prior - 1) * 100, 4)


def rs_over(sector_series: pd.Series, nifty_series: pd.Series, as_of: dt.date,
           trading_days: int) -> tuple[float | None, float | None, float | None]:
    """Returns (sector_perf, nifty_perf, relative_strength) for one horizon."""
    sp = perf_over(sector_series, as_of, trading_days)
    np_ = perf_over(nifty_series, as_of, trading_days)
    rs = round(sp - np_, 4) if (sp is not None and np_ is not None) else None
    return sp, np_, rs


def above_sma(series: pd.Series, as_of: dt.date, window: int) -> str | None:
    """Y/N — None if there isn't `window` days of history yet."""
    pos = _position_at_or_before(series, as_of)
    if pos is None or pos - window + 1 < 0:
        return None
    sma = series.iloc[pos - window + 1: pos + 1].mean()
    if pd.isna(sma):
        return None
    return "Y" if series.iloc[pos] > sma else "N"


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

    # momentum_1m = rs_1m(t) - rs_1m(t - MOMENTUM_LOOKBACK_DAYS sessions)
    pos = _position_at_or_before(sector_series, as_of)
    momentum_1m = None
    if pos is not None and pos - MOMENTUM_LOOKBACK_DAYS >= 0:
        earlier_date = sector_series.index[pos - MOMENTUM_LOOKBACK_DAYS]
        _, _, rs_1m_earlier = rs_over(sector_series, nifty_series, earlier_date,
                                      HORIZON_TRADING_DAYS["1m"])
        if rs_1m_earlier is not None and rs_values["1m"] is not None:
            momentum_1m = round(rs_values["1m"] - rs_1m_earlier, 4)
    out["momentum_1m"] = momentum_1m

    # Inflection helpers: RS_3M / RS_6M as they stood N sessions ago (used by
    # the classifier for "was it different recently" checks — Weakening / Early Momentum).
    for horizon in ("3m", "6m"):
        val = None
        if pos is not None and pos - INFLECTION_LOOKBACK_DAYS >= 0:
            earlier_date = sector_series.index[pos - INFLECTION_LOOKBACK_DAYS]
            _, _, rs_earlier = rs_over(sector_series, nifty_series, earlier_date,
                                       HORIZON_TRADING_DAYS[horizon])
            val = rs_earlier
        out[f"rs_{horizon}_{INFLECTION_LOOKBACK_DAYS}d_ago"] = val

    # Improving slope: rs_1m(t) - rs_1m(t - IMPROVING_SLOPE_LOOKBACK_DAYS)
    slope = None
    if pos is not None and pos - IMPROVING_SLOPE_LOOKBACK_DAYS >= 0:
        earlier_date = sector_series.index[pos - IMPROVING_SLOPE_LOOKBACK_DAYS]
        _, _, rs_1m_earlier2 = rs_over(sector_series, nifty_series, earlier_date,
                                       HORIZON_TRADING_DAYS["1m"])
        if rs_1m_earlier2 is not None and rs_values["1m"] is not None:
            slope = round(rs_values["1m"] - rs_1m_earlier2, 4)
    out["rs_1m_slope"] = slope

    for window in SMA_WINDOWS:
        out[f"above_{window}_sma"] = above_sma(sector_series, as_of, window)

    if pos is not None:
        out["close"] = float(sector_series.iloc[pos])
    else:
        out["close"] = None

    return out
