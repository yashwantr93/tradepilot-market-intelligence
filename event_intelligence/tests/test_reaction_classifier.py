"""
Market Reaction classification tests — Phase 3.

Covers reaction-state tiers (evidence-calibrated thresholds), continuation
vs. reversal, event-direction alignment — and, critically, that a positive
event with a negative reaction (and vice versa) is preserved and correctly
labeled CONTRADICTS, never silently reconciled.
"""

from __future__ import annotations

from event_intelligence.reaction_classifier import (
    classify_continuation,
    classify_event_alignment,
    classify_reaction_state,
)


class TestReactionStateTiers:
    def test_unknown_when_no_5d_data(self):
        state, reason = classify_reaction_state(None)
        assert state == "UNKNOWN"

    def test_strong_positive(self):
        state, _ = classify_reaction_state(8.0)
        assert state == "STRONG POSITIVE"

    def test_positive(self):
        state, _ = classify_reaction_state(4.0)
        assert state == "POSITIVE"

    def test_neutral_band(self):
        state, _ = classify_reaction_state(1.0)
        assert state == "NEUTRAL"
        state, _ = classify_reaction_state(-1.0)
        assert state == "NEUTRAL"

    def test_negative(self):
        state, _ = classify_reaction_state(-4.0)
        assert state == "NEGATIVE"

    def test_strong_negative(self):
        state, _ = classify_reaction_state(-8.0)
        assert state == "STRONG NEGATIVE"

    def test_boundary_at_moderate_threshold(self):
        # moderate_pct = 2.5 -> exactly 2.5 should be POSITIVE (>=), not NEUTRAL
        state, _ = classify_reaction_state(2.5)
        assert state == "POSITIVE"

    def test_reason_is_human_readable(self):
        _, reason = classify_reaction_state(4.2)
        assert "4.2" in reason
        assert "%" in reason


class TestContinuation:
    def test_insufficient_data_when_missing(self):
        assert classify_continuation(None, 5.0) == "INSUFFICIENT_DATA"
        assert classify_continuation(1.0, None) == "INSUFFICIENT_DATA"

    def test_continuation_same_direction_growing(self):
        assert classify_continuation(3.0, 6.0) == "CONTINUATION"

    def test_reversal_opposite_direction(self):
        assert classify_continuation(3.0, -2.0) == "REVERSAL"

    def test_negative_continuation(self):
        assert classify_continuation(-3.0, -6.0) == "CONTINUATION"

    def test_tiny_initial_move_is_insufficient_not_a_direction_call(self):
        assert classify_continuation(0.1, 5.0) == "INSUFFICIENT_DATA"

    def test_partial_reversal_same_sign_but_shrinking(self):
        """The real case found during Phase 3's data validation: BAJAJ-AUTO
        moved 1d -2.79% -> 5d -2.59% — same sign, merely fading, never
        crossed zero. Must be distinguished from a genuine sign flip."""
        assert classify_continuation(-2.7889, -2.5883) == "PARTIAL_REVERSAL"

    def test_true_reversal_is_a_genuine_sign_flip(self):
        """The real case that must stay REVERSAL: VISAKAIND moved
        1d -2.13% -> 5d +0.98% — an actual crossing through zero."""
        assert classify_continuation(-2.1308, 0.9827) == "REVERSAL"


class TestEventAlignment:
    def test_unknown_when_reaction_unknown(self):
        assert classify_event_alignment("Bullish", "UNKNOWN") == "UNKNOWN"

    def test_not_applicable_for_neutral_event(self):
        assert classify_event_alignment("Neutral", "STRONG POSITIVE") == "NOT_APPLICABLE"

    def test_not_applicable_for_ambiguous_event(self):
        assert classify_event_alignment("Ambiguous", "NEGATIVE") == "NOT_APPLICABLE"

    def test_bullish_event_positive_reaction_is_aligned(self):
        assert classify_event_alignment("Bullish", "POSITIVE") == "ALIGNED"
        assert classify_event_alignment("Bullish", "STRONG POSITIVE") == "ALIGNED"

    def test_bullish_event_negative_reaction_contradicts(self):
        """THE critical case: a positive event whose price reaction is
        negative — must remain visible, never silently reconciled."""
        assert classify_event_alignment("Bullish", "NEGATIVE") == "CONTRADICTS"
        assert classify_event_alignment("Bullish", "STRONG NEGATIVE") == "CONTRADICTS"

    def test_bearish_event_negative_reaction_is_aligned(self):
        assert classify_event_alignment("Bearish", "NEGATIVE") == "ALIGNED"

    def test_bearish_event_positive_reaction_contradicts(self):
        """The mirror case: a negative event whose price reaction is
        positive — equally must remain visible."""
        assert classify_event_alignment("Bearish", "POSITIVE") == "CONTRADICTS"

    def test_neutral_reaction_is_ambiguous_not_forced_either_way(self):
        assert classify_event_alignment("Bullish", "NEUTRAL") == "AMBIGUOUS"
        assert classify_event_alignment("Bearish", "NEUTRAL") == "AMBIGUOUS"
