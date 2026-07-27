"""
Corporate actions ingestion.

Flow: EXTRACT (NSE announcements + structured actions) → CLASSIFY (rule-based
event type / impact / priority) → FILTER (keep only tracked event types) →
DEDUPE-STORE. No scoring, no ML.
"""

from __future__ import annotations

import hashlib

import pandas as pd

from core.connectors.corp_actions_connector import CorpActionsConnector
from core.db import repository as repo
from core.processing.event_classifier import classify_event
from core.utils.logging import get_logger

log = get_logger(__name__)


def _dedupe_hash(symbol: str, date, event_type: str, summary: str) -> str:
    key = f"{symbol}|{date}|{event_type}|{summary[:80]}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def run_corp_actions_ingestion() -> tuple[int, dict, dict]:
    """Ingest + classify corporate actions.

    Returns (stored, source_status, counts) where counts has raw/classified/stored.
    """
    job_id = repo.start_job("corp_actions_ingestion", source="nse")
    try:
        conn = CorpActionsConnector()
        frames, status = [], {}
        for resource in ("announcements", "actions"):
            df = conn.fetch(resource)
            status[resource] = conn.last_status
            if not df.empty:
                frames.append(df)
        raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if raw.empty:
            repo.finish_job(job_id, "ok", rows_in=0, rows_out=0)
            return 0, status, {"raw": 0, "classified": 0, "stored": 0}

        rows, classified = [], 0
        for _, r in raw.iterrows():
            event_type, impact, priority = classify_event(r["raw_text"])
            if event_type is None:
                continue  # untracked noise (board outcome, newspaper pub, etc.)
            classified += 1
            summary = r["raw_text"].strip()[:300]
            rows.append({
                "announcement_date": r["date"],
                "symbol": str(r["symbol"]).strip().upper(),
                "company_name": r["company_name"],
                "event_type": event_type, "event_summary": summary,
                "impact_tag": impact, "priority": priority, "source": r["source"],
                "dedupe_hash": _dedupe_hash(r["symbol"], r["date"], event_type, summary),
            })

        stored = repo.upsert_corporate_actions(rows)
        repo.finish_job(job_id, "ok", rows_in=len(raw), rows_out=stored)
        log.info("Corp actions: %d raw, %d classified (tracked), %d stored (deduped)",
                 len(raw), classified, stored)
        return stored, status, {"raw": len(raw), "classified": classified, "stored": stored}
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("Corp actions ingestion failed")
        raise
