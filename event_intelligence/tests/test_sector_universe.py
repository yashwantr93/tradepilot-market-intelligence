"""Sector universe tests — Phase 6."""

from __future__ import annotations

from event_intelligence.sector_universe import MIN_CONSTITUENTS, THEME_BASKETS, get_universe


class TestUniverseConstruction:
    def test_unknown_sector_is_excluded(self):
        sector_map = {"Unknown": ["A"] * 20, "Technology": ["B"] * 20}
        universe = get_universe(sector_map)
        assert "Unknown" not in universe
        assert "Technology" in universe

    def test_insufficient_constituents_excluded(self):
        sector_map = {"TinySector": ["A", "B", "C"]}  # below MIN_CONSTITUENTS
        universe = get_universe(sector_map)
        assert "TinySector" not in universe

    def test_sufficient_constituents_included(self):
        sector_map = {"RealSector": [f"S{i}" for i in range(MIN_CONSTITUENTS)]}
        universe = get_universe(sector_map)
        assert "RealSector" in universe
        assert len(universe["RealSector"]) == MIN_CONSTITUENTS

    def test_theme_baskets_always_included_regardless_of_size(self):
        universe = get_universe({})
        assert "Defence" in universe
        assert "PSU" in universe
        assert len(universe["Defence"]) < MIN_CONSTITUENTS  # themes are exempt

    def test_theme_baskets_are_real_curated_symbols_not_fabricated(self):
        """These must trace to the existing, already-curated V1 SECTORS
        dict — not invented for this phase."""
        assert set(THEME_BASKETS["Defence"]) == {"HAL", "BEL", "BDL", "MAZDOCK", "COCHINSHIP"}
        assert set(THEME_BASKETS["PSU"]) == {"ONGC", "COALINDIA", "NTPC", "POWERGRID", "GAIL"}
