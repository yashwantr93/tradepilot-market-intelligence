"""
Sector/Theme -> Stock cross-reference runner — Phase 7 (event_intelligence/).

Combines Phase 6's latest sector/theme state with Phase 5's per-symbol
trade signals — a pure combination of already-computed data, no new price/
event computation. Run AFTER both run_sector_theme.py and
run_trade_signals.py.

Produces trade_context labels (LONG_CONTEXT / SHORT_CONTEXT / MATURE_CAUTION
/ WATCH_CANDIDATE / CONTRADICTED / NO_CATALYST / INSUFFICIENT_EVIDENCE) —
categorical, explainable, NOT a score or a final ranking.

Usage:  python run_sector_stock_crossref.py
"""

from __future__ import annotations

from core.db.engine import init_db
from core.utils.logging import get_logger
from event_intelligence.cross_reference_pipeline import run_cross_reference

log = get_logger("run_sector_stock_crossref")


def main() -> None:
    log.info("=== Sector/Theme -> Stock cross-reference run ===")
    init_db()

    report = run_cross_reference()

    print("\n".join([
        "",
        f"As-of date                    : {report.get('as_of_date')}",
        f"Rows processed                : {report.get('processed')}",
        f"Distinct participating symbols : {report.get('distinct_symbols')}",
        f"Symbols with a company event   : {report.get('symbols_with_company_event')}",
        f"Conflicts found                : {report.get('conflicts_found')}",
        f"By trade_context               : {report.get('by_trade_context')}",
    ]))


if __name__ == "__main__":
    main()
