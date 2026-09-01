"""
Opportunity Intelligence tests — Phase 8. Pure logic, no DB.
"""

from __future__ import annotations

from event_intelligence.opportunity import build_opportunity


def _signal(direction="LONG", signal_strength="STRONG", materiality_tier="HIGH",
           market_reaction_state="STRONG POSITIVE", continuation_state="CONTINUATION",
           technical_confirmation="CONFIRMED", time_horizon="SWING", data_quality="HIGH",
           symbol="ABC", corporate_action_id=1, event_type="Large Order Win",
           evidence_for=None, evidence_against=None, risk="some risk", invalidation="some invalidation"):
    return {"symbol": symbol, "corporate_action_id": corporate_action_id, "event_type": event_type,
            "direction": direction, "signal_strength": signal_strength,
            "materiality_tier": materiality_tier, "market_reaction_state": market_reaction_state,
            "continuation_state": continuation_state, "technical_confirmation": technical_confirmation,
            "time_horizon": time_horizon, "data_quality": data_quality,
            "evidence_for": evidence_for or ["stock evidence"], "evidence_against": evidence_against or [],
            "risk": risk, "invalidation": invalidation}


def _cross_ref(sector_stage="EARLY_MOMENTUM", participation_role="early_participant",
              trade_context="LONG_CONTEXT", conflicts=None, sector_or_theme="Industrials"):
    return {"sector_or_theme": sector_or_theme, "sector_stage": sector_stage,
            "participation_role": participation_role, "trade_context": trade_context,
            "conflicts_json": conflicts or [], "sector_evidence_json": ["sector evidence"]}


class TestBaseTiers:
    def test_strong_signal_no_sector_data_is_strong_tier_event_driven(self):
        opp = build_opportunity(_signal(signal_strength="STRONG"), None)
        assert opp["opportunity_type"] == "EVENT_DRIVEN"
        assert opp["tier"] == "STRONG"

    def test_weak_signal_no_sector_data_is_moderate_tier(self):
        opp = build_opportunity(_signal(signal_strength="WEAK"), None)
        assert opp["tier"] == "MODERATE"

    def test_short_direction_mirrors_long(self):
        long_opp = build_opportunity(_signal(direction="LONG", signal_strength="STRONG"), None)
        short_opp = build_opportunity(_signal(direction="SHORT", signal_strength="STRONG"), None)
        assert long_opp["tier"] == short_opp["tier"]
        assert set(long_opp.keys()) == set(short_opp.keys())


class TestConfluence:
    def test_aligned_sector_upgrades_tier(self):
        no_sector = build_opportunity(_signal(signal_strength="WEAK"), None)
        with_sector = build_opportunity(_signal(signal_strength="WEAK"), _cross_ref())
        assert with_sector["opportunity_type"] == "CONFLUENCE"
        tiers = ["NO_TRADE", "WATCH", "SPECULATIVE", "MODERATE", "STRONG", "PRIME"]
        assert tiers.index(with_sector["tier"]) > tiers.index(no_sector["tier"])

    def test_short_confluence_mirrors_long_confluence(self):
        long_opp = build_opportunity(_signal(direction="LONG", signal_strength="WEAK"),
                                     _cross_ref(sector_stage="EARLY_MOMENTUM", trade_context="LONG_CONTEXT"))
        short_opp = build_opportunity(_signal(direction="SHORT", signal_strength="WEAK"),
                                      _cross_ref(sector_stage="WEAKENING", trade_context="SHORT_CONTEXT"))
        assert long_opp["opportunity_type"] == short_opp["opportunity_type"] == "CONFLUENCE"
        assert long_opp["tier"] == short_opp["tier"]

    def test_unaligned_sector_data_stays_event_driven(self):
        """Sector data exists but doesn't clearly support this direction —
        must not be silently treated as confluence."""
        opp = build_opportunity(_signal(direction="LONG"),
                                _cross_ref(trade_context="NOT_APPLICABLE_OR_UNRELATED"))
        assert opp["opportunity_type"] == "EVENT_DRIVEN"


class TestContradictionDowngrade:
    def test_conflicts_downgrade_tier_not_eliminate(self):
        clean = build_opportunity(_signal(signal_strength="STRONG"), _cross_ref())
        conflicted = build_opportunity(_signal(signal_strength="STRONG"),
                                       _cross_ref(conflicts=["sector disagrees"]))
        tiers = ["NO_TRADE", "WATCH", "SPECULATIVE", "MODERATE", "STRONG", "PRIME"]
        assert tiers.index(conflicted["tier"]) < tiers.index(clean["tier"])
        assert conflicted["tier"] != "NO_TRADE"  # downgraded, not eliminated

    def test_conflicts_appear_in_evidence_against(self):
        opp = build_opportunity(_signal(), _cross_ref(conflicts=["sector disagrees with stock"]))
        assert "sector disagrees with stock" in opp["evidence_against_json"]

    def test_conflicts_are_never_dropped(self):
        opp = build_opportunity(_signal(), _cross_ref(conflicts=["c1", "c2"]))
        assert opp["conflicts_json"] == ["c1", "c2"]


