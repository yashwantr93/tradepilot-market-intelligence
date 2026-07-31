"""
Shared Relative Strength Engine — the ONE implementation every V2 module uses.

Created as a mandatory defect fix, not a new feature. Phase 3 (Early Momentum)
independently discovered and fixed two real defects that Phase 1 (Sector
Intelligence) — and therefore Phase 2 (Market Cycle), which only consumes
Phase 1's stored output — still had:

  1. CORRUPTED BENCHMARK PRICES. V1's stored `price_history` contains isolated
     bad closes (e.g. NIFTY 50 printing 16,848 between two ~24,000 closes —
     an impossible single-day round trip). Left unfiltered, these silently
     wreck any relative-strength window that includes one.

  2. DATE-ALIGNMENT MISMATCH. Comparing a stock/sector series against the
     benchmark by POSITION offset ("21 rows back") is wrong whenever the two
     series have different date coverage — which they do whenever a basket is
     thin or a symbol has gaps. "21 rows back" then resolves to a different
     CALENDAR date in each series, comparing performance over different
     windows and calling the difference "relative strength."

This module is the single, tested place both defects are fixed. No phase may
compute relative strength independently — see the "REFACTORED" note at the
top of sector_metrics.py, sector_prices.py, and momentum_metrics.py.

Design note: sanitisation and alignment are NOT new indicators. They are data
hygiene and correct measurement of the SAME quantities every phase already
used (close price, % change, relative strength). No new signal, no new
threshold-based business rule lives here — those stay in each phase's own
classifier, unchanged.
"""

from __future__ import annotations

import bisect
import datetime as dt

import pandas as pd

# ---------------------------------------------------------------------------
# Sanitisation — the exact algorithm validated during Phase 3, unchanged.
# ---------------------------------------------------------------------------
DEFAULT_MAX_DAILY_MOVE_PCT = 25.0   # NSE circuit bands top out at 20%; a larger
                                    # single-session move is corrupt by
                                    # definition, not a judgement call.
DEFAULT_SANITIZE_WINDOW = 21        # ~1 month — sized for the per-stock universe.
                                    # NOTE: does not reliably survive a DENSE
                                    # cluster of 3+ bad prints within ~1-3
                                    # weeks of each other (see
                                    # BENCHMARK_SANITIZE_WINDOW below) — each
                                    # bad print can then sit inside its
                                    # neighbour's own centred window and
                                    # mutually mask the deviation check.
DEFAULT_SANITIZE_MIN_PERIODS = 5

# Phase 6 audit (Launch Validation) found V1's stored NIFTY 50 history contains
# a denser corruption cluster than DEFAULT_SANITIZE_WINDOW was validated
# against: four bad prints inside a 6-week span (2026-03-03/26/31, 04-03), of
# which the default 21-session window only ever caught one. A wider window is
# safe for the BENCHMARK specifically — it is one large, liquid index, not a
# smaller/more volatile individual stock — but was deliberately NOT applied to
# the wider per-stock universe: empirically it raised the universe-wide drop
# count from 178 to 472 rows (40 to 81 symbols), a blast radius too broad to
# validate for every individual stock's legitimate volatility within this fix.
# 51 sessions is the smallest window that plateaus (61/71-session windows
# catch the identical set), so it is not a fragile, arbitrarily-tuned value.
BENCHMARK_SANITIZE_WINDOW = 51


def sanitize_close_series(closes: pd.Series,
                          max_daily_move_pct: float = DEFAULT_MAX_DAILY_MOVE_PCT,
                          window: int = DEFAULT_SANITIZE_WINDOW,
                          min_periods: int = DEFAULT_SANITIZE_MIN_PERIODS,
                          ) -> tuple[pd.Series, int]:
    """Drop isolated corrupt closes from a price series.

    Reference level is a CENTRED ROLLING MEDIAN (immune to the spikes being
    removed — unlike a running "last valid value" anchor, which sticks after a
    drop and then wrongly rejects the legitimate values that follow it). Any
    close deviating from that reference by more than `max_daily_move_pct` is
    dropped.

    Deterministic and order-stable. Returns (clean_series, rows_dropped).
    Never modifies the caller's data source — operates on an in-memory copy.
    """
    if closes.empty:
        return closes, 0

    reference = closes.rolling(window=window, center=True, min_periods=min_periods).median()
    deviation_pct = (closes / reference - 1).abs() * 100

    keep = ~((deviation_pct > max_daily_move_pct) | closes.isna() | (closes <= 0))
    keep = keep.fillna(False)
    dropped = int((~keep).sum())
    return closes[keep], dropped


