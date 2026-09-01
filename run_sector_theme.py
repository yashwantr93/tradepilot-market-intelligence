"""
Sector/Theme Emergence runner — Phase 6 (event_intelligence/).

Builds an append-only daily history of sector/theme breadth, relative
strength, event density, and lifecycle state for the GICS-derived sector
universe (symbol_master.sector) plus the two curated theme baskets
(Defence, PSU) — see event_intelligence/sector_universe.py for why this is
a DIFFERENT, wider-breadth universe than V1's existing 12-sector
SECTORS/sector_rotation, which this script does not touch.

Deliberately a standalone top-level script (like run_market_reaction.py
and run_trade_signals.py before it) — the one place allowed to import both
`core.db` and `intelligence_v2`.

NO scoring · NO ML · state_basis is always HEURISTIC.

Usage:  python run_sector_theme.py
"""

from __future__ import annotations

from core.db.engine import init_db
from core.utils.logging import get_logger
from event_intelligence.sector_pipeline import run_sector_theme

log = get_logger("run_sector_theme")


def main() -> None:
    log.info("=== Sector/Theme Emergence run ===")
    init_db()

    report = run_sector_theme(lookback_sessions=90)

    print("\n".join([
        "",
        f"Sectors/themes processed : {report.get('sectors')}",
        f"Trading sessions covered : {report.get('trade_dates_covered')}",
        f"Rows stored              : {report.get('stored')}",
        "",
        "NOTE: state_basis is HEURISTIC for every row — see docs/PRODUCT_VISION.md",
        "and the Phase 6 report before treating any state as predictive.",
    ]))


if __name__ == "__main__":
    main()
