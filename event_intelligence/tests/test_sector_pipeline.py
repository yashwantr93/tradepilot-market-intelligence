"""
Sector/Theme pipeline wiring tests — Phase 6. Hermetic monkeypatch pattern
matching Phase 3/5's pipeline tests — verifies orchestration (universe
construction, stale/missing-data handling), not the classification math
itself (covered by test_sector_state.py/test_sector_metrics.py).
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from event_intelligence import sector_pipeline as spl


@pytest.fixture(autouse=True)
def _stub_repo(monkeypatch):
    monkeypatch.setattr(spl.repo, "get_symbol_sector_map",
                        lambda: {"Technology": [f"TECH{i}" for i in range(10)]})
    monkeypatch.setattr(spl.repo, "get_corporate_actions_for_backfill", lambda: [])
    monkeypatch.setattr(spl.repo, "upsert_sector_theme_state", lambda rows: len(rows))


class TestEmptyOrStaleData:
    def test_empty_benchmark_reports_error_not_a_crash(self, monkeypatch):
        monkeypatch.setattr(spl, "_load_benchmark", lambda: pd.Series(dtype=float))
        monkeypatch.setattr(spl, "_load_clean_price_frame", lambda symbol: pd.DataFrame())
        report = spl.run_sector_theme(lookback_sessions=90)
        assert report["processed"] == 0
        assert "error" in report

    def test_missing_constituent_price_data_does_not_crash(self, monkeypatch):
        dates = pd.bdate_range("2026-01-05", periods=40).date.tolist()
        bench = pd.Series([20000.0] * 40, index=dates)
        monkeypatch.setattr(spl, "_load_benchmark", lambda: bench)
        monkeypatch.setattr(spl, "_load_clean_price_frame", lambda symbol: pd.DataFrame())
        report = spl.run_sector_theme(lookback_sessions=40)
        assert report["processed"] > 0  # still produces rows — every field UNKNOWN/None, not a crash


class TestUniverseIsRespected:
    def test_only_symbol_master_sectors_and_theme_baskets_are_processed(self, monkeypatch):
        dates = pd.bdate_range("2026-01-05", periods=40).date.tolist()
        bench = pd.Series([20000.0] * 40, index=dates)
        monkeypatch.setattr(spl, "_load_benchmark", lambda: bench)

        def fake_frame(symbol):
            return pd.DataFrame({"close": [100.0] * 40, "volume": [1_000_000] * 40}, index=dates)
        monkeypatch.setattr(spl, "_load_clean_price_frame", fake_frame)

        captured = {}
        monkeypatch.setattr(spl.repo, "upsert_sector_theme_state",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        spl.run_sector_theme(lookback_sessions=5)
        names = {r["sector_or_theme"] for r in captured["rows"]}
        assert "Technology" in names  # from the stubbed sector map
        assert "Defence" in names     # curated theme, always present
        assert "PSU" in names


class TestOutputShape:
    def test_every_row_has_required_fields(self, monkeypatch):
        dates = pd.bdate_range("2026-01-05", periods=40).date.tolist()
        bench = pd.Series([20000.0 + i for i in range(40)], index=dates)
        monkeypatch.setattr(spl, "_load_benchmark", lambda: bench)

        def fake_frame(symbol):
            return pd.DataFrame({"close": [100.0 + i * 0.1 for i in range(40)],
                                "volume": [1_000_000] * 40}, index=dates)
        monkeypatch.setattr(spl, "_load_clean_price_frame", fake_frame)

        captured = {}
        monkeypatch.setattr(spl.repo, "upsert_sector_theme_state",
                            lambda rows: captured.setdefault("rows", rows) and len(rows))

        spl.run_sector_theme(lookback_sessions=5)
        row = captured["rows"][0]
        for field in ("confirmed_state", "raw_state", "direction_context", "data_quality",
                     "leaders_json", "evidence_for_json", "state_basis"):
            assert field in row
        assert row["state_basis"] == "HEURISTIC"
