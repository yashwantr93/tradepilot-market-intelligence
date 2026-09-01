"""
Technical Confirmation bridge tests — Phase 5. Monkeypatches the V2
contract calls (`early_momentum`/`bearish_opportunity`) rather than hitting
the real V2 database — tests the CONFIRMED/PARTIAL/NOT_CONFIRMED/UNKNOWN
translation logic in isolation.
"""

from __future__ import annotations

import pandas as pd
import pytest

from event_intelligence import technical_confirmation as tc


def _history(category: str) -> pd.DataFrame:
    return pd.DataFrame([
        {"trade_date": "2026-08-20", "category": "Watch Closely"},
        {"trade_date": "2026-08-21", "category": category},
    ])


class TestLongSide:
    def test_emerging_leader_is_confirmed(self, monkeypatch):
        monkeypatch.setattr(tc.early_momentum, "get_symbol_history",
                            lambda symbol: _history("Emerging Leader"))
        result = tc.get_technical_confirmation("TESTCO", "long")
        assert result["status"] == "CONFIRMED"

    def test_building_momentum_is_partial(self, monkeypatch):
        monkeypatch.setattr(tc.early_momentum, "get_symbol_history",
                            lambda symbol: _history("Building Momentum"))
        result = tc.get_technical_confirmation("TESTCO", "long")
        assert result["status"] == "PARTIAL"

    def test_not_qualified_is_not_confirmed(self, monkeypatch):
        monkeypatch.setattr(tc.early_momentum, "get_symbol_history",
                            lambda symbol: _history("Not Qualified"))
        result = tc.get_technical_confirmation("TESTCO", "long")
        assert result["status"] == "NOT_CONFIRMED"

    def test_no_history_is_unknown_not_guessed(self, monkeypatch):
        monkeypatch.setattr(tc.early_momentum, "get_symbol_history",
                            lambda symbol: pd.DataFrame())
        result = tc.get_technical_confirmation("TESTCO", "long")
        assert result["status"] == "UNKNOWN"
        assert result["category"] is None

    def test_uses_the_latest_row_not_an_arbitrary_one(self, monkeypatch):
        """History has an OLDER 'Watch Closely' row and a NEWER 'Emerging
        Leader' row — must use the latest, not the first/any row."""
        monkeypatch.setattr(tc.early_momentum, "get_symbol_history",
                            lambda symbol: _history("Emerging Leader"))
        result = tc.get_technical_confirmation("TESTCO", "long")
        assert result["category"] == "Emerging Leader"


class TestShortSide:
    def test_high_conviction_bearish_is_confirmed(self, monkeypatch):
        monkeypatch.setattr(tc.bearish_opportunity, "get_symbol_history",
                            lambda symbol: _history("High Conviction Bearish"))
        result = tc.get_technical_confirmation("TESTCO", "short")
        assert result["status"] == "CONFIRMED"

    def test_building_weakness_is_partial(self, monkeypatch):
        monkeypatch.setattr(tc.bearish_opportunity, "get_symbol_history",
                            lambda symbol: _history("Building Weakness"))
        result = tc.get_technical_confirmation("TESTCO", "short")
        assert result["status"] == "PARTIAL"


class TestInvalidSide:
    def test_invalid_side_raises(self):
        with pytest.raises(ValueError):
            tc.get_technical_confirmation("TESTCO", "sideways")
