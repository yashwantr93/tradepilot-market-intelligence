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
from core.pipelines.corp_action_materiality_pipeline import run_corp_action_materiality
from core.processing.event_classifier import classify_event
from core.utils.logging import get_logger

# NOTE: Market Reaction (Phase 3, event_intelligence/) is deliberately NOT
# imported here, unlike the materiality pipeline above. corp_action_
# materiality_pipeline lives inside core/ and only ever touches V1 data, so
# importing it from here stays within core/'s own boundary. event_intelligence
# additionally imports intelligence_v2 (for calendar-aligned RS primitives) —
# importing IT from inside core/ would make core/ transitively depend on
# intelligence_v2 being importable, which is exactly what CLAUDE.md's V1/V2
# isolation rule exists to prevent, even though the rule's literal text only
# names direct imports. Market Reaction therefore runs as its own separate
# step (see run_market_reaction.py) — called after run_corp_actions.py in
# run_daily.py, the same pattern V2's run_v2_*.py scripts already use to
# depend on V1 data without either package importing the other.

log = get_logger(__name__)


def dedupe_hash(symbol: str, date, summary: str) -> str:
    """An event's stable identity — Phase 1.5 fix.

    Deliberately does NOT include event_type. Audited (Phase 1.5) against
    all 431 real stored rows: grouping by (symbol, date, summary[:80]) alone
    produces zero collisions, so this is already a reliable real-world event
    identity on its own. event_type is a CLASSIFIED/DERIVED attribute of the
    event, not part of its identity — including it meant that correcting a
    misclassification (e.g. the Phase 1 ESOP/FDA-warning-letter fixes)
    produced a brand new hash and therefore a duplicate row on the next live
    re-run, rather than updating the original. Corrections now go through
    `core/pipelines/corp_actions_backfill.py`, which updates existing rows
    in place under this same identity.
    """
    key = f"{symbol}|{date}|{summary[:80]}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


# Backward-compatible alias — old call sites/tests that still pass event_type
# positionally would break loudly rather than silently drift; none exist in
# this codebase (checked), so no wrapper is kept.


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
                "dedupe_hash": dedupe_hash(r["symbol"], r["date"], summary),
            })

        stored, stored_ids = repo.upsert_corporate_actions(rows)
        repo.finish_job(job_id, "ok", rows_in=len(raw), rows_out=stored)
        log.info("Corp actions: %d raw, %d classified (tracked), %d stored (deduped)",
                 len(raw), classified, stored)

        # Phase 2 — incremental materiality for just the newly-stored rows.
        # Failure here must never fail the ingestion job itself (materiality
        # is an enrichment, not a required step for corp_actions to be usable).
        if stored_ids:
            try:
                run_corp_action_materiality(action_ids=stored_ids)
            except Exception:  # noqa: BLE001
                log.exception("Corp action materiality enrichment failed "
                              "(non-fatal — corp_actions rows are still stored)")

        return stored, status, {"raw": len(raw), "classified": classified, "stored": stored}
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("Corp actions ingestion failed")
        raise
