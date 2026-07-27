"""
Phase 1 backend runner.

Runs the minimum-viable pipeline end-to-end, in the approved priority order:

    1. Database setup
    2. Symbol master
    3. Price ingestion (feeds technical fields)
    4. Bulk deal ingestion
    5. Block deal ingestion
    6. Daily watchlist generation

Usage:
    python run_backend.py                 # run for latest trading day
    python run_backend.py --date 2026-06-23
    python run_backend.py --show          # also print the resulting watchlist

Set MID_OFFLINE=0 to attempt live sources (falls back to seed on failure).
"""

from __future__ import annotations

import argparse
import datetime as dt

from core.db import repository as repo
from core.db.engine import init_db
from core.pipelines.deals_pipeline import run_deal_ingestion
from core.pipelines.price_pipeline import run_price_ingestion
from core.processing.symbol_master import build_symbol_master
from core.utils.logging import get_logger
from core.utils.timeutils import latest_trading_day
from core.watchlist.rules import generate_watchlist

log = get_logger("run_backend")


def run(trade_date: dt.date) -> None:
    log.info("=== Phase 1 backend run for %s ===", trade_date)

    # 1. Database
    init_db()
    log.info("[1/6] Database ready")

    # 2. Symbol master
    n_sym = build_symbol_master()
    log.info("[2/6] Symbol master: %d symbols", n_sym)

    # 3. Price ingestion
    n_px = run_price_ingestion(end=trade_date)
    log.info("[3/6] Price history: %d rows", n_px)

    # 4. Bulk deals
    n_bulk = run_deal_ingestion("bulk", trade_date)
    log.info("[4/6] Bulk deals stored: %d", n_bulk)

    # 5. Block deals
    n_block = run_deal_ingestion("block", trade_date)
    log.info("[5/6] Block deals stored: %d", n_block)

    # 6. Watchlist
    n_wl = generate_watchlist(trade_date)
    log.info("[6/6] Watchlist generated: %d names", n_wl)

    log.info("=== Done ===")


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase 1 backend runner")
    ap.add_argument("--date", help="trade date YYYY-MM-DD (default: latest trading day)")
    ap.add_argument("--show", action="store_true", help="print resulting watchlist")
    args = ap.parse_args()

    trade_date = (dt.date.fromisoformat(args.date) if args.date
                  else latest_trading_day())
    run(trade_date)

    if args.show:
        df = repo.get_watchlist(trade_date)
        if df.empty:
            print("\n(No watchlist rows.)")
        else:
            cols = ["symbol", "sector", "current_price", "catalyst_tag",
                    "above_20_sma", "relative_strength", "volume_expansion",
                    "dist_52w_high_pct", "technical_status", "rule_count"]
            import pandas as pd
            pd.set_option("display.max_columns", None)
            pd.set_option("display.width", 200)
            print(f"\n=== Daily Watchlist - {trade_date} ({len(df)} names) ===")
            print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
