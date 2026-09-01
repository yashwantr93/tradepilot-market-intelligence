"""
Opportunity Intelligence runner — Phase 8 (event_intelligence/).

Combines Phase 5's per-event trade signals with Phase 7's sector/stock
cross-reference into explainable Opportunity records — categorical tier
(PRIME/STRONG/MODERATE/SPECULATIVE/WATCH/NO_TRADE), never a numeric score.
Pure combination of already-computed data; run AFTER run_trade_signals.py
and run_sector_stock_crossref.py.

predictive_status is always EXPLORATORY — see docs/PRODUCT_VISION.md and
the Phase 8 report before treating any tier as validated.

Usage:  python run_opportunity_intelligence.py
"""

from __future__ import annotations

from core.db.engine import init_db
from core.utils.logging import get_logger
from event_intelligence.opportunity_pipeline import run_opportunity_intelligence

log = get_logger("run_opportunity_intelligence")


def main() -> None:
    log.info("=== Opportunity Intelligence run ===")
    init_db()

    report = run_opportunity_intelligence()

    print("\n".join([
        "",
        f"As-of date        : {report.get('as_of_date')}",
        f"Opportunities      : {report.get('processed')}",
        f"By type            : {report.get('by_type')}",
        f"By tier            : {report.get('by_tier')}",
        "",
        "NOTE: tier_basis is HEURISTIC and predictive_status is EXPLORATORY",
        "for every opportunity — see docs/PRODUCT_VISION.md and the Phase 8 report.",
    ]))


if __name__ == "__main__":
    main()