def sanitize_price_frame(frame: pd.DataFrame, close_col: str = "close",
                         **sanitize_kwargs) -> tuple[pd.DataFrame, int]:
    """Sanitise a DataFrame (e.g. close+volume) by its close column, dropping
    the same rows from every other column so nothing gets misaligned."""
    if frame.empty:
        return frame, 0
    clean_closes, dropped = sanitize_close_series(frame[close_col], **sanitize_kwargs)
    return frame.loc[clean_closes.index], dropped


def sanitize_benchmark_series(closes: pd.Series) -> tuple[pd.Series, int]:
    """Sanitise the benchmark series specifically, using the wider
    BENCHMARK_SANITIZE_WINDOW (see its docstring for why this is safe only
    for the benchmark and not applied universe-wide). Same threshold and
    algorithm as `sanitize_close_series` — only the window differs. Callers
    fetching the benchmark (sector_prices.py, momentum_metrics.py) should use
    this instead of `sanitize_close_series` directly, so the wider window
    stays defined in exactly one place.
    """
    return sanitize_close_series(closes, window=BENCHMARK_SANITIZE_WINDOW)


# ---------------------------------------------------------------------------
# Position / calendar-date lookup primitives
# ---------------------------------------------------------------------------
def position_at_or_before(index, as_of: dt.date) -> int | None:
    """Integer position of the latest entry in `index` that is <= as_of.

    Shared by every lookback calculation — was previously duplicated near-
    verbatim in sector_metrics.py (`_position_at_or_before`) and
    momentum_metrics.py (`_pos_at_or_before`).
    """
    dates = list(index)
    if not dates:
        return None
    pos = bisect.bisect_right(dates, as_of) - 1
    return pos if pos >= 0 else None


def performance_over(series: pd.Series, pos: int, lookback_days: int) -> float | None:
    """% change from `lookback_days` POSITIONS before `pos` to `pos`, within
    ONE series. Safe to use standalone only when both ends are measured on the
    same series — for cross-series (relative strength) comparisons use
    `performance_between_dates` / `rs_as_of` instead, which are calendar-
    aligned rather than position-aligned."""
    if pos is None or pos - lookback_days < 0:
        return None
    curr, prior = series.iloc[pos], series.iloc[pos - lookback_days]
    if pd.isna(curr) or pd.isna(prior) or prior == 0:
        return None
    return round((curr / prior - 1) * 100, 4)


def performance_between_dates(series: pd.Series, start: dt.date, end: dt.date) -> float | None:
    """% change of `series` between two CALENDAR dates (at-or-before lookup
    on each end independently).

    THE alignment primitive: used to measure the benchmark over exactly the
    same calendar window as the stock/sector being compared, regardless of
    how many rows either series actually has. This is what fixes defect #2 —
    every relative-strength calculation in this module goes through here for
    its benchmark leg, never through `performance_over` on the benchmark
    series measured by position.
    """
    start_pos = position_at_or_before(series.index, start)
    end_pos = position_at_or_before(series.index, end)
    if start_pos is None or end_pos is None or start_pos >= end_pos:
        return None
    prior, curr = series.iloc[start_pos], series.iloc[end_pos]
    if pd.isna(curr) or pd.isna(prior) or prior == 0:
        return None
    return round((curr / prior - 1) * 100, 4)


