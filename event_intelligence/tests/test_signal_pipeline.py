"""
Trade Signal pipeline wiring tests — Phase 5. Same hermetic monkeypatch
pattern as Phase 2/3's pipeline tests — dependency-injects repo and
technical_confirmation calls, verifies orchestration (not the decision
logic itself, covered by test_signal_engine.py).
"""

from __future__ import annotations

import datetime as dt

import pytest

from event_intelligence import signal_pipeline as sp


def _event(id_, symbol="TESTCO", impact_tag="Bullish"):
    return {"id": id_, "symbol": symbol, "event_type": "Large Order Win",
            "impact_tag": impact_tag, "announcement_date": dt.date(2026, 1, 1),
            "materiality_tier": "HIGH", "reaction_state": "STRONG POSITIVE",
            "continuation_state": "CONTINUATION", "event_alignment": "ALIGNED",
            "relative_return_5d": 6.0, "volume_ratio_day0": 2.0}


@pytest.fixture(autouse=True)
def _stub_expectation(monkeypatch):
    monkeypatch.setattr(sp.repo, "get_nearby_expectation_surprise", lambda symbol, before: None)


class TestSideSelection:
    def test_bullish_event_fetches_long_side_technical(self, monkeypatch):
        monkeypatch.setattr(sp.repo, "get_events_for_signal_engine",
                            lambda ids=None: [_event(1, impact_tag="Bullish")])
        monkeypatch.setattr(sp.repo, "upsert_event_trade_signal", lambda rows: len(rows))
        calls = []
        monkeypatch.setattr(sp, "get_technical_confirmation",
                            lambda symbol, side: calls.append(side) or
                            {"status": "CONFIRMED", "category": "Emerging Leader", "reason": "x"})

        sp.run_trade_signals()
        assert calls == ["long"]

    def test_bearish_event_fetches_short_side_technical(self, monkeypatch):
        monkeypatch.setattr(sp.repo, "get_events_for_signal_engine",
                            lambda ids=None: [_event(1, impact_tag="Bearish")])
        monkeypatch.setattr(sp.repo, "upsert_event_trade_signal", lambda rows: len(rows))
        calls = []
        monkeypatch.setattr(sp, "get_technical_confirmation",
                            lambda symbol, side: calls.append(side) or
                            {"status": "CONFIRMED", "category": "High Conviction Bearish", "reason": "x"})

        sp.run_trade_signals()
        assert calls == ["short"]

    def test_neutral_event_never_calls_technical_confirmation(self, monkeypatch):
        """Avoids wasted V2 lookups for events with no directional thesis."""
        monkeypatch.setattr(sp.repo, "get_events_for_signal_engine",
                            lambda ids=None: [_event(1, impact_tag="Neutral")])
        monkeypatch.setattr(sp.repo, "upsert_event_trade_signal", lambda rows: len(rows))
        calls = []
        monkeypatch.setattr(sp, "get_technical_confirmation",
                            lambda symbol, side: calls.append(side) or
                            {"status": "CONFIRMED", "category": "x", "reason": "x"})

        sp.run_trade_signals()
        assert calls == []


class TestIncrementalFiltering:
    def test_action_ids_restricts_scope(self, monkeypatch):
        seen_ids = []
        def fake_get(ids=None):
            seen_ids.append(ids)
            return []
        monkeypatch.setattr(sp.repo, "get_events_for_signal_engine", fake_get)
        monkeypatch.setattr(sp.repo, "upsert_event_trade_signal", lambda rows: len(rows))
        sp.run_trade_signals(action_ids=[5, 6])
        assert seen_ids == [[5, 6]]


class TestReportAggregation:
    def test_by_direction_and_strength_counts(self, monkeypatch):
        monkeypatch.setattr(sp.repo, "get_events_for_signal_engine",
                            lambda ids=None: [_event(1, "A", "Bullish"), _event(2, "B", "Neutral")])
        monkeypatch.setattr(sp.repo, "upsert_event_trade_signal", lambda rows: len(rows))
        monkeypatch.setattr(sp, "get_technical_confirmation",
                            lambda symbol, side: {"status": "CONFIRMED",
                                                  "category": "Emerging Leader", "reason": "x"})

        report = sp.run_trade_signals()
        assert report["processed"] == 2
        assert report["by_direction"].get("LONG", 0) + report["by_direction"].get("NO_TRADE", 0) == 2

    def test_json_evidence_fields_are_serialized_strings(self, monkeypatch):
        monkeypatch.setattr(sp.repo, "get_events_for_signal_engine",
                            lambda ids=None: [_event(1)])
        captured = {}
        monkeypatch.setattr(sp.repo, "upsert_event_trade_signal",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))
        monkeypatch.setattr(sp, "get_technical_confirmation",
                            lambda symbol, side: {"status": "CONFIRMED",
                                                  "category": "Emerging Leader", "reason": "x"})

        sp.run_trade_signals()
        import json
        row = captured["rows"][0]
        assert isinstance(row["evidence_for_json"], str)
        parsed = json.loads(row["evidence_for_json"])
        assert isinstance(parsed, list)
