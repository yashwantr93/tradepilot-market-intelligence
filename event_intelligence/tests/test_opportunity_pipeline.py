"""
Opportunity Intelligence pipeline wiring tests — Phase 8. Hermetic
monkeypatch pattern matching Phase 5/6/7 — verifies orchestration (the two
input streams, JSON round-tripping), not the combination logic itself
(covered by test_opportunity.py).
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from event_intelligence import opportunity_pipeline as op


def _signal_row(symbol="ABC", direction="LONG", corporate_action_id=1,
                no_trade_reason=None, event_type="Large Order Win"):
    return {
        "symbol": symbol, "corporate_action_id": corporate_action_id, "event_type": event_type,
        "announcement_date": dt.date(2026, 8, 1), "direction": direction,
        "no_trade_reason": no_trade_reason, "signal_strength": "STRONG",
        "materiality_tier": "HIGH", "market_reaction_state": "STRONG POSITIVE",
        "continuation_state": "CONTINUATION", "technical_confirmation": "CONFIRMED",
        "time_horizon": "SWING", "data_quality": "HIGH", "risk": "risk text",
        "invalidation": "invalidation text", "evidence_for_json": json.dumps(["e1"]),
        "evidence_against_json": json.dumps([]),
    }


class TestEmptyInput:
    def test_empty_signals_reports_error(self, monkeypatch):
        monkeypatch.setattr(op.repo, "get_event_trade_signals", lambda: pd.DataFrame())
        monkeypatch.setattr(op.repo, "get_latest_sector_stock_cross_reference", lambda: pd.DataFrame())
        report = op.run_opportunity_intelligence()
        assert report["processed"] == 0
        assert "error" in report


class TestMultiSnapshotRegression:
    """Phase 9 regression: a live refresh produced a SECOND real
    sector_stock_cross_reference snapshot and exposed that this pipeline
    must call the LATEST-only accessor, never the unfiltered one — see the
    Phase 9 report's DISCOVERED ISSUES."""

    def test_pipeline_calls_the_latest_only_accessor_not_the_unfiltered_one(self, monkeypatch):
        calls = []
        monkeypatch.setattr(op.repo, "get_event_trade_signals", lambda: pd.DataFrame())
        monkeypatch.setattr(op.repo, "get_latest_sector_stock_cross_reference",
                            lambda: calls.append("latest") or pd.DataFrame())
        # If the pipeline ever regresses to calling the unfiltered accessor,
        # this attribute simply won't exist on the mock target used above,
        # and the real (unpatched) unfiltered call would be made instead —
        # asserting the tracked call list is the direct signal.
        op.run_opportunity_intelligence()
        assert calls == ["latest"]


