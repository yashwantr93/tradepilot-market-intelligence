"""
Sector Intelligence (V2 Phase 1) runner.

Backfills every date already present in V1's sector_rotation table (read-only
— "use existing V1 sector data as the primary source"), then computes and
stores multi-horizon performance/RS/momentum/trend + the 7-state
classification for each date, for all 12 sectors, into market_v2.db.

Idempotent: re-running is always safe (snapshots upsert on trade_date+sector).
Never writes to V1's database.

Usage:
    python run_v2_sector_intelligence.py
"""

from __future__ import annotations

from intelligence_v2.database.engine import init_db
from intelligence_v2.services.sector_intelligence import (
    get_overview,
    get_v1_sector_rotation_dates,
    run_backfill,
)
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("run_sector_intelligence")


def main() -> None:
    print("=== Sector Intelligence (V2 Phase 1) ===\n")
    init_db()

    dates = get_v1_sector_rotation_dates()
    print(f"V1 sector_rotation dates found: {len(dates)} ({dates[0]} to {dates[-1]})"
         if dates else "No V1 sector_rotation history found.")

    result = run_backfill(dates)
    print(f"\nSnapshots written : {result['snapshots_written']} "
         f"({result['dates']} dates x up to 12 sectors)")
    if result["sectors_skipped"]:
        print(f"Sectors with at least one skipped date: {result['sectors_skipped']}")

    overview = get_overview()
    if not overview.empty:
        print(f"\n=== Latest snapshot: {overview['trade_date'].iloc[0]} ===")
        cols = ["sector", "state", "days_in_state", "rs_1m", "rs_3m", "rs_6m",
               "above_20_sma", "above_200_sma", "consistency_pct"]
        print(overview[cols].to_string(index=False))


if __name__ == "__main__":
    main()
