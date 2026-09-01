"""
Trade Signal pipeline — Phase 5. Orchestration only: reads V1 event/
materiality/reaction data and V1 expectation cross-reference (`core.db`),
reads V2 technical confirmation (`intelligence_v2` via
`technical_confirmation.py`), computes via `signal_engine.py` (pure logic),
writes back to V1 (`event_trade_signal`).

Same bridging pattern as `pipeline.py` (Phase 3) — the one place allowed to
import both `core.db` and V2, kept at this level rather than inside `core/`
or `intelligence_v2/` themselves.
"""

from __future__ import annotations

import json

from core.db import repository as repo
from event_intelligence.signal_engine import build_signal
from event_intelligence.technical_confirmation import get_technical_confirmation


def run_trade_signals(action_ids: list[int] | None = None) -> dict:
    """Returns {"processed": N, "by_direction": {...}, "by_strength": {...}}.

    Phase 11: wrapped with the same job_runs audit-trail convention every V1
    pipeline already uses — see the Phase 11 report's FAILURE RECOVERY
    section."""
    job_id = repo.start_job("trade_signals", source="event_intelligence")
    try:
        return _run_trade_signals(action_ids, job_id)
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        raise


def _run_trade_signals(action_ids: list[int] | None, job_id: int) -> dict:
    events = repo.get_events_for_signal_engine(ids=action_ids)

    updates = []
    by_direction: dict[str, int] = {}
    by_strength: dict[str, int] = {}

    for event in events:
        impact_tag = event["impact_tag"]
        if impact_tag == "Bullish":
            technical = get_technical_confirmation(event["symbol"], "long")
        elif impact_tag == "Bearish":
            technical = get_technical_confirmation(event["symbol"], "short")
        else:
            # Neutral/Ambiguous events short-circuit inside build_signal
            # before technical confirmation would matter — fetching either
            # side here would be wasted work, so pass a neutral UNKNOWN stub.
            technical = {"status": "UNKNOWN", "category": None,
                        "reason": "Event has no directional thesis — technical "
                                  "confirmation was not evaluated."}

        expectation = repo.get_nearby_expectation_surprise(event["symbol"], event["announcement_date"])

        signal = build_signal(event, technical, expectation)

        by_direction[signal["direction"]] = by_direction.get(signal["direction"], 0) + 1
        by_strength[signal["signal_strength"]] = by_strength.get(signal["signal_strength"], 0) + 1

        updates.append({
            "corporate_action_id": event["id"], "symbol": event["symbol"],
            "event_type": event["event_type"], "announcement_date": event["announcement_date"],
            **{k: v for k, v in signal.items() if k not in ("evidence_for_json", "evidence_against_json")},
            "evidence_for_json": json.dumps(signal["evidence_for_json"]),
            "evidence_against_json": json.dumps(signal["evidence_against_json"]),
        })

    stored = repo.upsert_event_trade_signal(updates)
    repo.finish_job(job_id, "ok", rows_in=len(events), rows_out=stored)
    return {"processed": len(events), "stored": stored,
           "by_direction": by_direction, "by_strength": by_strength}
