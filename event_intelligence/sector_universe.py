"""
Sector/Theme universe definition — Phase 6.

CRITICAL DISCOVERY made during this phase's mandatory "inspect before
implementing" pass: the codebase has TWO INCOMPATIBLE sector taxonomies,
and the existing one is unusable for breadth-based emergence detection:

  1. `core.config.SECTORS` (V1) — 12 curated Indian-market sectors (Banking,
     IT, Auto, Pharma, FMCG, Capital Goods, Defence, Realty, PSU, Energy,
     Metals, Financial Services), each a fixed 5-stock basket. Used by V1's
     `core/sector_rotation/engine.py` and V2's Sector Intelligence engine.
     With only 5 constituents per sector, genuine breadth (% participating)
     cannot be measured meaningfully — n=5 makes every breadth percentage a
     multiple of 20%, and one stock's move swings it by a fifth.

  2. `symbol_master.sector` (V1, populated from yfinance, previously
     unused by any sector-level engine) — 11 real GICS-style categories
     (Technology, Industrials, Consumer Cyclical, Financial Services,
     Healthcare, Basic Materials, Consumer Defensive, Real Estate,
     Communication Services, Energy, Utilities) plus an "Unknown" bucket
     (132 symbols). Measured coverage: 9 to 68 constituents per real
     sector, with price_history coverage at or near 100% for every named
     sector (Consumer Cyclical 68/68, Industrials 61/61, Technology 38/38,
     etc. — see the Phase 6 report's EXISTING DATA SOURCES section for the
     full table).

DECISION (reported, not silently made): this phase's breadth/participation
engine uses taxonomy #2 (`symbol_master.sector`, excluding "Unknown") as
its primary universe — it is the only one with enough real constituents to
measure breadth honestly. Taxonomy #1 is NOT modified, removed, or
replaced — V1's `sector_rotation` and V2's Sector Intelligence continue to
serve their existing, different purpose (a curated institutional-watchlist
candidate pool) completely unchanged.

THEME support: `core.config.SECTORS` additionally defines "Defence" and
"PSU" — genuinely thematic groupings with no GICS equivalent (GICS has no
"Defence" or "PSU" category; those symbols are scattered across
Industrials/Utilities/Energy/etc.). These two are carried forward as
explicit THEME_BASKET entries alongside the 11 GICS SECTOR entries, since
real, already-curated membership exists for them. Every other example theme
in the task brief (Railways, Manufacturing, Capex, Renewable Energy, Power,
AI, Electronics, Infrastructure, Export cycle, China+1, Government
spending) has ZERO membership data anywhere in this codebase — NOT
implemented, not fabricated. See the Phase 6 report's THEME SUPPORT section.
"""

from __future__ import annotations

from core.config import SECTORS as V1_SECTOR_BASKETS

# Curated V1 baskets that are genuinely thematic (no GICS equivalent),
# carried forward as THEME_BASKET entries. Deliberately NOT the other 10
# V1 SECTORS entries — those overlap (imperfectly) with GICS categories
# already covered by the broader taxonomy, and duplicating them would
# create two "IT"-ish or "Banking"-ish groups with different membership
# under confusingly similar names.
THEME_BASKETS: dict[str, list[str]] = {
    "Defence": list(V1_SECTOR_BASKETS["Defence"]["basket"]),
    "PSU": list(V1_SECTOR_BASKETS["PSU"]["basket"]),
}

MIN_CONSTITUENTS = 8  # below this, breadth percentages are too coarse to be meaningful (noise control)


def get_universe(sector_map: dict[str, list[str]]) -> dict[str, list[str]]:
    """`sector_map` — {sector_name: [symbols]} from
    repo.get_symbol_sector_map(), i.e. symbol_master.sector grouped.
    Returns the combined GICS-sector + THEME_BASKET universe, excluding
    "Unknown" and any group below MIN_CONSTITUENTS."""
    universe = {}
    for sector, symbols in sector_map.items():
        if sector == "Unknown" or sector is None:
            continue
        if len(symbols) < MIN_CONSTITUENTS:
            continue
        universe[sector] = sorted(set(symbols))
    for theme, symbols in THEME_BASKETS.items():
        universe[theme] = sorted(set(symbols))  # themes exempt from MIN_CONSTITUENTS — curated, not sampled
    return universe
