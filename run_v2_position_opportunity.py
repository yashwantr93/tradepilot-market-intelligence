"""
Position Opportunity Engine (V2 Phase 5) runner.

Scans V1's existing stock universe (price_history) via the same shared
relative-strength machinery Phase 3/4 use, joins Phase 1 sector strength +
Phase 2 market cycle + Phase 3 Early Momentum confirmation, and assigns each
stock exactly one category: High Conviction Position / Position Candidate /
Accumulation Watch / Not Qualified.

Idempotent: each date's rows are replaced wholesale, so re-running is safe.
Never touches V1.

Prerequisites:
    python run_v2_sector_intelligence.py
    python run_v2_market_cycle.py
    python run_v2_early_momentum.py

Usage:
    python run_v2_position_opportunity.py
"""

from __future__ import annotations

from intelligence_v2.database.engine import init_db
from intelligence_v2.services.position_opportunity import (
    get_available_dates,
    get_category_counts,
    get_latest,
    run_position_backfill,
)


def main() -> None:
    print("=== Position Opportunity Engine (V2 Phase 5) ===\n")
    init_db()

    dates = get_available_dates()
    if not dates:
        print("No Phase 1/2/3 context found. Run run_v2_sector_intelligence.py, "
             "run_v2_market_cycle.py and run_v2_early_momentum.py first.")
        return
    print(f"Context dates available: {len(dates)} ({dates[0]} to {dates[-1]})")

    result = run_position_backfill(dates)
    print(f"\nUniverse scanned : {result['universe']} symbols (from V1 price_history)")
    print(f"Rows written     : {result['rows_written']} ({result['dates']} dates)")

    counts = get_category_counts()
    print("\n=== Latest categories ===")
    for category, n in counts.items():
        print(f"  {category:24s} {n}")

    conviction = get_latest("High Conviction Position")
    if not conviction.empty:
        print(f"\n=== High Conviction Position (top 10 of {len(conviction)}) ===")
        cols = ["rank_in_category", "symbol", "sector", "sector_state",
               "cycle_stage", "early_momentum_category", "rs_3m", "signal_count"]
        print(conviction[cols].head(10).to_string(index=False))

    candidates = get_latest("Position Candidate")
    if not candidates.empty:
        print(f"\n=== Position Candidates (top 10 of {len(candidates)}) ===")
        cols = ["rank_in_category", "symbol", "rs_3m", "rs_slope", "signal_count"]
        print(candidates[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
