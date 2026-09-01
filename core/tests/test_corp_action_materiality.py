"""
Corporate-action materiality tests — Phase 2 Event Materiality.

Covers dividend-yield and order-value materiality: valid denominator, missing
denominator, USD-currency non-conversion, no-magnitude UNKNOWN, and boundary
behavior. Several cases reuse the real ITC/LT figures measured during this
phase's real-data audit (see the Phase 2 report's REAL-DATA VALIDATION
section) so the tests double as a record of that verification.
"""

from __future__ import annotations

import datetime as dt

from core.pipelines.corp_action_materiality_pipeline import run_corp_action_materiality
from core.processing.corp_action_materiality import (
    compute_dividend_materiality,
    compute_large_order_materiality,
)


class TestDividendMateriality:
    def test_real_itc_dividend_yield(self):
        """Real data: ITC 'Dividend - Rs 7.50 Per Share' vs. a ₹287.25 close
        -> 2.61% yield, the highest in the locally observed distribution."""
        result = compute_dividend_materiality("Dividend - Rs 7.50 Per Share", 287.25)
        assert result["magnitude_value"] == 7.5
        assert result["magnitude_unit"] == "PER_SHARE_INR"
        assert result["materiality_tier"] == "HIGH"
        assert "2.6" in result["materiality_reason"]

    def test_low_yield_tier(self):
        # AXISBANK real case: Rs 1/share vs ~1245.80 close -> 0.08% yield
        result = compute_dividend_materiality("Dividend - Rs 1 Per Share", 1245.80)
        assert result["materiality_tier"] == "LOW"

    def test_unknown_when_no_amount_in_text(self):
        result = compute_dividend_materiality(
            "Record Date International Conveyors Limited ... Record date is 17-Sep-2026.",
            100.0,
        )
        assert result["materiality_tier"] == "UNKNOWN"
        assert result["magnitude_value"] is None

    def test_unknown_when_no_price_available(self):
        result = compute_dividend_materiality("Dividend - Rs 5 Per Share", None)
        assert result["materiality_tier"] == "UNKNOWN"
        assert result["magnitude_value"] == 5.0  # magnitude WAS extracted
        assert result["denominator_value"] is None

    def test_unknown_when_price_is_zero(self):
        result = compute_dividend_materiality("Dividend - Rs 5 Per Share", 0.0)
        assert result["materiality_tier"] == "UNKNOWN"

    def test_reason_is_human_readable_and_explains_the_ratio(self):
        result = compute_dividend_materiality("Dividend - Rs 10 Per Share", 1000.0)
        assert "10" in result["materiality_reason"]
        assert "1000" in result["materiality_reason"]
        assert "%" in result["materiality_reason"]


class TestLargeOrderMateriality:
    def test_real_lt_order_value_ratio(self):
        """Real order text (LT, Rs 15000 Cr) against a trailing-revenue
        denominator — see the Phase 2 report for the explicit caveat that
        this particular denominator is currently offline-seed data, not a
        verified live figure; the CALCULATION is what's being tested here."""
        result = compute_large_order_materiality(
            "Bagging/Receiving of orders - bags order worth Rs 15000 Cr", 13623.12
        )
        assert result["magnitude_value"] == 15000.0
        assert result["magnitude_unit"] == "INR_CR"
        assert result["materiality_tier"] == "TRANSFORMATIONAL"  # ~110% of trailing revenue

    def test_unknown_when_no_order_value_in_text(self):
        result = compute_large_order_materiality(
            "Bagging/Receiving of orders/contracts Company has informed the Exchange "
            "about Bagging/Receiving of orders/contracts", 1000.0
        )
        assert result["materiality_tier"] == "UNKNOWN"
        assert result["magnitude_value"] is None

    def test_unknown_when_no_trailing_revenue(self):
        result = compute_large_order_materiality(
            "Bagging/Receiving of orders - bags order worth Rs 500 Cr", None
        )
        assert result["materiality_tier"] == "UNKNOWN"
        assert result["magnitude_value"] == 500.0  # magnitude WAS extracted
        assert result["denominator_value"] is None

    def test_unknown_when_trailing_revenue_is_zero(self):
        result = compute_large_order_materiality(
            "Bagging/Receiving of orders - bags order worth Rs 500 Cr", 0.0
        )
        assert result["materiality_tier"] == "UNKNOWN"

    def test_usd_only_is_unknown_not_converted(self):
        """No fabricated FX conversion — real LTTS case."""
        result = compute_large_order_materiality(
            "L&T Technology Services has secured a landmark engagement valued at over "
            "$75 Million from a leading global technology enterprise.", 5000.0
        )
        assert result["materiality_tier"] == "UNKNOWN"
        assert result["magnitude_unit"] == "USD_MN"
        assert result["magnitude_value"] == 75.0
        assert "not implemented" in result["materiality_reason"].lower() or \
               "conversion" in result["materiality_reason"].lower()

    def test_low_tier_small_order(self):
        result = compute_large_order_materiality(
            "Bagging/Receiving of orders - bags order worth Rs 50 Cr", 10000.0
        )
        assert result["materiality_tier"] == "LOW"  # 0.5% of revenue


