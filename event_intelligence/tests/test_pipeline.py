"""
Market Reaction pipeline wiring tests — Phase 3.

Business-logic wiring only, dependency-injected via monkeypatch (same
hermetic pattern as Phase 1.5/2's backfill/materiality pipeline tests) —
verifies incremental filtering, coverage-percentage computation, and that
every event gets a stored outcome (including UNKNOWN), without needing a
real database.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from event_intelligence import pipeline as pipeline_mod


def _action(id_, symbol, event_type="Dividend", impact_tag="Neutral",
           announcement_date=dt.date(2026, 1, 1)):
    return {"id": id_, "symbol": symbol, "announcement_date": announcement_date,
            "event_summary": "x", "event_type": event_type, "impact_tag": impact_tag,
            "priority": "Low", "dedupe_hash": "h"}


@pytest.fixture(autouse=True)
def _stub_expensive_io(monkeypatch):
    """Every test in this file stubs out real DB/price access — only the
    orchestration logic (filtering, aggregation, upsert-call shape) is
    under test here."""
    monkeypatch.setattr(pipeline_mod, "_load_benchmark", lambda: pd.Series(dtype=float))
    monkeypatch.setattr(pipeline_mod, "_load_clean_price_frame", lambda symbol: pd.DataFrame())


class TestIncrementalFiltering:
    def test_action_ids_restricts_to_requested_rows(self, monkeypatch):
        actions = [_action(1, "A"), _action(2, "B"), _action(3, "C")]
        monkeypatch.setattr(pipeline_mod.repo, "get_corporate_actions_for_backfill",
                            lambda: actions)
        captured = {}
        monkeypatch.setattr(pipeline_mod.repo, "upsert_event_market_reaction",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        report = pipeline_mod.run_market_reaction(action_ids=[2])

        assert report["processed"] == 1
        assert captured["rows"][0]["symbol"] == "B"

    def test_none_processes_every_stored_action(self, monkeypatch):
        actions = [_action(1, "A"), _action(2, "B")]
        monkeypatch.setattr(pipeline_mod.repo, "get_corporate_actions_for_backfill",
                            lambda: actions)
        monkeypatch.setattr(pipeline_mod.repo, "upsert_event_market_reaction", lambda rows: len(rows))

        report = pipeline_mod.run_market_reaction(action_ids=None)
        assert report["processed"] == 2


class TestEveryEventGetsAnOutcome:
    def test_event_with_no_price_data_still_produces_a_row(self, monkeypatch):
        """With price frame empty (stubbed), every event should still get a
        stored row with reaction_state=UNKNOWN — never silently skipped."""
        actions = [_action(1, "NOPRICE")]
        monkeypatch.setattr(pipeline_mod.repo, "get_corporate_actions_for_backfill",
                            lambda: actions)
        captured = {}
        monkeypatch.setattr(pipeline_mod.repo, "upsert_event_market_reaction",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        report = pipeline_mod.run_market_reaction()

        assert report["processed"] == 1
        assert captured["rows"][0]["reaction_state"] == "UNKNOWN"
        assert report["by_state"] == {"UNKNOWN": 1}


class TestCoverageComputation:
    def test_coverage_percentages_reflect_actual_availability(self, monkeypatch):
        actions = [_action(1, "A"), _action(2, "B")]
        monkeypatch.setattr(pipeline_mod.repo, "get_corporate_actions_for_backfill",
                            lambda: actions)
        monkeypatch.setattr(pipeline_mod.repo, "upsert_event_market_reaction", lambda rows: len(rows))

        # Both symbols have no price data (stubbed empty) -> 0% coverage everywhere.
        report = pipeline_mod.run_market_reaction()
        assert report["coverage"]["total_events"] == 2
        assert report["coverage"]["1d_pct"] == 0.0
        assert report["coverage"]["5d_pct"] == 0.0

    def test_zero_events_does_not_divide_by_zero(self, monkeypatch):
        monkeypatch.setattr(pipeline_mod.repo, "get_corporate_actions_for_backfill", lambda: [])
        monkeypatch.setattr(pipeline_mod.repo, "upsert_event_market_reaction", lambda rows: len(rows))
        report = pipeline_mod.run_market_reaction()
        assert report["coverage"]["total_events"] == 0
        assert report["coverage"]["5d_pct"] == 0.0
