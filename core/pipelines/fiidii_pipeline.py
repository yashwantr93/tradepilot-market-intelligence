"""FII/DII ingestion: fetch latest provisional flows → store (forward-accumulating)."""

from __future__ import annotations

from core.connectors.fiidii_connector import FiiDiiConnector
from core.db import repository as repo
from core.utils.logging import get_logger

log = get_logger(__name__)


def run_fiidii_ingestion() -> tuple[int, str]:
    """Ingest the latest FII/DII row. Returns (rows_stored, source_status)."""
    job_id = repo.start_job("fiidii_ingestion", source="nse")
    try:
        conn = FiiDiiConnector()
        df = conn.fetch("fii_dii")
        stored = repo.upsert_fii_dii(df, source="NSE" if conn.last_status == "ok" else "seed")
        repo.finish_job(job_id, "ok", rows_in=len(df), rows_out=stored)
        if not df.empty:
            r = df.iloc[0]
            log.info("FII/DII %s: FII net %.1f Cr, DII net %.1f Cr (%s)",
                     r["trade_date"], r["fii_net"], r["dii_net"], conn.last_status)
        return stored, conn.last_status
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("FII/DII ingestion failed")
        raise
