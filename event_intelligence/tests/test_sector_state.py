"""
Sector/Theme state classification tests — Phase 6. Covers every state,
breadth expansion/contraction, isolated-stock false-emergence guarding,
event-density contribution, missing data, and hysteresis-based state
transitions (reusing V2's own apply_hysteresis, verified here in
combination with classify_raw).
"""

from __future__ import annotations

from intelligence_v2.processors.sector_classifier import apply_hysteresis

from event_intelligence.sector_state import (
    DIRECTION_CONTEXT,
    build_evidence,
    classify_participation,
    classify_raw,
)


def _agg(pct_above_20sma, avg_rs_1m):
    return {"pct_above_20sma": pct_above_20sma, "avg_rs_1m": avg_rs_1m,
           "measurable_count": 20, "constituent_count": 20}


class TestConfirmedStrongAndMature:
    def test_confirmed_strong_broad_and_still_accelerating(self):
        state = classify_raw(_agg(80, 5), _agg(70, 3), 0, 0)
        assert state == "CONFIRMED_STRONG"

    def test_mature_broad_but_no_longer_accelerating(self):
        """Same breadth/RS level as CONFIRMED_STRONG but NOT still
        accelerating — the core 'strong but not early' distinction."""
        state = classify_raw(_agg(80, 5), _agg(80, 5), 0, 0)
        assert state == "MATURE"


class TestEarlyStageStates:
    def test_early_momentum_moderate_breadth_both_expanding(self):
        state = classify_raw(_agg(50, 3), _agg(40, 1), 0, 0)
        assert state == "EARLY_MOMENTUM"

    def test_developing_low_breadth_but_trending_right(self):
        state = classify_raw(_agg(25, 2), _agg(15, 0), 0, 0)
        assert state == "DEVELOPING"

    def test_emerging_requires_event_density_when_breadth_flat(self):
        """RS turning up but breadth NOT yet expanding — needs a second,
        independent confirming signal (event density) to become EMERGING."""
        state_without_events = classify_raw(_agg(15, 1), _agg(15, -2), positive_event_count=0,
                                            negative_event_count=0)
        state_with_events = classify_raw(_agg(15, 1), _agg(15, -2), positive_event_count=3,
                                         negative_event_count=0)
        assert state_without_events != "EMERGING"
        assert state_with_events == "EMERGING"


class TestIsolatedStockFalseEmergence:
    def test_tiny_breadth_and_rs_tick_does_not_trigger_emergence(self):
        """A single stock's move nudging the sector average slightly must
        NOT be classified as any emergence state — both changes are below
        the noise floor and there's no event density to compensate."""
        state = classify_raw(_agg(12, 0.5), _agg(10, 0.0), 0, 0)
        assert state == "SIDEWAYS"


class TestWeakening:
    def test_weakening_declining_from_a_stronger_base(self):
        state = classify_raw(_agg(20, -5), _agg(40, 2), 0, 0)
        assert state == "WEAKENING"

    def test_weak_but_not_yet_declining_is_not_weakening(self):
        """Negative RS alone, without an active decline AND contraction,
        should not be WEAKENING — could just be a persistently weak but
        stable sector."""
        state = classify_raw(_agg(20, -2), _agg(20, -2), 0, 0)
        assert state != "WEAKENING"


class TestMissingData:
    def test_missing_breadth_is_sideways_not_fabricated(self):
        state = classify_raw({"pct_above_20sma": None, "avg_rs_1m": 3.0}, _agg(30, 1), 0, 0)
        assert state == "SIDEWAYS"

    def test_missing_prior_disables_trend_checks_gracefully(self):
        # prior={} (no data) -> breadth_change/rs_change both None -> can
        # still fall through to a state that doesn't require a trend (MATURE),
        # never crashes.
        state = classify_raw(_agg(80, 5), {}, 0, 0)
        assert state == "MATURE"


