"""
Market Cycle Engine (V2 Phase 2) runner.

Reads Phase 1's `sector_intelligence_daily` from market_v2.db, classifies every
sector into exactly one of 7 cycle stages per date (chronologically, so
hysteresis and transition history build correctly), and stores the results plus
a log of confirmed transitions.

Idempotent: re-running is safe (upsert on natural keys). Never touches V1.

Prerequisite: run `python run_v2_sector_intelligence.py` first.

Usage:
    python run_v2_market_cycle.py
"""

from __future__ import annotations

from intelligence_v2.database.engine import init_db
from intelligence_v2.services.market_cycle import (
    get_current_market_cycle,
    get_sector_intelligence_dates,
    get_transition_history,
    run_cycle_backfill,
)


def main() -> None:
    print("=== Market Cycle Engine (V2 Phase 2) ===\n")
    init_db()

    dates = get_sector_intelligence_dates()
    if not dates:
        print("No Sector Intelligence data found. Run run_v2_sector_intelligence.py first.")
        return
    print(f"Sector Intelligence dates available: {len(dates)} ({dates[0]} to {dates[-1]})")

    result = run_cycle_backfill(dates)
    print(f"\nCycle rows written : {result['rows_written']} "
         f"({result['dates']} dates x 12 sectors)")
    print(f"Confirmed transitions logged: {result['transitions']}")

    current = get_current_market_cycle()
    if not current.empty:
        print(f"\n=== Current Market Cycle: {current['trade_date'].iloc[0]} ===")
        cols = ["sector", "stage", "prior_stage", "days_in_stage", "raw_stage"]
        print(current[cols].to_string(index=False))
        pending = current[current["stage"] != current["raw_stage"]]
        if not pending.empty:
            print(f"\n{len(pending)} sector(s) have a pending (unconfirmed) stage change.")

    transitions = get_transition_history(limit=10)
    if not transitions.empty:
        print("\n=== Most recent confirmed transitions ===")
        tv = transitions.copy()
        tv["change"] = tv["from_stage"].fillna("-") + " -> " + tv["to_stage"]
        print(tv[["transition_date", "sector", "change",
                 "days_in_previous_stage"]].to_string(index=False))


if __name__ == "__main__":
    main()
