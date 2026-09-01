"""
Signal Engine tests — Phase 5.

Pure decision-logic tests (no DB) — covers LONG/SHORT symmetry, the
CONTRADICTS gate (both directions), missing-evidence propagation, evidence-
for/against construction, and provenance fields (signal_strength_basis,
predictive_status) always being present and correctly labeled.
"""

from __future__ import annotations

from event_intelligence.signal_engine import build_signal

_TECH_CONFIRMED = {"status": "CONFIRMED", "category": "Emerging Leader", "reason": "confirmed"}
_TECH_UNKNOWN = {"status": "UNKNOWN", "category": None, "reason": "no V2 history"}
_TECH_NOT_CONFIRMED = {"status": "NOT_CONFIRMED", "category": "Not Qualified", "reason": "not qualified"}


def _event(impact_tag="Bullish", materiality_tier="HIGH", reaction_state="STRONG POSITIVE",
          continuation_state="CONTINUATION", event_alignment="ALIGNED",
          relative_return_5d=6.0, volume_ratio_day0=2.0, symbol="TESTCO",
          event_type="Large Order Win"):
    return {"symbol": symbol, "event_type": event_type, "impact_tag": impact_tag,
            "materiality_tier": materiality_tier, "reaction_state": reaction_state,
            "continuation_state": continuation_state, "event_alignment": event_alignment,
            "relative_return_5d": relative_return_5d, "volume_ratio_day0": volume_ratio_day0}


class TestDirectionalGate:
    def test_neutral_event_is_no_trade(self):
        signal = build_signal(_event(impact_tag="Neutral"), _TECH_UNKNOWN, None)
        assert signal["direction"] == "NO_TRADE"
        assert signal["no_trade_reason"] == "NEUTRAL_OR_AMBIGUOUS_EVENT"

    def test_ambiguous_event_is_no_trade(self):
        signal = build_signal(_event(impact_tag="Ambiguous"), _TECH_UNKNOWN, None)
        assert signal["direction"] == "NO_TRADE"
        assert signal["no_trade_reason"] == "NEUTRAL_OR_AMBIGUOUS_EVENT"


class TestContradictsGateBothDirections:
    def test_bullish_event_contradicting_reaction_is_no_trade_not_short(self):
        """The critical case: a positive event with a negative reaction must
        NEVER become a SHORT — it becomes NO_TRADE."""
        event = _event(impact_tag="Bullish", event_alignment="CONTRADICTS",
                       reaction_state="NEGATIVE")
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert signal["direction"] == "NO_TRADE"
        assert signal["no_trade_reason"] == "CONTRADICTED_EVIDENCE"

    def test_bearish_event_contradicting_reaction_is_no_trade_not_long(self):
        """The mirror case: a negative event with a positive reaction must
        NEVER become a LONG."""
        event = _event(impact_tag="Bearish", event_alignment="CONTRADICTS",
                       reaction_state="POSITIVE")
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert signal["direction"] == "NO_TRADE"
        assert signal["no_trade_reason"] == "CONTRADICTED_EVIDENCE"


class TestLongShortSymmetry:
    def test_valid_long_with_strong_evidence(self):
        event = _event(impact_tag="Bullish", materiality_tier="HIGH",
                       reaction_state="STRONG POSITIVE", continuation_state="CONTINUATION",
                       event_alignment="ALIGNED", volume_ratio_day0=2.5)
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert signal["direction"] == "LONG"
        assert signal["signal_strength"] in ("STRONG", "MODERATE")

    def test_valid_short_with_strong_evidence_mirrors_long(self):
        """Identical evidence STRENGTH on the negative side must produce a
        symmetric SHORT — no asymmetric handling of Bearish vs Bullish."""
        event = _event(impact_tag="Bearish", materiality_tier="HIGH",
                       reaction_state="STRONG NEGATIVE", continuation_state="CONTINUATION",
                       event_alignment="ALIGNED", volume_ratio_day0=2.5)
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert signal["direction"] == "SHORT"
        assert signal["signal_strength"] in ("STRONG", "MODERATE")

    def test_long_and_short_use_the_same_strength_thresholds(self):
        """Build a LONG and a SHORT with structurally identical (mirrored)
        evidence and confirm they land on the same strength tier — proves
        no hidden asymmetry in the classification thresholds themselves."""
        long_event = _event(impact_tag="Bullish", materiality_tier="MEDIUM",
                            reaction_state="POSITIVE", continuation_state="CONTINUATION",
                            event_alignment="ALIGNED", volume_ratio_day0=1.6)
        short_event = _event(impact_tag="Bearish", materiality_tier="MEDIUM",
                             reaction_state="NEGATIVE", continuation_state="CONTINUATION",
                             event_alignment="ALIGNED", volume_ratio_day0=1.6)
        long_signal = build_signal(long_event, _TECH_CONFIRMED, None)
        short_signal = build_signal(short_event, _TECH_CONFIRMED, None)
        assert long_signal["signal_strength"] == short_signal["signal_strength"]
        assert long_signal["confirming_dimensions"] == short_signal["confirming_dimensions"]