class TestDirectionContext:
    def test_all_early_and_strong_states_are_bullish_context(self):
        for state in ("CONFIRMED_STRONG", "MATURE", "EARLY_MOMENTUM", "DEVELOPING", "EMERGING"):
            assert DIRECTION_CONTEXT[state] == "BULLISH"

    def test_weakening_is_bearish_context(self):
        assert DIRECTION_CONTEXT["WEAKENING"] == "BEARISH"

    def test_sideways_is_neutral(self):
        assert DIRECTION_CONTEXT["SIDEWAYS"] == "NEUTRAL"


class TestParticipation:
    def test_leader_above_sector_average_and_above_own_sma(self):
        metrics = {"LEADER": {"rs_1m": 10.0, "rs_1w": 5.0, "above_20sma": "Y"}}
        result = classify_participation(metrics, sector_avg_rs_1m=3.0)
        assert "LEADER" in result["leaders"]

    def test_early_participant_short_term_turning_not_yet_leading(self):
        metrics = {"EARLY": {"rs_1m": 1.0, "rs_1w": 2.0, "above_20sma": "N"}}
        result = classify_participation(metrics, sector_avg_rs_1m=3.0)
        assert "EARLY" in result["early_participants"]

    def test_laggard_negative_rs(self):
        metrics = {"LAG": {"rs_1m": -5.0, "rs_1w": -3.0, "above_20sma": "N"}}
        result = classify_participation(metrics, sector_avg_rs_1m=3.0)
        assert "LAG" in result["laggards"]

    def test_missing_constituent_is_non_participant(self):
        metrics = {"MISSING": None}
        result = classify_participation(metrics, sector_avg_rs_1m=3.0)
        assert "MISSING" in result["non_participants"]

    def test_none_sector_average_returns_empty_groups_not_a_crash(self):
        result = classify_participation({"A": {"rs_1m": 1.0}}, sector_avg_rs_1m=None)
        assert result == {"leaders": [], "early_participants": [], "laggards": [], "non_participants": []}


class TestEvidenceBuilder:
    def test_evidence_for_cites_actual_breadth_and_rs_numbers(self):
        participation = {"leaders": ["A", "B", "C"], "early_participants": [], "laggards": [], "non_participants": []}
        evidence_for, evidence_against = build_evidence(
            "EARLY_MOMENTUM", _agg(50, 3), _agg(40, 1), 2, 0, participation
        )
        assert any("50%" in e for e in evidence_for)
        assert any("+3.00%" in e for e in evidence_for)

    def test_negative_events_appear_in_evidence_against(self):
        participation = {"leaders": ["A", "B", "C"], "early_participants": [], "laggards": [], "non_participants": []}
        _, evidence_against = build_evidence("SIDEWAYS", _agg(30, 0), _agg(30, 0), 0, 3, participation)
        assert any("negative material event" in e for e in evidence_against)

    def test_narrow_leadership_flagged_in_evidence_against(self):
        participation = {"leaders": ["A"], "early_participants": [], "laggards": [], "non_participants": []}
        _, evidence_against = build_evidence("EARLY_MOMENTUM", _agg(50, 3), _agg(40, 1), 0, 0, participation)
        assert any("narrow" in e.lower() for e in evidence_against)


class TestStateTransitionsWithHysteresis:
    def test_state_does_not_flip_on_a_single_days_raw_change(self):
        """Reuses V2's own apply_hysteresis (MIN_DWELL_DAYS=3) — a raw
        state must persist 3 consecutive sessions before it's confirmed."""
        # Day 1: confirmed SIDEWAYS. Day 2: raw flips to EARLY_MOMENTUM once —
        # must NOT confirm yet.
        confirmed, days = apply_hysteresis("EARLY_MOMENTUM", "SIDEWAYS", 5, ["SIDEWAYS", "SIDEWAYS"])
        assert confirmed == "SIDEWAYS"  # not yet confirmed — only 1 session of the new raw state

    def test_state_confirms_after_three_consecutive_sessions(self):
        confirmed, days = apply_hysteresis("EARLY_MOMENTUM", "SIDEWAYS", 5,
                                           ["EARLY_MOMENTUM", "EARLY_MOMENTUM"])
        assert confirmed == "EARLY_MOMENTUM"
        assert days == 1
