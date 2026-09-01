"""
Materiality tests — Phase 1 Event Intelligence Foundation.

Covers valid-denominator ratio tiering, missing-denominator UNKNOWN, and
boundary/edge cases. No black-box scoring — every result must carry an
explainable reason string.
"""

from __future__ import annotations

from core.processing.materiality import compute_ratio_materiality, compute_results_materiality

_THRESH = {"low_pct": 5.0, "medium_pct": 10.0, "high_pct": 20.0}


class TestResultsMateriality:
    def test_unknown_when_surprise_missing(self):
        result = compute_results_materiality(None)
        assert result["materiality_tier"] == "UNKNOWN"
        assert isinstance(result["materiality_reason"], str) and result["materiality_reason"]

    def test_low_tier_for_small_surprise(self):
        result = compute_results_materiality(2.0)
        assert result["materiality_tier"] == "LOW"

    def test_medium_tier(self):
        result = compute_results_materiality(7.0)
        assert result["materiality_tier"] == "MEDIUM"

    def test_high_tier(self):
        result = compute_results_materiality(15.0)
        assert result["materiality_tier"] == "HIGH"

    def test_transformational_tier_for_large_surprise(self):
        result = compute_results_materiality(35.0)
        assert result["materiality_tier"] == "TRANSFORMATIONAL"

    def test_negative_surprise_uses_absolute_magnitude(self):
        """A -35pp surprise is just as material as a +35pp one — direction
        is a separate concept (see expectation.py), materiality is about
        magnitude."""
        pos = compute_results_materiality(35.0)
        neg = compute_results_materiality(-35.0)
        assert pos["materiality_tier"] == neg["materiality_tier"] == "TRANSFORMATIONAL"

    def test_every_result_has_a_human_readable_reason(self):
        for surprise in (None, 2.0, 7.0, 15.0, 35.0, -35.0):
            result = compute_results_materiality(surprise)
            assert isinstance(result["materiality_reason"], str)
            assert len(result["materiality_reason"]) > 0

    def test_boundary_exactly_at_threshold(self):
        # low_pct threshold is 5.0 -> exactly 5.0 should NOT be LOW (uses <)
        result = compute_results_materiality(5.0)
        assert result["materiality_tier"] == "MEDIUM"


class TestRatioMateriality:
    def test_unknown_when_value_missing(self):
        result = compute_ratio_materiality(None, 1000.0, "revenue", _THRESH)
        assert result["materiality_tier"] == "UNKNOWN"

    def test_unknown_when_denominator_missing(self):
        result = compute_ratio_materiality(100.0, None, "revenue", _THRESH)
        assert result["materiality_tier"] == "UNKNOWN"

    def test_unknown_when_denominator_zero(self):
        result = compute_ratio_materiality(100.0, 0.0, "revenue", _THRESH)
        assert result["materiality_tier"] == "UNKNOWN"

    def test_unknown_when_denominator_negative(self):
        """A ratio against a negative denominator (e.g. negative trailing
        revenue base) is not meaningful — must not be silently computed."""
        result = compute_ratio_materiality(100.0, -50.0, "revenue", _THRESH)
        assert result["materiality_tier"] == "UNKNOWN"

    def test_low_tier(self):
        result = compute_ratio_materiality(30.0, 1000.0, "revenue", _THRESH)  # 3%
        assert result["materiality_tier"] == "LOW"

    def test_high_tier(self):
        result = compute_ratio_materiality(150.0, 1000.0, "revenue", _THRESH)  # 15%
        assert result["materiality_tier"] == "HIGH"

    def test_transformational_tier(self):
        result = compute_ratio_materiality(250.0, 1000.0, "revenue", _THRESH)  # 25%
        assert result["materiality_tier"] == "TRANSFORMATIONAL"

    def test_uses_absolute_value(self):
        pos = compute_ratio_materiality(250.0, 1000.0, "revenue", _THRESH)
        neg = compute_ratio_materiality(-250.0, 1000.0, "revenue", _THRESH)
        assert pos["materiality_tier"] == neg["materiality_tier"]
