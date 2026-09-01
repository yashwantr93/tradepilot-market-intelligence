"""
Results classifier tests — Phase 1 Event Intelligence Foundation.

Covers YoY calculation, insufficient history, invalid/zero/negative base,
and the new compute_all_metrics() multi-quarter retention behavior. The
ORIGINAL compute_metrics()/classify() are untouched this phase — these
tests confirm that explicitly (zero regression) alongside the new function.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from core.processing.results_classifier import classify, compute_all_metrics, compute_metrics


def _stmt(cols: list[dt.date], revenue: list[float], net_income: list[float]) -> pd.DataFrame:
    return pd.DataFrame({c: [ni, r] for c, ni, r in zip(cols, net_income, revenue)},
                        index=["Net Income", "Total Revenue"])


class TestComputeMetricsUnchanged:
    """The original single-latest-quarter function — must keep working exactly
    as before; nothing in Phase 1 touches its logic."""

    def test_yoy_growth_calculation(self):
        cols = [dt.date(2026, 3, 31), dt.date(2025, 12, 31), dt.date(2025, 9, 30),
                dt.date(2025, 6, 30), dt.date(2025, 3, 31)]
        stmt = _stmt(cols, revenue=[1150, 1100, 1050, 1000, 1000],
                    net_income=[150, 140, 130, 120, 100])
        m = compute_metrics(stmt)
        assert m is not None
        assert m["basis"] == "YoY"
        assert m["revenue_growth_pct"] == 15.0
        assert m["profit_growth_pct"] == 50.0

    def test_qoq_fallback_when_insufficient_history(self):
        cols = [dt.date(2026, 3, 31), dt.date(2025, 12, 31)]
        stmt = _stmt(cols, revenue=[1100, 1000], net_income=[120, 100])
        m = compute_metrics(stmt)
        assert m is not None
        assert m["basis"] == "QoQ"

    def test_none_when_empty(self):
        assert compute_metrics(pd.DataFrame()) is None
        assert compute_metrics(None) is None

    def test_none_when_missing_required_rows(self):
        stmt = pd.DataFrame({dt.date(2026, 3, 31): [100]}, index=["Some Other Row"])
        assert compute_metrics(stmt) is None

    def test_none_when_zero_base(self):
        cols = [dt.date(2026, 3, 31), dt.date(2025, 12, 31), dt.date(2025, 9, 30),
                dt.date(2025, 6, 30), dt.date(2025, 3, 31)]
        stmt = _stmt(cols, revenue=[1150, 1100, 1050, 1000, 0], net_income=[150, 140, 130, 120, 100])
        assert compute_metrics(stmt) is None

    def test_growth_none_on_negative_base(self):
        cols = [dt.date(2026, 3, 31), dt.date(2025, 12, 31), dt.date(2025, 9, 30),
                dt.date(2025, 6, 30), dt.date(2025, 3, 31)]
        # Prior-year net income is negative (a loss) -> profit_growth_pct should
        # be None (a % off a negative base is not meaningful), not a garbage number.
        stmt = _stmt(cols, revenue=[1150, 1100, 1050, 1000, 1000],
                    net_income=[150, 140, 130, 120, -50])
        m = compute_metrics(stmt)
        assert m is not None
        assert m["profit_growth_pct"] is None
        assert m["revenue_growth_pct"] == 15.0  # revenue base was still positive


class TestClassify:
    def test_strong(self):
        assert classify(20.0, 20.0) == "Strong"

    def test_weak_on_revenue_decline(self):
        assert classify(-5.0, 20.0) == "Weak"

    def test_weak_on_profit_decline(self):
        assert classify(20.0, -5.0) == "Weak"

    def test_neutral(self):
        assert classify(5.0, 5.0) == "Neutral"

    def test_neutral_when_growth_unavailable(self):
        assert classify(None, 20.0) == "Neutral"


class TestComputeAllMetrics:
    """Phase 1: retain multi-quarter information instead of discarding it."""

    def test_stores_raw_values_for_every_quarter_even_without_yoy(self):
        cols = [dt.date(2026, 3, 31), dt.date(2025, 12, 31), dt.date(2025, 9, 30),
                dt.date(2025, 6, 30), dt.date(2025, 3, 31)]
        stmt = _stmt(cols, revenue=[1150, 1100, 1050, 1000, 1000],
                    net_income=[150, 140, 130, 120, 100])
        all_metrics = compute_all_metrics(stmt)
        # All 5 quarters get a raw row — previously only 1 (the latest) was stored.
        assert len(all_metrics) == 5
        for row in all_metrics:
            assert row["revenue_actual"] is not None
            assert row["profit_actual"] is not None
            assert row["margin_pct"] is not None

    def test_only_the_yoy_eligible_quarter_gets_growth_fields(self):
        cols = [dt.date(2026, 3, 31), dt.date(2025, 12, 31), dt.date(2025, 9, 30),
                dt.date(2025, 6, 30), dt.date(2025, 3, 31)]
        stmt = _stmt(cols, revenue=[1150, 1100, 1050, 1000, 1000],
                    net_income=[150, 140, 130, 120, 100])
        all_metrics = compute_all_metrics(stmt)
        yoy_rows = [r for r in all_metrics if r["basis"] == "YoY"]
        raw_rows = [r for r in all_metrics if r["basis"] == "Raw"]
        assert len(yoy_rows) == 1  # only col0 has a comparator at col0+4
        assert len(raw_rows) == 4
        assert yoy_rows[0]["revenue_growth_pct"] == 15.0

    def test_empty_on_empty_statement(self):
        assert compute_all_metrics(pd.DataFrame()) == []
        assert compute_all_metrics(None) == []

    def test_skips_quarter_with_zero_revenue(self):
        cols = [dt.date(2026, 3, 31), dt.date(2025, 12, 31)]
        stmt = _stmt(cols, revenue=[1100, 0], net_income=[120, 100])
        all_metrics = compute_all_metrics(stmt)
        # The zero-revenue quarter can't even report a raw margin -> skipped,
        # not stored as a garbage/inf value.
        periods = [r["period_end"] for r in all_metrics]
        assert dt.date(2025, 12, 31) not in periods
        assert dt.date(2026, 3, 31) in periods
