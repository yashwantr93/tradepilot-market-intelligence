"""
Stock-level metric calculations for the Early Momentum Engine.

Reads price + volume series from V1's `price_history` through the read-only
bridge (no new connector, no new indicator — the same measures already used
elsewhere in the project, applied per stock).

`compute_stock_metrics()` is PURE (takes series, returns a dict) so it is
directly unit-testable against synthetic inputs.

REFACTORED (shared Relative Strength Engine): sanitisation, calendar-aligned
performance/RS, RS trend, and moving-average helpers now delegate to
`intelligence_v2.processors.shared_relative_strength` — the one place these
are implemented, per the mandatory defect-fix refactor. This module's own
algorithm was the one Phase 3 already validated and fixed, so the shared
module's implementation is a direct extraction of it (behaviour unchanged);
Phase 1/2 were the modules with the actual defects being fixed by adopting it.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from intelligence_v2.config.early_momentum import (
    BENCHMARK_SYMBOL,
    HIGH_52W_LOOKBACK,
    HORIZON_DAYS,
    MAX_DAILY_MOVE_PCT,
    RS_SLOPE_LOOKBACK,
    SMA_WINDOWS,
    VOL_BASE_DAYS,
    VOL_RECENT_DAYS,
)
from intelligence_v2.database.v1_reference import read_v1
from intelligence_v2.processors.shared_relative_strength import (
    BENCHMARK_SANITIZE_WINDOW,
    above_moving_average,
    calculate_rs_trend,
    position_at_or_before,
    rs_as_of,
    sanitize_price_frame,
)
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("processors.momentum_metrics")


def sanitize_closes(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop isolated corrupt closes from V1's stored price history.

    Thin wrapper over the shared sanitiser (centred rolling-median reference,
    `MAX_DAILY_MOVE_PCT` deviation threshold) so `volume` stays aligned to
    whichever `close` rows survive. V1's stored data is never modified — this
    filters V2's in-memory copy only.
    """
    return sanitize_price_frame(frame, close_col="close", max_daily_move_pct=MAX_DAILY_MOVE_PCT)


def load_universe_series() -> tuple[dict[str, pd.DataFrame], pd.Series]:
    """Load every symbol's OHLCV once (bulk read), plus the benchmark closes.

    Returns ({symbol: DataFrame[close, volume] indexed by date}, nifty_closes).
    """
    df = read_v1("SELECT symbol, trade_date, close, volume FROM price_history "
                "ORDER BY symbol, trade_date")
    if df.empty:
        return {}, pd.Series(dtype=float)

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    series: dict[str, pd.DataFrame] = {}
    total_dropped = 0
    affected = 0
    for symbol, g in df.groupby("symbol"):
        sub = g.set_index("trade_date")[["close", "volume"]].sort_index()
        # The benchmark gets the wider, benchmark-specific window (see
        # shared_relative_strength.BENCHMARK_SANITIZE_WINDOW) — every other
        # symbol keeps the untouched default, preserving existing behaviour
        # for the rest of the universe.
        if symbol == BENCHMARK_SYMBOL:
            sub, dropped = sanitize_price_frame(
                sub, close_col="close", max_daily_move_pct=MAX_DAILY_MOVE_PCT,
                window=BENCHMARK_SANITIZE_WINDOW)
        else:
            sub, dropped = sanitize_closes(sub)
        if dropped:
            total_dropped += dropped
            affected += 1
        series[symbol] = sub

    benchmark = series.pop(BENCHMARK_SYMBOL, pd.DataFrame())
    nifty_closes = benchmark["close"] if not benchmark.empty else pd.Series(dtype=float)
    log.info("Loaded %d symbols from V1 price_history (benchmark %s: %d rows)",
             len(series), BENCHMARK_SYMBOL, len(nifty_closes))
    if total_dropped:
        log.warning("Data hygiene: dropped %d corrupt close(s) across %d symbol(s) "
                   "(single-day moves > %.0f%%). V1's stored data is unchanged.",
                   total_dropped, affected, MAX_DAILY_MOVE_PCT)
    return series, nifty_closes


def compute_stock_metrics(closes: pd.Series, volumes: pd.Series,
                          nifty_closes: pd.Series, as_of: dt.date) -> dict | None:
    """All Early Momentum metrics for one stock on one date.

    Returns None when the stock has no data at/before `as_of`. Individual
    fields are None when their specific window is unavailable — never guessed.
    """
    pos = position_at_or_before(closes.index, as_of)
    if pos is None:
        return None

    out: dict = {"close": round(float(closes.iloc[pos]), 4)}

    # Performance + relative strength per horizon, via the shared engine's
    # calendar-aligned rs_as_of — the benchmark is measured over the SAME
    # CALENDAR WINDOW as the stock, not the same number of index positions.
    # Series here have differing lengths (missing sessions, sanitised rows),
    # so "21 positions back" resolves to a different date in each series —
    # comparing them directly silently produced nonsense relative strength.
    rs_values: dict[str, float | None] = {}
    for horizon, days in HORIZON_DAYS.items():
        sp, _np, rs = rs_as_of(closes, nifty_closes, as_of, days)
        out[f"perf_{horizon}"] = sp
        out[f"rs_{horizon}"] = rs
        rs_values[horizon] = rs

    # RS slope: rs_1m(t) - rs_1m(t - RS_SLOPE_LOOKBACK)  ->  "RS improving".
    out["rs_slope"] = (
        calculate_rs_trend(closes, nifty_closes, as_of, HORIZON_DAYS["1m"], RS_SLOPE_LOOKBACK)
        if rs_values["1m"] is not None and not nifty_closes.empty else None)

    # Moving-average position
    for window in SMA_WINDOWS:
        out[f"above_{window}_sma"] = above_moving_average(closes, as_of, window)

    # Volume expansion ratio (volume already stored in V1 price_history)
    volume_ratio = None
    if pos - (VOL_RECENT_DAYS + VOL_BASE_DAYS) + 1 >= 0:
        recent = volumes.iloc[pos - VOL_RECENT_DAYS + 1: pos + 1].mean()
        base = volumes.iloc[pos - VOL_RECENT_DAYS - VOL_BASE_DAYS + 1: pos - VOL_RECENT_DAYS + 1].mean()
        if pd.notna(recent) and pd.notna(base) and base > 0:
            volume_ratio = round(float(recent / base), 4)
    out["volume_ratio"] = volume_ratio

    # Distance from 52-week high (context only — not a classification gate)
    hi_lb = min(HIGH_52W_LOOKBACK, pos + 1)
    high_52w = float(closes.iloc[pos - hi_lb + 1: pos + 1].max())
    out["dist_52w_high_pct"] = (
        round((high_52w - closes.iloc[pos]) / high_52w * 100, 2) if high_52w else None)

    return out
