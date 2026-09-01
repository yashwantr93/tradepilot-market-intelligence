"""
Cross-reference pipeline wiring tests — Phase 7. Hermetic monkeypatch
pattern matching Phase 3/5/6 — verifies orchestration (role extraction,
recency filtering, missing sector membership), not the combination logic
itself (covered by test_cross_reference.py).
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from event_intelligence import cross_reference_pipeline as crp


def _latest_sector_df():
    return pd.DataFrame([{
        "as_of_date": dt.date(2026, 8, 21), "sector_or_theme": "Technology",
        "confirmed_state": "EARLY_MOMENTUM", "direction_context": "BULLISH",
        "leaders_json": json.dumps(["LEAD1"]),
        "early_participants_json": json.dumps(["EARLY1"]),
        "laggards_json": json.dumps(["LAG1"]),
        "non_participants_json": json.dumps(["NON1"]),
    }])


class TestNoSectorData:
    def test_empty_sector_state_reports_error_not_a_crash(self, monkeypatch):
        monkeypatch.setattr(crp.repo, "get_latest_sector_theme_state", lambda: pd.DataFrame())
        report = crp.run_cross_reference()
        assert report["processed"] == 0
        assert "error" in report


class TestRoleExtraction:
    def test_every_participation_role_is_processed(self, monkeypatch):
        monkeypatch.setattr(crp.repo, "get_latest_sector_theme_state", _latest_sector_df)
        monkeypatch.setattr(crp.repo, "get_latest_event_signal_per_symbol", lambda symbols, since: {})
        captured = {}
        monkeypatch.setattr(crp.repo, "upsert_sector_stock_cross_reference",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        report = crp.run_cross_reference()

        symbols = {r["symbol"] for r in captured["rows"]}
        assert symbols == {"LEAD1", "EARLY1", "LAG1", "NON1"}
        roles = {r["symbol"]: r["participation_role"] for r in captured["rows"]}
        assert roles["LEAD1"] == "leader"
        assert roles["EARLY1"] == "early_participant"
        assert roles["LAG1"] == "laggard"
        assert roles["NON1"] == "non_participant"

    def test_all_symbols_without_events_are_no_catalyst(self, monkeypatch):
        monkeypatch.setattr(crp.repo, "get_latest_sector_theme_state", _latest_sector_df)
        monkeypatch.setattr(crp.repo, "get_latest_event_signal_per_symbol", lambda symbols, since: {})
        monkeypatch.setattr(crp.repo, "upsert_sector_stock_cross_reference", lambda rows: len(rows))

        report = crp.run_cross_reference()
        assert report["by_trade_context"] == {"NO_CATALYST": 4}
        assert report["symbols_with_company_event"] == 0


class TestRecencyWindow:
    def test_since_date_is_computed_from_recency_days(self, monkeypatch):
        monkeypatch.setattr(crp.repo, "get_latest_sector_theme_state", _latest_sector_df)
        captured_since = {}
        def fake_signal_lookup(symbols, since):
            captured_since["since"] = since
            return {}
        monkeypatch.setattr(crp.repo, "get_latest_event_signal_per_symbol", fake_signal_lookup)
        monkeypatch.setattr(crp.repo, "upsert_sector_stock_cross_reference", lambda rows: len(rows))

        crp.run_cross_reference(recency_days=30)
        assert captured_since["since"] == dt.date(2026, 8, 21) - dt.timedelta(days=30)


class TestJsonSerialization:
    def test_list_fields_are_serialized_to_json_strings_for_storage(self, monkeypatch):
        monkeypatch.setattr(crp.repo, "get_latest_sector_theme_state", _latest_sector_df)
        monkeypatch.setattr(crp.repo, "get_latest_event_signal_per_symbol", lambda symbols, since: {})
        captured = {}
        monkeypatch.setattr(crp.repo, "upsert_sector_stock_cross_reference",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        crp.run_cross_reference()
        row = captured["rows"][0]
        for field in ("sector_evidence_json", "stock_evidence_json", "evidence_for_json",
                     "evidence_against_json", "conflicts_json"):
            assert isinstance(row[field], str)
            json.loads(row[field])  # must not raise
