"""
Sector/Theme -> Stock cross-reference tests — Phase 7. Pure logic, no DB.
"""

from __future__ import annotations

from event_intelligence.cross_reference import build_cross_reference


def _event(event_type="Large Order Win", event_direction="Bullish", materiality_tier="HIGH",
          market_reaction_state="POSITIVE", continuation_state="CONTINUATION",
          technical_confirmation="CONFIRMED", signal_direction="LONG", corporate_action_id=1,
          expectation_available=False, surprise_pct=None, time_horizon="SWING",
          evidence_for=None, evidence_against=None):
    return {"corporate_action_id": corporate_action_id, "event_type": event_type,
            "event_direction": event_direction, "materiality_tier": materiality_tier,
            "expectation_available": expectation_available, "surprise_pct": surprise_pct,
            "market_reaction_state": market_reaction_state, "continuation_state": continuation_state,
            "technical_confirmation": technical_confirmation, "signal_direction": signal_direction,
            "time_horizon": time_horizon, "evidence_for": evidence_for or ["evidence"],
            "evidence_against": evidence_against or []}


class TestNoCatalyst:
    def test_missing_company_event_is_no_catalyst(self):
        result = build_cross_reference("Technology", "EARLY_MOMENTUM", "BULLISH", "XYZ",
                                       "leader", None)
        assert result["trade_context"] == "NO_CATALYST"
        assert result["company_event_id"] is None

    def test_no_catalyst_has_low_data_quality(self):
        result = build_cross_reference("Technology", "EARLY_MOMENTUM", "BULLISH", "XYZ",
                                       "leader", None)
        assert result["data_quality"] == "LOW"


class TestLongContext:
    def test_early_sector_early_stock_positive_catalyst(self):
        """Case §8.B — early momentum sector + early participant + positive catalyst."""
        result = build_cross_reference("Industrials", "EARLY_MOMENTUM", "BULLISH", "ABC",
                                       "early_participant", _event())
        assert result["trade_context"] in ("LONG_CONTEXT", "WATCH_CANDIDATE")
        assert result["conflicts_json"] == []

    def test_leader_in_bullish_sector_with_long_signal(self):
        result = build_cross_reference("Technology", "EARLY_MOMENTUM", "BULLISH", "ABC",
                                       "leader", _event(market_reaction_state="STRONG POSITIVE"))
        assert result["trade_context"] == "LONG_CONTEXT"


class TestMatureCaution:
    def test_strong_sector_mature_extended_stock(self):
        """Case §8.A — sector already strong + stock already extended."""
        result = build_cross_reference("Consumer Defensive", "CONFIRMED_STRONG", "BULLISH", "ABC",
                                       "leader", _event(technical_confirmation="CONFIRMED"))
        assert result["trade_context"] == "MATURE_CAUTION"


class TestWatchCandidate:
    def test_material_catalyst_but_no_reaction_yet(self):
        """Case §8.C — strong catalyst, price hasn't moved yet."""
        result = build_cross_reference("Industrials", "DEVELOPING", "BULLISH", "ABC",
                                       "early_participant",
                                       _event(materiality_tier="HIGH", market_reaction_state="NEUTRAL"))
        assert result["trade_context"] == "WATCH_CANDIDATE"


class TestShortContext:
    def test_weakening_sector_negative_stock_breakdown(self):
        """Case §8.D — weakening sector + negative catalyst + breakdown."""
        result = build_cross_reference("Technology", "WEAKENING", "BEARISH", "XYZ", "laggard",
                                       _event(event_direction="Bearish", materiality_tier="HIGH",
                                             market_reaction_state="STRONG NEGATIVE",
                                             technical_confirmation="CONFIRMED",
                                             signal_direction="SHORT"))
        assert result["trade_context"] == "SHORT_CONTEXT"

    def test_weak_sector_does_not_force_a_short(self):
        """Explicit requirement: sector weakness alone (no negative company
        event / no SHORT signal) must not force SHORT_CONTEXT."""
        result = build_cross_reference("Technology", "WEAKENING", "BEARISH", "XYZ", "laggard",
                                       _event(event_direction="Bullish", signal_direction="LONG"))
        assert result["trade_context"] != "SHORT_CONTEXT"