def _fake_action(id_, symbol, event_type, summary):
    return {"id": id_, "symbol": symbol, "announcement_date": dt.date(2026, 1, 1),
            "event_summary": summary, "event_type": event_type}


class TestMaterialityPipelineWiring:
    """Business-logic wiring tests — dependency-injected repo calls via
    monkeypatch, same hermetic pattern as Phase 1.5's backfill tests."""

    def test_dividend_row_looks_up_price_and_stores_result(self, monkeypatch):
        actions = [_fake_action(1, "ITC", "Dividend", "Dividend - Rs 7.50 Per Share")]
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".get_corporate_actions_by_type", lambda types, ids=None: actions)
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".get_latest_close", lambda symbol: 287.25)
        captured = {}
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".upsert_corp_action_materiality",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        report = run_corp_action_materiality()

        assert report["processed"] == 1
        assert captured["rows"][0]["materiality_tier"] == "HIGH"
        assert captured["rows"][0]["corporate_action_id"] == 1

    def test_large_order_row_looks_up_trailing_revenue(self, monkeypatch):
        actions = [_fake_action(2, "LT", "Large Order Win",
                                "Bagging/Receiving of orders - bags order worth Rs 15000 Cr")]
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".get_corporate_actions_by_type", lambda types, ids=None: actions)
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".get_trailing_revenue", lambda symbol, quarters=4: 13623.12)
        captured = {}
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".upsert_corp_action_materiality",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        report = run_corp_action_materiality()

        assert report["processed"] == 1
        assert captured["rows"][0]["materiality_tier"] == "TRANSFORMATIONAL"

    def test_every_row_gets_a_result_including_unknown(self, monkeypatch):
        """No magnitude, no denominator — must still produce an UNKNOWN row,
        never silently skip it."""
        actions = [_fake_action(3, "XYZ", "Dividend", "Record date notice, no amount stated")]
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".get_corporate_actions_by_type", lambda types, ids=None: actions)
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".get_latest_close", lambda symbol: None)
        captured = {}
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".upsert_corp_action_materiality",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        report = run_corp_action_materiality()

        assert report["by_tier"] == {"UNKNOWN": 1}
        assert captured["rows"][0]["materiality_tier"] == "UNKNOWN"

    def test_only_wired_event_types_are_requested(self, monkeypatch):
        requested_types = []

        def fake_get(types, ids=None):
            requested_types.extend(types)
            return []
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".get_corporate_actions_by_type", fake_get)
        monkeypatch.setattr("core.pipelines.corp_action_materiality_pipeline.repo"
                            ".upsert_corp_action_materiality", lambda rows: 0)

        run_corp_action_materiality()

        assert set(requested_types) == {"Dividend", "Large Order Win"}