class TestStreamOne:
    def test_long_and_short_signals_both_produce_opportunities(self, monkeypatch):
        df = pd.DataFrame([_signal_row("A", "LONG"), _signal_row("B", "SHORT", corporate_action_id=2)])
        monkeypatch.setattr(op.repo, "get_event_trade_signals", lambda: df)
        monkeypatch.setattr(op.repo, "get_latest_sector_stock_cross_reference", lambda: pd.DataFrame())
        captured = {}
        monkeypatch.setattr(op.repo, "upsert_opportunity",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        report = op.run_opportunity_intelligence()
        assert report["processed"] == 2
        directions = {r["direction"] for r in captured["rows"]}
        assert directions == {"LONG", "SHORT"}

    def test_no_trade_signals_are_excluded_from_stream_one(self, monkeypatch):
        df = pd.DataFrame([_signal_row("A", "NO_TRADE", no_trade_reason="INSUFFICIENT_EVIDENCE")])
        monkeypatch.setattr(op.repo, "get_event_trade_signals", lambda: df)
        monkeypatch.setattr(op.repo, "get_latest_sector_stock_cross_reference", lambda: pd.DataFrame())
        monkeypatch.setattr(op.repo, "upsert_opportunity", lambda rows: len(rows))

        report = op.run_opportunity_intelligence()
        # No stream-1 opportunity from a NO_TRADE row, and no cross-ref data
        # for stream 2 either -> zero total.
        assert report["processed"] == 0


class TestStreamTwoEmergingTheme:
    def _cross_ref_df(self, symbol="A", trade_context="WATCH_CANDIDATE"):
        return pd.DataFrame([{
            "as_of_date": dt.date(2026, 8, 21), "symbol": symbol, "sector_or_theme": "Industrials",
            "sector_stage": "EARLY_MOMENTUM", "trade_context": trade_context,
            "participation_role": "early_participant",
            "conflicts_json": json.dumps([]), "sector_evidence_json": json.dumps(["sector evidence"]),
        }])

    def test_watch_candidate_with_eligible_no_trade_reason_becomes_emerging_theme(self, monkeypatch):
        signals = pd.DataFrame([_signal_row("A", "NO_TRADE", no_trade_reason="INSUFFICIENT_EVIDENCE")])
        monkeypatch.setattr(op.repo, "get_event_trade_signals", lambda: signals)
        monkeypatch.setattr(op.repo, "get_latest_sector_stock_cross_reference", lambda: self._cross_ref_df())
        captured = {}
        monkeypatch.setattr(op.repo, "upsert_opportunity",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        report = op.run_opportunity_intelligence()
        assert report["processed"] == 1
        assert captured["rows"][0]["opportunity_type"] == "EMERGING_THEME"
        assert captured["rows"][0]["tier"] == "SPECULATIVE"

    def test_neutral_ambiguous_no_trade_reason_is_excluded_from_emerging_theme(self, monkeypatch):
        """The real bug this phase caught (see DISCOVERED ISSUES): a
        Neutral-direction event must not become an actionable EMERGING_THEME
        opportunity merely because Phase 7 flagged WATCH_CANDIDATE."""
        signals = pd.DataFrame([_signal_row("A", "NO_TRADE",
                                            no_trade_reason="NEUTRAL_OR_AMBIGUOUS_EVENT")])
        monkeypatch.setattr(op.repo, "get_event_trade_signals", lambda: signals)
        monkeypatch.setattr(op.repo, "get_latest_sector_stock_cross_reference", lambda: self._cross_ref_df())
        monkeypatch.setattr(op.repo, "upsert_opportunity", lambda rows: len(rows))

        report = op.run_opportunity_intelligence()
        assert report["processed"] == 0

    def test_non_watch_candidate_trade_context_is_excluded_from_emerging_theme(self, monkeypatch):
        signals = pd.DataFrame([_signal_row("A", "NO_TRADE", no_trade_reason="INSUFFICIENT_EVIDENCE")])
        monkeypatch.setattr(op.repo, "get_event_trade_signals", lambda: signals)
        monkeypatch.setattr(op.repo, "get_latest_sector_stock_cross_reference",
                            lambda: self._cross_ref_df(trade_context="NO_CATALYST"))
        monkeypatch.setattr(op.repo, "upsert_opportunity", lambda rows: len(rows))

        report = op.run_opportunity_intelligence()
        assert report["processed"] == 0


class TestJsonRoundTrip:
    def test_stored_rows_have_json_string_fields(self, monkeypatch):
        df = pd.DataFrame([_signal_row("A", "LONG")])
        monkeypatch.setattr(op.repo, "get_event_trade_signals", lambda: df)
        monkeypatch.setattr(op.repo, "get_latest_sector_stock_cross_reference", lambda: pd.DataFrame())
        captured = {}
        monkeypatch.setattr(op.repo, "upsert_opportunity",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        op.run_opportunity_intelligence()
        row = captured["rows"][0]
        for field in ("evidence_for_json", "evidence_against_json", "conflicts_json"):
            assert isinstance(row[field], str)
            json.loads(row[field])
