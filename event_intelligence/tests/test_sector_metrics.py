"""Sector metrics tests — Phase 6. Synthetic, controlled price series."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from event_intelligence.sector_metrics import aggregate_sector_metrics, compute_constituent_metrics


def _trading_days(n: int, start: dt.date = dt.date(2026, 1, 5)) -> list[dt.date]:
    days, d = [], start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += dt.timedelta(days=1)
    return days


def _series(dates, values) -> pd.Series:
    return pd.Series(values, index=pd.Index(dates, name="trade_date"))


class TestConstituentMetrics:
    def test_missing_symbol_returns_none(self):
        result = compute_constituent_metrics(pd.Series(dtype=float), None, pd.Series(dtype=float),
                                             dt.date(2026, 1, 1))
        assert result is None

    def test_event_before_any_data_returns_none(self):
        dates = _trading_days(30)
        close = _series(dates, [100.0] * 30)
        bench = _series(dates, [20000.0] * 30)
        result = compute_constituent_metrics(close, None, bench, dates[0] - dt.timedelta(days=100))
        assert result is None

    def test_above_sma_and_rs_computed_for_a_real_date(self):
        dates = _trading_days(60)
        close = _series(dates, [100.0 + i * 0.5 for i in range(60)])  # steady uptrend
        bench = _series(dates, [20000.0] * 60)  # flat benchmark -> stock outperforms
        result = compute_constituent_metrics(close, None, bench, dates[40])
        assert result["above_20sma"] == "Y"
        assert result["rs_1m"] is not None and result["rs_1m"] > 0

    def test_missing_volume_series_leaves_ratio_none(self):
        dates = _trading_days(30)
        close = _series(dates, [100.0] * 30)
        bench = _series(dates, [20000.0] * 30)
        result = compute_constituent_metrics(close, None, bench, dates[25])
        assert result["volume_ratio"] is None


class TestAggregation:
    def test_no_measurable_constituents_returns_all_none(self):
        agg = aggregate_sector_metrics({"A": None, "B": None})
        assert agg["measurable_count"] == 0
        assert agg["pct_above_20sma"] is None

    def test_missing_constituents_reduce_denominator_not_treated_as_negative(self):
        """A missing (None) constituent must not count as 'not
        participating' — it's excluded from the percentage, not counted
        against it."""
        metrics = {
            "A": {"above_20sma": "Y", "rs_1w": 1.0, "rs_1m": 1.0, "rs_3m": 1.0, "volume_ratio": 1.0},
            "B": None,  # missing — must not drag the percentage down
        }
        agg = aggregate_sector_metrics(metrics)
        assert agg["constituent_count"] == 2
        assert agg["measurable_count"] == 1
        assert agg["pct_above_20sma"] == 100.0  # 1/1 measurable, not 1/2

    def test_broad_participation_high_percentage(self):
        metrics = {f"S{i}": {"above_20sma": "Y", "rs_1w": 1.0, "rs_1m": 1.0, "rs_3m": 1.0,
                            "volume_ratio": 2.0} for i in range(10)}
        agg = aggregate_sector_metrics(metrics)
        assert agg["pct_above_20sma"] == 100.0
        assert agg["pct_volume_expansion"] == 100.0

    def test_narrow_leadership_low_percentage(self):
        metrics = {f"S{i}": {"above_20sma": "Y" if i == 0 else "N", "rs_1w": 5.0 if i == 0 else -1.0,
                            "rs_1m": 5.0 if i == 0 else -1.0, "rs_3m": 0.0, "volume_ratio": 1.0}
                  for i in range(10)}
        agg = aggregate_sector_metrics(metrics)
        assert agg["pct_above_20sma"] == 10.0  # only 1/10
