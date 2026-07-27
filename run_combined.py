"""
Combined Watchlist runner (Confluence Engine).

Merges the two EXISTING watchlist sources already in the database:
  * Deal watchlist          (daily_watchlist)        -> bulk/block deals
  * Institutional watchlist (institutional_watchlist) -> FII/DII + sector rotation

…into one tiered research list and writes three artifacts under reports/:
  1. Combined Watchlist CSV   (sorted Tier 1 -> 2 -> 3)
  2. Combined Daily Report
  3. Tier Summary Report

Pure rule-based confluence. NO scoring · NO weighting · NO prediction.

Prerequisite: run run_live.py (deals) and run_institutional.py (FII/DII+sectors)
first so both source watchlists exist. This runner does not fetch any new data.

Usage:  python run_combined.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import datetime as dt

from core import reports
from core.db import repository as repo
from core.db.engine import init_db
from core.utils.logging import get_logger
from core.watchlist.combined import build_combined_watchlist

log = get_logger("run_combined")


def main() -> None:
    ap = argparse.ArgumentParser(description="Combined watchlist (confluence) runner")
    ap.add_argument("--date", help="trade date YYYY-MM-DD (default: latest available)")
    args = ap.parse_args()

    init_db()
    trade_date = (dt.date.fromisoformat(args.date) if args.date
                  else repo.latest_watchlist_date())
    if trade_date is None:
        log.error("No watchlist data found. Run run_live.py and run_institutional.py first.")
        return

    log.info("=== Combined watchlist for %s ===", trade_date)
    deal_n = len(repo.get_watchlist(trade_date))
    inst_n = len(repo.get_institutional_watchlist(trade_date))
    if deal_n == 0 and inst_n == 0:
        log.error("Both sources empty for %s — nothing to combine.", trade_date)
        return

    n = build_combined_watchlist(trade_date)
    df = repo.get_combined_watchlist(trade_date)
    t1 = int((df["tier"] == 1).sum()) if not df.empty else 0
    t2 = int((df["tier"] == 2).sum()) if not df.empty else 0
    t3 = int((df["tier"] == 3).sum()) if not df.empty else 0

    csv_path, csv_rows = reports.export_combined_csv(trade_date)
    report_path = reports.generate_combined_report(trade_date)
    summary_path = reports.generate_tier_summary(trade_date)

    print("\n".join([
        "",
        f"Trade date          : {trade_date}",
        f"Deal watchlist      : {deal_n} stocks",
        f"Institutional list  : {inst_n} stocks",
        f"Combined (unique)   : {n} stocks",
        f"  Tier 1 (both)     : {t1}",
        f"  Tier 2 (inst only): {t2}",
        f"  Tier 3 (deal only): {t3}",
        f"Combined CSV        : {csv_path} ({csv_rows} rows)",
        f"Combined report     : {report_path}",
        f"Tier summary        : {summary_path}",
    ]))


if __name__ == "__main__":
    main()
