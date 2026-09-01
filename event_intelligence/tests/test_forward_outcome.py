"""
Incremental forward-outcome tests — Phase 4.

Controlled synthetic series (deterministic) verifying the look-ahead
boundary is respected: the outcome is measured strictly from `from_session`
to `to_session`, never touching data before `from_session` or beyond
`to_session`, and never touching the pre-event baseline at all.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from event_intelligence.forward_outcome import compute_incremental_forward_return


def _trading_days(n: int, start: dt.date = dt.date(2026, 1, 5)) -> list[dt.date]:
    days = []
    d = start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += dt.timedelta(days=1)
    return days


def _df(dates, closes) -> pd.DataFrame:
    return pd.DataFrame({"close": closes}, index=pd.Index(dates, name="trade_date"))


class TestIncrementalArithmetic:
    def test_return_measured_strictly_between_the_two_endpoints(self):
        dates = _trading_days(40)
        closes = [100.0] * 40
        closes[15] = 200.0  # a huge move sitting BETWEEN session +5 and +10 (anchor=10)
        # anchor at index 10: from_session=5 -> position 15; to_session=10 -> position 20
        df = _df(dates, closes)
        bench = pd.Series([20000.0] * 40, index=dates)

        result = compute_incremental_forward_return(df, bench, dates[10], 5, 10)
        # from_close = closes[15] = 200 ; to_close = closes[20] = 100 (reverted)
        assert result["forward_return"] == pytest.approx(-50.0, abs=0.01)

    def test_pre_event_baseline_never_touched(self):
        """A dramatic move BEFORE the from_session position must have zero
        effect on the computed forward return — only [from, to] matters."""
        dates = _trading_days(40)
        closes = [100.0] * 40
        closes[0] = 999999.0  # wild pre-event value, must be irrelevant
        closes[15] = 100.0
        closes[20] = 110.0
        df = _df(dates, closes)
        bench = pd.Series([20000.0] * 40, index=dates)
        result = compute_incremental_forward_return(df, bench, dates[10], 5, 10)
        assert result["forward_return"] == pytest.approx(10.0, abs=0.01)

    def test_benchmark_relative_forward_return(self):
        dates = _trading_days(40)
        # position 15 (from_session) is still 100/20000; position 20
        # (to_session) has moved to 110/20200 — the jump sits strictly
        # between the two measured endpoints.
        closes = [100.0] * 20 + [110.0] * 20
        bench_vals = [20000.0] * 20 + [20200.0] * 20
        df = _df(dates, closes)
        bench = pd.Series(bench_vals, index=dates)
        result = compute_incremental_forward_return(df, bench, dates[10], 5, 10)
        assert result["forward_return"] == pytest.approx(10.0, abs=0.01)
        assert result["benchmark_forward_return"] == pytest.approx(1.0, abs=0.01)
        assert result["relative_forward_return"] == pytest.approx(9.0, abs=0.01)


class TestMissingData:
    def test_empty_price_frame_returns_none(self):
        result = compute_incremental_forward_return(pd.DataFrame(), pd.Series(dtype=float),
                                                     dt.date(2026, 1, 1), 5, 10)
        assert result["forward_return"] is None

    def test_to_session_beyond_available_data_returns_none(self):
        dates = _trading_days(18)  # only 7 sessions after anchor position 10
        closes = [100.0] * 18
        df = _df(dates, closes)
        bench = pd.Series([20000.0] * 18, index=dates)
        result = compute_incremental_forward_return(df, bench, dates[10], 5, 10)
        assert result["forward_return"] is None  # position 20 doesn't exist (only 18 rows)

    def test_from_session_beyond_available_data_returns_none(self):
        dates = _trading_days(14)
        closes = [100.0] * 14
        df = _df(dates, closes)
        bench = pd.Series([20000.0] * 14, index=dates)
        result = compute_incremental_forward_return(df, bench, dates[10], 5, 10)
        assert result["forward_return"] is None  # position 15 doesn't exist

    def test_event_not_found_in_index_returns_none(self):
        dates = _trading_days(30)
        closes = [100.0] * 30
        df = _df(dates, closes)
        bench = pd.Series([20000.0] * 30, index=dates)
        result = compute_incremental_forward_return(df, bench,
                                                     dates[-1] + dt.timedelta(days=100), 5, 10)
        assert result["forward_return"] is None