class TestContradictions:
    def test_strong_sector_non_participating_weak_stock_with_negative_event(self):
        result = build_cross_reference("Industrials", "CONFIRMED_STRONG", "BULLISH", "XYZ",
                                       "non_participant", _event(event_direction="Bearish"))
        assert result["trade_context"] == "CONTRADICTED"
        assert len(result["conflicts_json"]) > 0

    def test_weak_sector_strong_outperforming_stock(self):
        result = build_cross_reference("Technology", "WEAKENING", "BEARISH", "ABC", "leader",
                                       _event(event_direction="Bullish"))
        assert result["trade_context"] == "CONTRADICTED"
        assert any("outperforming" in c for c in result["conflicts_json"])

    def test_positive_sector_negative_company_event(self):
        """Sector strong but individual company has a negative catalyst."""
        result = build_cross_reference("Industrials", "EARLY_MOMENTUM", "BULLISH", "XYZ",
                                       "early_participant", _event(event_direction="Bearish"))
        assert result["trade_context"] == "CONTRADICTED"
        assert any("Bearish" in c for c in result["conflicts_json"])

    def test_negative_sector_positive_company_event(self):
        """Company-specific catalyst may override broader sector weakness —
        must be surfaced, not hidden."""
        result = build_cross_reference("Technology", "WEAKENING", "BEARISH", "ABC", "laggard",
                                       _event(event_direction="Bullish"))
        assert result["trade_context"] == "CONTRADICTED"
        assert any("override" in c for c in result["conflicts_json"])

    def test_conflicts_are_never_silently_dropped_even_when_other_evidence_is_strong(self):
        """A conflict must dominate trade_context even if the stock would
        otherwise look like a strong LONG_CONTEXT candidate."""
        result = build_cross_reference("Industrials", "EARLY_MOMENTUM", "BULLISH", "ABC",
                                       "leader", _event(event_direction="Bearish",
                                                        market_reaction_state="STRONG POSITIVE"))
        assert result["trade_context"] == "CONTRADICTED"


class TestEvidenceIndependence:
    def test_sector_and_stock_evidence_are_kept_in_separate_fields(self):
        result = build_cross_reference("Technology", "EARLY_MOMENTUM", "BULLISH", "ABC",
                                       "leader", _event())
        assert result["sector_evidence_json"] != result["stock_evidence_json"]
        assert "Technology" in result["sector_evidence_json"][0]
        assert "ABC" in result["stock_evidence_json"][0]

    def test_stock_event_does_not_appear_inside_sector_evidence(self):
        result = build_cross_reference("Technology", "EARLY_MOMENTUM", "BULLISH", "ABC",
                                       "leader", _event(event_type="Large Order Win"))
        assert not any("Large Order Win" in e for e in result["sector_evidence_json"])


class TestLongShortSymmetry:
    def test_long_and_short_context_use_symmetric_structure(self):
        long_result = build_cross_reference("Industrials", "EARLY_MOMENTUM", "BULLISH", "ABC",
                                            "leader", _event(market_reaction_state="STRONG POSITIVE"))
        short_result = build_cross_reference("Industrials", "WEAKENING", "BEARISH", "XYZ",
                                             "laggard", _event(event_direction="Bearish",
                                                               market_reaction_state="STRONG NEGATIVE",
                                                               signal_direction="SHORT"))
        assert long_result["trade_context"] == "LONG_CONTEXT"
        assert short_result["trade_context"] == "SHORT_CONTEXT"
        assert set(long_result.keys()) == set(short_result.keys())  # identical schema, both directions


class TestMissingSubFields:
    def test_missing_technical_confirmation_still_produces_a_result(self):
        result = build_cross_reference("Technology", "EARLY_MOMENTUM", "BULLISH", "ABC",
                                       "leader", _event(technical_confirmation="UNKNOWN"))
        assert result["technical_confirmation"] == "UNKNOWN"
        assert result["trade_context"] is not None

    def test_missing_reaction_lowers_data_quality(self):
        result = build_cross_reference("Technology", "EARLY_MOMENTUM", "BULLISH", "ABC",
                                       "leader", _event(market_reaction_state="UNKNOWN"))
        assert result["data_quality"] in ("LOW", "MEDIUM")
