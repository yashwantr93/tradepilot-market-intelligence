"""
Early Momentum Engine (V2 Phase 3) runner.

Scans V1's existing stock universe (price_history), computes relative strength,
moving-average position, price momentum and volume expansion, joins Phase 1
sector strength + Phase 2 market cycle, and assigns each stock exactly one
category: Emerging Leader / Building Momentum / Watch Closely / Not Qualified.

Idempotent: each date's rows are replaced wholesale, so re-running is safe.
Never touches V1.

Prerequisites:
    python run_v2_sector_intelligence.py
    python run_v2_market_cycle.py

Usage:
    python run_v2_early_momentum.py
"""

from __future__ import annotations

from intelligence_v2.database.engine import init_db
from intelligence_v2.services.early_momentum import (
    get_available_dates,
    get_category_counts,
    get_latest,
    run_momentum_backfill,
)


def main() -> None:
    print("=== Early Momentum Engine (V2 Phase 3) ===\n")
    init_db()

    dates = get_available_dates()
    if not dates:
        print("No Phase 1/2 context found. Run run_v2_sector_intelligence.py and "
             "run_v2_market_cycle.py first.")
        return
    print(f"Context dates available: {len(dates)} ({dates[0]} to {dates[-1]})")

    result = run_momentum_backfill(dates)
    print(f"\nUniverse scanned : {result['universe']} symbols (from V1 price_history)")
    print(f"Rows written     : {result['rows_written']} ({result['dates']} dates)")

    counts = get_category_counts()
    print("\n=== Latest categories ===")
    for category, n in counts.items():
        print(f"  {category:20s} {n}")

    leaders = get_latest("Emerging Leader")
    if not leaders.empty:
        print("\n=== Emerging Leaders ===")
        cols = ["rank_in_category", "symbol", "sector", "sector_state",
               "cycle_stage", "rs_1m", "signal_count"]
        print(leaders[cols].to_string(index=False))

    building = get_latest("Building Momentum")
    if not building.empty:
        print(f"\n=== Building Momentum (top 10 of {len(building)}) ===")
        cols = ["rank_in_category", "symbol", "rs_1m", "rs_slope", "signal_count"]
        print(building[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
