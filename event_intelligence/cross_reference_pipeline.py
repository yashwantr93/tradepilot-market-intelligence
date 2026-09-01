"""
Sector/Theme -> Stock cross-reference pipeline — Phase 7. Orchestration
only: reads Phase 6's latest sector/theme state and Phase 5's per-symbol
trade signals (both already computed and stored — no new price/RS/event
computation happens here), combines via `cross_reference.py`, writes to
`sector_stock_cross_reference`.

Recency window (default 90 days, matching Phase 6's own event-density
convention): a symbol's corporate action older than this is not treated as
"the company's current catalyst" — the symbol still appears in the
cross-reference (with company_event=None -> NO_CATALYST), it just isn't
credited with a stale event.
"""

from __future__ import annotations

import datetime as dt
import json

from core.db import repository as repo
from event_intelligence.cross_reference import build_cross_reference

_ROLE_FIELDS = [
    ("leaders_json", "leader"), ("early_participants_json", "early_participant"),
    ("laggards_json", "laggard"), ("non_participants_json", "non_participant"),
]
DEFAULT_RECENCY_DAYS = 90


def run_cross_reference(recency_days: int = DEFAULT_RECENCY_DAYS) -> dict:
    """Phase 11: wrapped with the same job_runs audit-trail convention every
    V1 pipeline already uses — see the Phase 11 report's FAILURE RECOVERY
    section."""
    job_id = repo.start_job("cross_reference", source="event_intelligence")
    try:
        return _run_cross_reference(recency_days, job_id)
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        raise


def _run_cross_reference(recency_days: int, job_id: int) -> dict:
    latest = repo.get_latest_sector_theme_state()
    if latest.empty:
        repo.finish_job(job_id, "ok", rows_in=0, rows_out=0,
                        error="no sector_theme_state data — run run_sector_theme.py first")
        return {"processed": 0, "error": "no sector_theme_state data — run run_sector_theme.py first"}

    as_of_date = latest["as_of_date"].iloc[0]

    role_map: dict[tuple[str, str], str] = {}
    sector_info: dict[str, dict] = {}
    for _, row in latest.iterrows():
        sector = row["sector_or_theme"]
        sector_info[sector] = {"stage": row["confirmed_state"], "direction": row["direction_context"]}
        for field, role in _ROLE_FIELDS:
            for symbol in json.loads(row[field]):
                role_map[(sector, symbol)] = role

    all_symbols = {sym for (_, sym) in role_map}
    since = as_of_date - dt.timedelta(days=recency_days)
    event_signals = repo.get_latest_event_signal_per_symbol(all_symbols, since)

    updates = []
    by_context: dict[str, int] = {}
    conflicts_found = 0

    for (sector, symbol), role in role_map.items():
        info = sector_info[sector]
        company_event = event_signals.get(symbol)
        result = build_cross_reference(sector, info["stage"], info["direction"], symbol, role, company_event)

        by_context[result["trade_context"]] = by_context.get(result["trade_context"], 0) + 1
        if result["conflicts_json"]:
            conflicts_found += 1

        updates.append({
            "as_of_date": as_of_date, **{k: v for k, v in result.items()
                                        if k not in ("sector_evidence_json", "stock_evidence_json",
                                                     "evidence_for_json", "evidence_against_json",
                                                     "conflicts_json")},
            "sector_evidence_json": json.dumps(result["sector_evidence_json"]),
            "stock_evidence_json": json.dumps(result["stock_evidence_json"]),
            "evidence_for_json": json.dumps(result["evidence_for_json"]),
            "evidence_against_json": json.dumps(result["evidence_against_json"]),
            "conflicts_json": json.dumps(result["conflicts_json"]),
        })

    stored = repo.upsert_sector_stock_cross_reference(updates)
    repo.finish_job(job_id, "ok", rows_in=len(updates), rows_out=stored)
    return {
        "processed": len(updates), "stored": stored, "as_of_date": str(as_of_date),
        "distinct_symbols": len(all_symbols), "symbols_with_company_event": len(event_signals),
        "by_trade_context": by_context, "conflicts_found": conflicts_found,
    }
