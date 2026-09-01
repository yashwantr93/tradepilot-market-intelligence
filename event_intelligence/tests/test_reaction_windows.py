"""
Event-relative reaction window tests — Phase 3.

Controlled, synthetic price series (deterministic, hand-verifiable) — the
mechanism's correctness against REAL stored data is separately verified via
the Phase 3 report's REAL-DATA VALIDATION section (76 real events, spot-
checked). These tests isolate trading-session-aware edge cases: weekend/
holiday events, missing data, and the exact windows/MFE/MAE arithmetic.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from event_intelligence.reaction_windows import compute_event_reaction


def _trading_days(n: int, start: dt.date = dt.date(2026, 1, 5)) -> list[dt.date]:
    """n consecutive weekday sessions starting on a Monday — no gaps, so
    tests can reason about exact positions."""
    days = []
    d = start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += dt.timedelta(days=1)
    return days


def _price_df(dates, closes, opens=None, highs=None, lows=None, volumes=None) -> pd.DataFrame:
    n = len(dates)
    return pd.DataFrame({
        "open": opens or closes, "high": highs or closes, "low": lows or closes,
        "close": closes, "volume": volumes or [1_000_000] * n,
    }, index=pd.Index(dates, name="trade_date"))


def _flat_benchmark(dates, value=20000.0) -> pd.Series:
    return pd.Series([value] * len(dates), index=dates)


class TestSessionResolution:
    def test_event_on_trading_day_anchors_to_that_day(self):
        dates = _trading_days(30)
        closes = [100.0 + i for i in range(30)]
        df = _price_df(dates, closes)
        bench = _flat_benchmark(dates)

        result = compute_event_reaction(df, bench, dates[10])
        assert result["anchor_date"] == dates[10]
        assert result["pre_event_close_date"] == dates[9]

    def test_event_on_weekend_resolves_forward_to_monday(self):
        dates = _trading_days(30)  # Mon-Fri only
        closes = [100.0 + i for i in range(30)]
        df = _price_df(dates, closes)
        bench = _flat_benchmark(dates)

        friday = dates[9]
        saturday = friday + dt.timedelta(days=1)
        monday = dates[10]
        assert monday.weekday() == 0

        result = compute_event_reaction(df, bench, saturday)
        assert result["anchor_date"] == monday
        assert result["pre_event_close_date"] == friday  # NOT the weekend itself

    def test_event_on_market_holiday_resolves_to_next_session(self):
        """A holiday is just a missing row — no different from a weekend in
        this data model (price_history only has actual trading sessions)."""
        dates = _trading_days(10)
        holiday_gap_dates = [d for i, d in enumerate(dates) if i != 5]  # remove one session
        closes = [100.0 + i for i in range(len(holiday_gap_dates))]
        df = _price_df(holiday_gap_dates, closes)
        bench = _flat_benchmark(holiday_gap_dates)

        missing_day = dates[5]
        result = compute_event_reaction(df, bench, missing_day)
        assert result["anchor_date"] == dates[6]  # first real session after the gap

    def test_after_hours_ambiguity_is_a_documented_limitation_not_a_crash(self):
        """No time-of-day exists in the data — an announcement dated the
        same day as an existing session simply anchors to that session,
        whether it was actually pre-market or after-hours. Verifies this
        doesn't crash or silently misbehave; the ambiguity itself is
        accepted and documented, not resolved."""
        dates = _trading_days(10)
        closes = [100.0 + i for i in range(10)]
        df = _price_df(dates, closes)
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[3])
        assert result["anchor_date"] == dates[3]
        assert result["insufficient_reason"] is None


class TestMissingData:
    def test_empty_price_history_is_insufficient(self):
        result = compute_event_reaction(pd.DataFrame(), pd.Series(dtype=float), dt.date(2026, 1, 1))
        assert result["insufficient_reason"] is not None
        assert result["return_5d"] is None

    def test_event_beyond_end_of_price_history_is_insufficient(self):
        dates = _trading_days(10)
        closes = [100.0] * 10
        df = _price_df(dates, closes)
        bench = _flat_benchmark(dates)
        far_future = dates[-1] + dt.timedelta(days=365)
        result = compute_event_reaction(df, bench, far_future)
        assert result["insufficient_reason"] is not None

    def test_event_before_any_price_history_has_no_baseline(self):
        dates = _trading_days(10)
        closes = [100.0] * 10
        df = _price_df(dates, closes)
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[0] - dt.timedelta(days=100))
        assert result["insufficient_reason"] is not None

    def test_missing_volume_column_leaves_volume_ratio_none_not_a_crash(self):
        dates = _trading_days(30)
        closes = [100.0 + i for i in range(30)]
        df = _price_df(dates, closes).drop(columns=["volume"])
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[25])
        assert result["volume_ratio_day0"] is None
        assert result["return_1d"] is not None  # everything else still computes

    def test_all_output_keys_present_even_when_fully_insufficient(self):
        """UNKNOWN must propagate as an explicit, complete set of None
        values — never a partial/missing dict."""
        result = compute_event_reaction(pd.DataFrame(), pd.Series(dtype=float), dt.date(2026, 1, 1))
        for w in (1, 5, 10, 20):
            assert f"return_{w}d" in result
            assert f"benchmark_return_{w}d" in result
            assert f"relative_return_{w}d" in result
        assert "mfe_pct" in result and "mae_pct" in result


class TestWindowedReturns:
    def test_day0_return_and_forward_returns_are_distinct(self):
        dates = _trading_days(30)
        # pre-event close = 100 (index 9). Event day (index 10) closes 110.
        # Index 11 (+1 session) closes 115.
        closes = [100.0] * 10 + [110.0, 115.0] + [115.0] * 18
        df = _price_df(dates, closes)
        bench = _flat_benchmark(dates)  # flat benchmark -> relative == absolute

        result = compute_event_reaction(df, bench, dates[10])
        assert result["return_0d"] == pytest.approx(10.0, abs=0.01)   # 100 -> 110, event day itself
        assert result["return_1d"] == pytest.approx(15.0, abs=0.01)   # 100 -> 115, one session later
        assert result["relative_return_0d"] == pytest.approx(10.0, abs=0.01)  # bench flat

    def test_benchmark_moving_changes_relative_not_absolute_return(self):
        dates = _trading_days(30)
        closes = [100.0] * 10 + [105.0] * 20  # stock +5% at event, held flat after
        bench_vals = [20000.0] * 10 + [20200.0] * 20  # benchmark +1% too
        df = _price_df(dates, closes)
        bench = pd.Series(bench_vals, index=dates)

        result = compute_event_reaction(df, bench, dates[10])
        assert result["return_0d"] == pytest.approx(5.0, abs=0.01)
        assert result["benchmark_return_0d"] == pytest.approx(1.0, abs=0.01)
        assert result["relative_return_0d"] == pytest.approx(4.0, abs=0.01)

    def test_window_unavailable_beyond_end_of_data_is_none_not_extrapolated(self):
        dates = _trading_days(13)  # only 2 sessions exist after event position 10
        closes = [100.0] * 13
        df = _price_df(dates, closes)
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[10])
        assert result["return_0d"] is not None
        assert result["return_1d"] is not None   # position 11 exists
        assert result["return_5d"] is None       # would need position 15, out of range
        assert result["return_20d"] is None
        assert result["max_window_available"] == 1  # furthest window actually reached

    def test_only_event_day_available_reports_max_window_zero_not_none(self):
        """A brand-new event with zero forward sessions yet must report
        max_window_available=0 (a real, meaningful state), never None
        (which means 'nothing at all is measurable')."""
        dates = _trading_days(11)  # event IS the very last stored session
        closes = [100.0] * 11
        df = _price_df(dates, closes)
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[10])
        assert result["return_0d"] is not None
        assert result["return_1d"] is None
        assert result["max_window_available"] == 0

    def test_gap_pct_uses_open_not_close(self):
        dates = _trading_days(15)
        closes = [100.0] * 10 + [102.0] * 5
        opens = [100.0] * 10 + [108.0] + [102.0] * 4  # a big gap-up open on event day
        df = _price_df(dates, closes, opens=opens)
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[10])
        assert result["gap_pct"] == pytest.approx(8.0, abs=0.01)      # 100 -> 108 open
        assert result["return_0d"] == pytest.approx(2.0, abs=0.01)    # 100 -> 102 close, same day


class TestVolumeRatio:
    def test_volume_expansion_detected(self):
        # Need >= 20 prior sessions for the trailing volume average, so the
        # event sits at position 25 (25 prior sessions available).
        dates = _trading_days(45)
        closes = [100.0] * 45
        volumes = [1_000_000] * 25 + [5_000_000] + [1_000_000] * 19
        df = _price_df(dates, closes, volumes=volumes)
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[25])
        assert result["volume_ratio_day0"] == pytest.approx(5.0, abs=0.01)

    def test_insufficient_prior_volume_history_is_none(self):
        dates = _trading_days(15)
        closes = [100.0] * 15
        df = _price_df(dates, closes)
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[3])  # only 3 prior sessions, need 20
        assert result["volume_ratio_day0"] is None


class TestExcursion:
    def test_mfe_and_mae_use_high_low_over_available_window(self):
        # anchor_pos=10, 30 total sessions -> max_window_available=10
        # (window 20 would need position 30, out of range) -> excursion
        # window is positions [10, 20] inclusive. Spikes placed inside it.
        dates = _trading_days(30)
        closes = [100.0] * 30
        highs = [100.0] * 12 + [115.0] + [100.0] * 17    # spike at position 12
        lows = [100.0] * 17 + [90.0] + [100.0] * 12      # spike at position 17
        df = _price_df(dates, closes, highs=highs, lows=lows)
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[10])
        assert result["max_window_available"] == 10
        assert result["mfe_pct"] == pytest.approx(15.0, abs=0.01)   # 100 -> 115 high
        assert result["mae_pct"] == pytest.approx(-10.0, abs=0.01)  # 100 -> 90 low

    def test_excursion_outside_the_available_window_is_excluded(self):
        """A spike beyond max_window_available must NOT be picked up —
        excursion is scoped to what was actually measured, not the whole
        series."""
        dates = _trading_days(30)
        closes = [100.0] * 30
        highs = [100.0] * 25 + [500.0] + [100.0] * 4  # spike at position 25 — beyond window
        df = _price_df(dates, closes, highs=highs)
        bench = _flat_benchmark(dates)
        result = compute_event_reaction(df, bench, dates[10])
        assert result["max_window_available"] == 10  # window caps at position 20
        assert result["mfe_pct"] < 5.0  # the position-25 spike must not leak in
