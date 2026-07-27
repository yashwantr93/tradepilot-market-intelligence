"""
Live-data validation runner.

Replaces synthetic seed with REAL market data wherever reachable:
  * Bulk/Block deals  -> NSE public archive CSV (latest trading day)
  * Prices / technicals -> yfinance (NSE .NS tickers) + ^NSEI benchmark
  * Sectors            -> yfinance .info (best effort)

Then generates today's actual watchlist and four artifacts under reports/:
  1. Watchlist CSV
  2. Daily Watchlist Report
  3. Data Quality Report
  4. Source Success/Failure Report

NO scoring · NO ML · NO prediction — rule-based reduction only.

Usage:  python run_live.py
"""

from __future__ import annotations

import os

# Force live mode before importing any core module (config reads env at import).
os.environ["MID_OFFLINE"] = "0"

import pandas as pd  # noqa: E402

from core.connectors.nse_connector import NSEConnector  # noqa: E402
from core.db import repository as repo  # noqa: E402
from core.db.engine import init_db  # noqa: E402
from core.pipelines.price_pipeline import run_price_ingestion  # noqa: E402
from core.processing.sectors import get_sectors  # noqa: E402
from core.processing.symbol_master import build_symbol_master_from_symbols  # noqa: E402
from core.processing.transforms import enrich_deals  # noqa: E402
from core.processing.validators import validate_deals  # noqa: E402
from core.utils.logging import get_logger  # noqa: E402
from core.watchlist.rules import generate_watchlist  # noqa: E402
from core import reports  # noqa: E402

log = get_logger("run_live")


def _store_deals(df: pd.DataFrame, kind: str, symbol_map: dict) -> tuple[int, int]:
    """Enrich → validate → dedupe-store an already-fetched deal frame."""
    if df.empty:
        return 0, 0
    enriched = enrich_deals(df, symbol_map)
    valid, rejected = validate_deals(enriched, symbol_map)
    for row in rejected:
        repo.add_dead_letter(f"{kind}_deals", row, row.pop("_reason", "invalid"))
    stored = repo.upsert_deals(valid, kind)
    return stored, len(rejected)


def main() -> None:
    log.info("=== LIVE validation run ===")
    init_db()

    # 1) EXTRACT real deals (also used to discover the universe + date).
    nse = NSEConnector()
    raw_bulk = nse.fetch("bulk_deals")
    bulk_status = nse.last_status
    raw_block = nse.fetch("block_deals")
    block_status = nse.last_status

    all_deals = pd.concat([d for d in (raw_bulk, raw_block) if not d.empty],
                          ignore_index=True) if (not raw_bulk.empty or not raw_block.empty) \
        else pd.DataFrame()
    if all_deals.empty:
        log.error("No deal data from any source — aborting.")
        return

    trade_date = max(all_deals["trade_date"])
    universe = sorted(all_deals["symbol"].unique())
    log.info("Trade date: %s | deal universe: %d symbols", trade_date, len(universe))

    # 2) Sectors (real, best-effort) + symbol master from the live universe.
    log.info("Resolving sectors for %d symbols (yfinance)...", len(universe))
    sectors = get_sectors(universe)
    sectors_resolved = sum(1 for v in sectors.values() if v != "Unknown")
    build_symbol_master_from_symbols(universe, sectors)
    symbol_map = repo.get_symbol_map()

    # 3) Prices / technicals (real) for the universe + benchmark.
    log.info("Ingesting prices (yfinance) for the universe...")
    run_price_ingestion(end=trade_date)
    priced = repo.get_symbols_with_prices() & set(universe)
    missing_price = [s for s in universe if s not in priced]
    log.info("Priced %d/%d symbols (%d missing)", len(priced), len(universe), len(missing_price))

    # 4) STORE deals (validate + dedupe).
    bulk_stored, bulk_rej = _store_deals(raw_bulk, "bulk", symbol_map)
    block_stored, block_rej = _store_deals(raw_block, "block", symbol_map)

    # 5) Generate the actual watchlist.
    n_wl = generate_watchlist(trade_date)
    log.info("Watchlist: %d names", n_wl)

    # 6) Stats + reports.
    stats = {
        "stocks_processed": len(universe),
        "bulk_candidates": int(raw_bulk["symbol"].nunique()) if not raw_bulk.empty else 0,
        "block_candidates": int(raw_block["symbol"].nunique()) if not raw_block.empty else 0,
        "bulk_rows": len(raw_bulk),
        "block_rows": len(raw_block),
        "priced_symbols": len(priced),
        "missing_price_symbols": len(missing_price),
        "sectors_resolved": sectors_resolved,
        "dead_letter": repo.count_dead_letters(),
    }

    sources = [
        {"Source": "NSE bulk-deals archive CSV", "Method": "archive_csv",
         "Status": _status_label(bulk_status), "Rows": len(raw_bulk)},
        {"Source": "NSE block-deals archive CSV", "Method": "archive_csv",
         "Status": _status_label(block_status), "Rows": len(raw_block)},
        {"Source": "yfinance prices/technicals", "Method": "yfinance",
         "Status": "OK" if priced else "FAIL", "Rows": len(priced)},
        {"Source": "yfinance sectors", "Method": "yfinance .info",
         "Status": "OK" if sectors_resolved else "PARTIAL",
         "Rows": f"{sectors_resolved}/{len(universe)}"},
        {"Source": "BSE deals", "Method": "stub", "Status": "SKIPPED", "Rows": 0},
    ]

    csv_path, csv_rows = reports.export_watchlist_csv(trade_date)
    daily_path = reports.generate_daily_report(trade_date, stats)
    dq_path = reports.generate_data_quality_report(trade_date, stats)
    src_path = reports.generate_source_report(trade_date, sources)

    log.info("=== Reports written ===")
    for p in (csv_path, daily_path, dq_path, src_path):
        log.info("  %s", p)
    print("\n".join([
        "",
        f"Trade date           : {trade_date}",
        f"Stocks processed     : {stats['stocks_processed']}",
        f"Bulk candidates      : {stats['bulk_candidates']}",
        f"Block candidates     : {stats['block_candidates']}",
        f"Final watchlist      : {n_wl}",
        f"Watchlist CSV        : {csv_path} ({csv_rows} rows)",
        f"Daily report         : {daily_path}",
        f"Data quality report  : {dq_path}",
        f"Source report        : {src_path}",
    ]))


def _status_label(s: str) -> str:
    return {"ok": "OK", "empty": "EMPTY", "fallback": "FALLBACK",
            "offline": "OFFLINE"}.get(s, s.upper())


if __name__ == "__main__":
    main()