class TestMaturity:
    def test_early_sector_stage_is_early_maturity(self):
        opp = build_opportunity(_signal(), _cross_ref(sector_stage="EMERGING"))
        assert opp["maturity"] == "EARLY"

    def test_developing_sector_stage_is_early_maturity(self):
        """Phase 6's 'DEVELOPING' sector STATE maps to Phase 8's 'EARLY'
        maturity LABEL — deliberately non-colliding names (see opportunity.py)."""
        opp = build_opportunity(_signal(), _cross_ref(sector_stage="DEVELOPING"))
        assert opp["maturity"] == "EARLY"

    def test_early_momentum_sector_stage_is_mid_stage_maturity(self):
        opp = build_opportunity(_signal(), _cross_ref(sector_stage="EARLY_MOMENTUM"))
        assert opp["maturity"] == "MID_STAGE"

    def test_confirmed_strong_sector_is_mature(self):
        opp = build_opportunity(_signal(), _cross_ref(sector_stage="CONFIRMED_STRONG",
                                                       trade_context="MATURE_CAUTION"))
        assert opp["maturity"] == "MATURE"

    def test_mature_confluence_gets_downgraded_not_boosted_twice(self):
        """A mature/extended confluence opportunity must not rank higher
        than a fresh, early one — maturity applies a caution downgrade."""
        early = build_opportunity(_signal(signal_strength="STRONG"),
                                  _cross_ref(sector_stage="EARLY_MOMENTUM", trade_context="LONG_CONTEXT"))
        mature = build_opportunity(_signal(signal_strength="STRONG"),
                                   _cross_ref(sector_stage="CONFIRMED_STRONG", trade_context="LONG_CONTEXT"))
        tiers = ["NO_TRADE", "WATCH", "SPECULATIVE", "MODERATE", "STRONG", "PRIME"]
        assert tiers.index(mature["tier"]) <= tiers.index(early["tier"])

    def test_mature_downgrades_position_candidate_to_swing(self):
        opp = build_opportunity(_signal(time_horizon="POSITION_CANDIDATE"),
                                _cross_ref(sector_stage="MATURE", trade_context="MATURE_CAUTION"))
        assert opp["time_horizon"] == "SWING"

    def test_no_cross_ref_and_confirmed_technical_is_mature(self):
        opp = build_opportunity(_signal(technical_confirmation="CONFIRMED"), None)
        assert opp["maturity"] == "MATURE"

    def test_no_cross_ref_and_unconfirmed_technical_is_unknown_maturity(self):
        opp = build_opportunity(_signal(technical_confirmation="UNKNOWN"), None)
        assert opp["maturity"] == "UNKNOWN"


class TestMissingEvidence:
    def test_missing_cross_ref_still_produces_full_record(self):
        opp = build_opportunity(_signal(), None)
        assert opp["sector_or_theme"] is None
        assert opp["has_sector_data"] is False
        assert opp["tier"] is not None

    def test_low_data_quality_is_preserved_separately_from_tier(self):
        """Data quality must never be silently folded into the tier."""
        opp = build_opportunity(_signal(signal_strength="STRONG", data_quality="LOW"), None)
        assert opp["tier"] == "STRONG"  # tier reflects evidence STRENGTH
        assert opp["data_quality"] == "LOW"  # data quality reflects evidence COMPLETENESS, kept separate

    def test_unknown_reaction_does_not_become_positive_or_negative(self):
        opp = build_opportunity(_signal(market_reaction_state="UNKNOWN"), None)
        assert opp["market_reaction_state"] == "UNKNOWN"


class TestNoDoubleCounting:
    def test_stock_evidence_and_sector_evidence_stay_separate(self):
        opp = build_opportunity(_signal(evidence_for=["stock: order win"]),
                                _cross_ref())
        assert "stock: order win" in opp["evidence_for_json"]
        assert "sector evidence" in opp["evidence_for_json"]
        # each appears exactly once — not duplicated across fields
        assert opp["evidence_for_json"].count("stock: order win") == 1
        assert opp["evidence_for_json"].count("sector evidence") == 1

    def test_predictive_status_and_tier_basis_always_labeled(self):
        for cross_ref in (None, _cross_ref()):
            opp = build_opportunity(_signal(), cross_ref)
            assert opp["predictive_status"] == "EXPLORATORY"
            assert opp["tier_basis"] == "HEURISTIC"
