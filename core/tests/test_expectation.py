"""
Expectation baseline tests — Phase 1 Event Intelligence Foundation.

Covers expectation availability (and explicit UNKNOWN when evidence is
insufficient), surprise calculation, and — critically — that EVENT
DIRECTION, EXPECTATION, ACTUAL and SURPRISE stay four separate values that
are never collapsed into one bullish/bearish field.
"""

from __future__ import annotations

from core.processing.expectation import compute_expectation, compute_surprise


class TestComputeExpectation:
    def test_unknown_with_zero_prior_samples(self):
        result = compute_expectation([])
        assert result["expectation_pct"] is None
        assert result["expectation_source"] == "unknown"
        assert result["expectation_confidence"] is None

    def test_trailing_average_with_one_sample_is_low_confidence(self):
        result = compute_expectation([12.0])
        assert result["expectation_pct"] == 12.0
        assert result["expectation_source"] == "internal_trailing_avg"
        assert result["expectation_confidence"] == "LOW"
        assert result["expectation_samples"] == 1

    def test_trailing_average_with_multiple_samples_is_medium_confidence(self):
        result = compute_expectation([10.0, 14.0, 12.0])
        assert result["expectation_pct"] == 12.0
        assert result["expectation_confidence"] == "MEDIUM"
        assert result["expectation_samples"] == 3

    def test_never_reports_high_confidence(self):
        """Phase 1 explicitly caps confidence at MEDIUM — the method is not
        validated enough to claim HIGH, no matter how many samples exist."""
        result = compute_expectation([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 18.0])
        assert result["expectation_confidence"] != "HIGH"

    def test_only_uses_the_configured_trailing_lookback(self):
        # trailing_lookback defaults to 3 — a 4th, older sample must not
        # silently influence the average.
        result_3 = compute_expectation([10.0, 20.0, 30.0])
        result_4 = compute_expectation([10.0, 20.0, 30.0, 1000.0])
        assert result_3["expectation_pct"] == result_4["expectation_pct"]
        assert result_4["expectation_samples"] == 3

    def test_unstable_history_returns_unknown_not_a_fabricated_average(self):
        """Prior prints swinging wildly (>60pp spread) shouldn't be averaged
        into a fake baseline — the method must refuse to guess."""
        result = compute_expectation([50.0, -40.0])
        assert result["expectation_pct"] is None
        assert result["expectation_source"] == "unknown"

    def test_never_fabricates_a_value_below_minimum_samples(self):
        result = compute_expectation([None, None])  # caller passed no real values
        assert result["expectation_pct"] is None


class TestComputeSurprise:
    def test_surprise_is_actual_minus_expected(self):
        assert compute_surprise(15.0, 30.0) == -15.0

    def test_headline_positive_can_be_a_negative_surprise(self):
        """The exact example from the product brief: +15% actual against a
        +30% expectation is headline-positive but a negative surprise."""
        actual, expected = 15.0, 30.0
        assert actual > 0  # headline: positive growth
        surprise = compute_surprise(actual, expected)
        assert surprise is not None and surprise < 0  # but a negative surprise

    def test_none_when_actual_missing(self):
        assert compute_surprise(None, 10.0) is None

    def test_none_when_expectation_missing(self):
        assert compute_surprise(10.0, None) is None

    def test_none_when_both_missing(self):
        assert compute_surprise(None, None) is None


class TestDirectionExpectationSurpriseSeparation:
    """These four concepts must never be collapsed into one field."""

    def test_direction_unaffected_by_surprise_sign(self):
        # A company can have DIRECTION=positive (actual growth > 0) while
        # SURPRISE is negative (missed its own trailing trend) — both facts
        # must be independently representable, not merged.
        actual_growth = 15.0          # raw direction: positive
        expectation = compute_expectation([25.0, 30.0, 35.0])
        surprise = compute_surprise(actual_growth, expectation["expectation_pct"])

        direction_is_positive = actual_growth > 0
        surprise_is_negative = surprise is not None and surprise < 0

        assert direction_is_positive is True
        assert surprise_is_negative is True