# ---------------------------------------------------------------------------
# Relative strength
# ---------------------------------------------------------------------------
def rs_as_of(series: pd.Series, benchmark: pd.Series, as_of: dt.date,
            lookback_days: int) -> tuple[float | None, float | None, float | None]:
    """Relative strength for ONE horizon, evaluated as of ANY date.

    Returns (series_perf, benchmark_perf, relative_strength). The benchmark
    leg is always measured over the series' own calendar window via
    `performance_between_dates` — never by a naive position offset on the
    benchmark's own (possibly differently-shaped) index. `as_of` need not be
    "today" — passing an earlier date is how `calculate_rs_trend` below
    evaluates RS as it stood in the past.
    """
    pos = position_at_or_before(series.index, as_of)
    series_perf = performance_over(series, pos, lookback_days) if pos is not None else None

    benchmark_perf = None
    if series_perf is not None and not benchmark.empty and pos is not None:
        window_start = series.index[pos - lookback_days]
        benchmark_perf = performance_between_dates(benchmark, window_start, as_of)

    rs = (round(series_perf - benchmark_perf, 4)
         if (series_perf is not None and benchmark_perf is not None) else None)
    return series_perf, benchmark_perf, rs


def build_relative_strength_set(series: pd.Series, benchmark: pd.Series, as_of: dt.date,
                                horizons: dict[str, int]) -> dict:
    """Relative strength across MULTIPLE horizons at once, e.g.
    {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "1y": 252}.

    Returns a flat dict with three keys per horizon label:
        perf_<label>, benchmark_perf_<label>, rs_<label>
    Replaces the near-identical per-horizon loop that previously lived in both
    Phase 1's `compute_metrics` and Phase 3's `compute_stock_metrics`.
    """
    out: dict[str, float | None] = {}
    for label, lookback_days in horizons.items():
        series_perf, benchmark_perf, rs = rs_as_of(series, benchmark, as_of, lookback_days)
        out[f"perf_{label}"] = series_perf
        out[f"benchmark_perf_{label}"] = benchmark_perf
        out[f"rs_{label}"] = rs
    return out


def calculate_rs_trend(series: pd.Series, benchmark: pd.Series, as_of: dt.date,
                       lookback_days: int, trend_lookback_days: int) -> float | None:
    """Change in relative strength over `trend_lookback_days` sessions —
    "is RS improving?" Positive means RS measured today is higher than RS
    measured `trend_lookback_days` sessions ago, for the same `lookback_days`
    horizon (e.g. 1-month RS today vs 1-month RS twenty sessions ago).

    Replaces Phase 1's `momentum_1m` / `rs_1m_slope` (two call sites, same
    logic, different lookback constants) and Phase 3's `rs_slope` — one
    function, each phase supplies its own `trend_lookback_days`.
    """
    pos = position_at_or_before(series.index, as_of)
    if pos is None or pos - trend_lookback_days < 0:
        return None
    earlier_as_of = series.index[pos - trend_lookback_days]

    _, _, rs_now = rs_as_of(series, benchmark, as_of, lookback_days)
    _, _, rs_earlier = rs_as_of(series, benchmark, earlier_as_of, lookback_days)
    if rs_now is None or rs_earlier is None:
        return None
    return round(rs_now - rs_earlier, 4)


def is_outperforming(rs_value: float | None, threshold: float = 0.0) -> bool | None:
    """Relative outperformance: is `rs_value` above `threshold`?

    Returns None (not False) when `rs_value` is unavailable, so callers can
    distinguish "measured and not outperforming" from "not measurable" if
    they need to — most callers coerce this to a plain bool for a signal
    check, which is a business-rule decision left to each phase's classifier.
    """
    if rs_value is None:
        return None
    return rs_value > threshold


# ---------------------------------------------------------------------------
# Shared helper: moving-average position (not RS-specific, but identical
# duplicated logic existed in both sector_metrics.above_sma and Phase 3's
# inline SMA loop — consolidated here as a general-purpose helper).
# ---------------------------------------------------------------------------
def above_moving_average(series: pd.Series, as_of: dt.date, window: int) -> str | None:
    """"Y" / "N" / None (insufficient history) — is `series` above its own
    trailing `window`-session simple moving average as of `as_of`?"""
    pos = position_at_or_before(series.index, as_of)
    if pos is None or pos - window + 1 < 0:
        return None
    sma = series.iloc[pos - window + 1: pos + 1].mean()
    if pd.isna(sma):
        return None
    return "Y" if series.iloc[pos] > sma else "N"