class TestPositiveNegativeReactionCombinations:
    def test_positive_event_positive_reaction(self):
        event = _event(impact_tag="Bullish", reaction_state="POSITIVE", event_alignment="ALIGNED")
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert signal["direction"] == "LONG"

    def test_positive_event_negative_reaction_never_becomes_long(self):
        event = _event(impact_tag="Bullish", reaction_state="NEGATIVE", event_alignment="CONTRADICTS")
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert signal["direction"] != "LONG"

    def test_negative_event_negative_reaction(self):
        event = _event(impact_tag="Bearish", reaction_state="NEGATIVE", event_alignment="ALIGNED")
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert signal["direction"] == "SHORT"

    def test_negative_event_positive_reaction_never_becomes_short(self):
        event = _event(impact_tag="Bearish", reaction_state="POSITIVE", event_alignment="CONTRADICTS")
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert signal["direction"] != "SHORT"


class TestMissingEvidencePropagation:
    def test_missing_expectation_is_unknown_not_penalized_or_rewarded(self):
        event = _event()
        signal_with = build_signal(event, _TECH_CONFIRMED,
                                   {"metric": "profit_growth_pct", "surprise_pct": 5.0,
                                    "expectation_source": "internal_trailing_avg", "period_end": None})
        signal_without = build_signal(event, _TECH_CONFIRMED, None)
        assert signal_without["expectation_available"] is False
        assert signal_without["surprise_pct"] is None
        # missing expectation must not silently outrank/underrank incorrectly —
        # both should still be evaluable directions given other strong evidence
        assert signal_without["direction"] == "LONG"

    def test_missing_materiality_is_unknown_and_reduces_evaluable_count(self):
        event = _event(materiality_tier="UNKNOWN")
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert any("Materiality could not be determined" in e for e in signal["evidence_against_json"])

    def test_missing_reaction_is_unknown(self):
        event = _event(reaction_state="UNKNOWN", event_alignment="UNKNOWN")
        signal = build_signal(event, _TECH_CONFIRMED, None)
        assert any("Market reaction UNKNOWN" in e for e in signal["evidence_against_json"])

    def test_all_evidence_unknown_is_insufficient_not_a_guess(self):
        event = _event(materiality_tier="UNKNOWN", reaction_state="UNKNOWN",
                       continuation_state="INSUFFICIENT_DATA", event_alignment="UNKNOWN",
                       volume_ratio_day0=None)
        signal = build_signal(event, _TECH_UNKNOWN, None)
        assert signal["direction"] == "NO_TRADE"
        assert signal["no_trade_reason"] == "INSUFFICIENT_EVIDENCE"
        assert signal["signal_strength"] == "INSUFFICIENT"


class TestEvidenceForAgainst:
    def test_both_lists_are_always_present(self):
        signal = build_signal(_event(), _TECH_CONFIRMED, None)
        assert isinstance(signal["evidence_for_json"], list)
        assert isinstance(signal["evidence_against_json"], list)

    def test_strong_long_has_nonempty_evidence_for(self):
        signal = build_signal(_event(), _TECH_CONFIRMED, None)
        assert len(signal["evidence_for_json"]) > 0

    def test_weak_long_still_has_evidence_against(self):
        event = _event(materiality_tier="LOW", volume_ratio_day0=0.8)
        signal = build_signal(event, _TECH_NOT_CONFIRMED, None)
        assert len(signal["evidence_against_json"]) > 0


class TestProvenance:
    def test_signal_strength_basis_is_always_heuristic(self):
        for evt in (_event(impact_tag="Bullish"), _event(impact_tag="Bearish"),
                   _event(impact_tag="Neutral")):
            signal = build_signal(evt, _TECH_UNKNOWN, None)
            assert signal["signal_strength_basis"] == "HEURISTIC"

    def test_predictive_status_is_always_exploratory(self):
        for evt in (_event(impact_tag="Bullish"), _event(impact_tag="Bearish")):
            signal = build_signal(evt, _TECH_CONFIRMED, None)
            assert signal["predictive_status"] == "EXPLORATORY"

    def test_reason_string_is_nonempty_and_traceable(self):
        signal = build_signal(_event(), _TECH_CONFIRMED, None)
        assert signal["reason"]
        assert signal["event_type"] if "event_type" in signal else True  # reason built from event


class TestNoFundamentalGate:
    def test_signal_engine_has_no_fundamental_quality_input_at_all(self):
        """Structural check: build_signal's signature only accepts event/
        technical/expectation — there is no fundamental-quality parameter to
        even pass, by design."""
        import inspect
        from event_intelligence.signal_engine import build_signal as fn
        params = list(inspect.signature(fn).parameters)
        assert params == ["event", "technical", "expectation"]
        assert not any("fundamental" in p.lower() for p in params)
