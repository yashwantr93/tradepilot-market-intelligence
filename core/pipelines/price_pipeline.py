"""Price ingestion: fetch OHLCV history → store in price_history."""

from __future__ import annotations

import datetime as dt

from core.connectors.price_connector import PriceConnector
from core.db import repository as repo
from core.utils.logging import get_logger

log = get_logger(__name__)


def run_price_ingestion(days: int = 280, end: dt.date | None = None,
                        symbols: list[str] | None = None) -> int:
    """Ingest daily OHLCV for the given symbols (+ benchmark). Returns rows stored.

    When ``symbols`` is None, the full symbol-master universe is used.
    """
    job_id = repo.start_job("price_ingestion", source="price")
    try:
        if symbols is None:
            symbols = list(repo.get_symbol_map().keys())
        df = PriceConnector().fetch("history", symbols=symbols, days=days, end=end)
        rows = repo.upsert_prices(df)
        repo.finish_job(job_id, "ok", rows_in=len(df), rows_out=rows)
        log.info("Price ingestion stored %d rows for %d symbols", rows, df["symbol"].nunique())
        return rows
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("Price ingestion failed")
        raise
