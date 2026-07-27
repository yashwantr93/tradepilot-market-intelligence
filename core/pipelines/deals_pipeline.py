"""
Bulk & block deal ingestion.

Flow per kind: EXTRACT (NSE + BSE) → TRANSFORM (enrich) → VALIDATE (DQ rules,
dead-letter) → STORE (dedup upsert). One function handles both bulk and block.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from core.connectors.bse_connector import BSEConnector
from core.connectors.nse_connector import NSEConnector
from core.db import repository as repo
from core.processing.transforms import enrich_deals
from core.processing.validators import validate_deals
from core.utils.logging import get_logger

log = get_logger(__name__)


def run_deal_ingestion(kind: str, trade_date: dt.date) -> int:
    """Ingest 'bulk' or 'block' deals for a date. Returns rows stored."""
    assert kind in ("bulk", "block")
    resource = f"{kind}_deals"
    job_id = repo.start_job(f"{kind}_deal_ingestion", source="nse+bse")
    try:
        symbol_map = repo.get_symbol_map()

        # EXTRACT — union NSE (primary) + BSE (stub for now).
        frames = []
        for conn in (NSEConnector(), BSEConnector()):
            try:
                frames.append(conn.fetch(resource, trade_date=trade_date))
            except Exception as e:  # noqa: BLE001 - one bad source must not stop ingest
                log.warning("%s %s fetch failed: %s", conn.name, resource, e)
        raw = pd.concat([f for f in frames if not f.empty], ignore_index=True) \
            if any(not f.empty for f in frames) else pd.DataFrame()

        if raw.empty:
            repo.finish_job(job_id, "ok", rows_in=0, rows_out=0)
            log.info("%s deals: no rows for %s", kind, trade_date)
            return 0

        # TRANSFORM
        enriched = enrich_deals(raw, symbol_map)

        # VALIDATE
        valid, rejected = validate_deals(enriched, symbol_map)
        for row in rejected:
            repo.add_dead_letter(f"{kind}_deals", row, row.pop("_reason", "invalid"))
        if rejected:
            log.warning("%s deals: quarantined %d invalid rows", kind, len(rejected))

        # STORE (dedup upsert)
        stored = repo.upsert_deals(valid, kind)
        repo.finish_job(job_id, "ok", rows_in=len(raw), rows_out=stored)
        log.info("%s deals: %d in, %d stored (deduped) for %s",
                 kind, len(raw), stored, trade_date)
        return stored
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("%s deal ingestion failed", kind)
        raise
