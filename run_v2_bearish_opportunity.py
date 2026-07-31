"""
Bearish Opportunity Engine (V2 Phase 4) runner.

Scans V1's existing stock universe (price_history) via the same shared
relative-strength machinery Phase 3 uses, joins Phase 1 sector weakness +
Phase 2 market cycle weakness, and assigns each stock exactly one category:
High Conviction Bearish / Building Weakness / Watch for Breakdown / Not Qualified.

Idempotent: each date's rows are replaced wholesale, so re-running is safe.
Never touches V1.

Prerequisites:
    python run_v2_sector_intelligence.py
    python run_v2_market_cycle.py

Usage:
    python run_v2_bearish_opportunity.py
"""

from __future__ import annotations

from intelligence_v2.database.engine import init_db
from intelligence_v2.services.bearish_opportunity import (
    get_available_dates,
    get_category_counts,
    get_latest,
    run_bearish_backfill,
)


def main() -> None:
    print("=== Bearish Opportunity Engine (V2 Phase 4) ===\n")
    init_db()

    dates = get_available_dates()
    if not dates:
        print("No Phase 1/2 context found. Run run_v2_sector_intelligence.py and "
             "run_v2_market_cycle.py first.")
        return
    print(f"Context dates available: {len(dates)} ({dates[0]} to {dates[-1]})")

    result = run_bearish_backfill(dates)
    print(f"\nUniverse scanned : {result['universe']} symbols (from V1 price_history)")
    print(f"Rows written     : {result['rows_written']} ({result['dates']} dates)")

    counts = get_category_counts()
    print("\n=== Latest categories ===")
    for category, n in counts.items():
        print(f"  {category:24s} {n}")

    conviction = get_latest("High Conviction Bearish")
    if not conviction.empty:
        print("\n=== High Conviction Bearish ===")
        cols = ["rank_in_category", "symbol", "sector", "sector_state",
               "cycle_stage", "rs_1m", "signal_count"]
        print(conviction[cols].to_string(index=False))

    building = get_latest("Building Weakness")
    if not building.empty:
        print(f"\n=== Building Weakness (top 10 of {len(building)}) ===")
        cols = ["rank_in_category", "symbol", "rs_1m", "rs_slope", "signal_count"]
        print(building[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
