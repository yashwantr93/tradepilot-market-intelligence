"""
Opportunity Intelligence pipeline — Phase 8. Orchestration only: reads
Phase 5's `event_trade_signal` and Phase 7's `sector_stock_cross_reference`
(both already computed — no new price/event/sector computation), combines
via `opportunity.py`, writes to `opportunity`.

Two input streams, matching the two ways an opportunity can originate
(never both from the same underlying row, so no double counting):

  1. Every LONG/SHORT event_trade_signal row -> EVENT_DRIVEN or CONFLUENCE
     (build_opportunity(), cross_ref attached if available).
  2. Phase 7 WATCH_CANDIDATE rows whose linked event has a genuine
     directional thesis (event_direction Bullish/Bearish) but Phase 5 chose
     NO_TRADE for a reason OTHER than "no directional thesis at all"
     (excludes NEUTRAL_OR_AMBIGUOUS_EVENT and CONTRADICTED_EVIDENCE) ->
     EMERGING_THEME. See the Phase 8 report's DISCOVERED ISSUES section:
     Phase 7's WATCH_CANDIDATE condition doesn't itself check the
     underlying event's direction, so this filter is applied here rather
     than assuming every WATCH_CANDIDATE row is actionable.
"""

from __future__ import annotations

import json

from core.db import repository as repo
from event_intelligence.opportunity import build_opportunity

_EXCLUDED_NO_TRADE_REASONS = {"NEUTRAL_OR_AMBIGUOUS_EVENT", "CONTRADICTED_EVIDENCE"}


def _cross_ref_for(symbol: str, cross_ref_by_symbol: dict[str, dict]) -> dict | None:
    row = cross_ref_by_symbol.get(symbol)
    if row is None:
        return None
    return {
        "sector_or_theme": row["sector_or_theme"], "sector_stage": row["sector_stage"],
        "participation_role": row["participation_role"], "trade_context": row["trade_context"],
        "conflicts_json": json.loads(row["conflicts_json"]) if row["conflicts_json"] else [],
        "sector_evidence_json": json.loads(row["sector_evidence_json"]) if row["sector_evidence_json"] else [],
    }


def run_opportunity_intelligence() -> dict:
    """Phase 11: wrapped with the same job_runs audit-trail convention every
    V1 pipeline already uses — see the Phase 11 report's FAILURE RECOVERY
    section."""
    job_id = repo.start_job("opportunity_intelligence", source="event_intelligence")
    try:
        return _run_opportunity_intelligence(job_id)
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        raise


def _run_opportunity_intelligence(job_id: int) -> dict:
    signals = repo.get_event_trade_signals()  # all rows, all directions
    cross_refs = repo.get_latest_sector_stock_cross_reference()

    if signals.empty:
        repo.finish_job(job_id, "ok", rows_in=0, rows_out=0,
                        error="no event_trade_signal data — run run_trade_signals.py first")
        return {"processed": 0, "error": "no event_trade_signal data — run run_trade_signals.py first"}

    cross_ref_by_symbol = ({row["symbol"]: row for _, row in cross_refs.iterrows()}
                           if not cross_refs.empty else {})
    as_of_date = cross_refs["as_of_date"].iloc[0] if not cross_refs.empty else \
        signals["announcement_date"].max()

    updates = []
    by_type: dict[str, int] = {}
    by_tier: dict[str, int] = {}

    # --- Stream 1: every LONG/SHORT signal ---
    directional = signals[signals["direction"].isin(["LONG", "SHORT"])]
    for _, sig in directional.iterrows():
        signal = {
            "symbol": sig["symbol"], "corporate_action_id": sig["corporate_action_id"],
            "event_type": sig["event_type"], "direction": sig["direction"],
            "signal_strength": sig["signal_strength"], "materiality_tier": sig["materiality_tier"],
            "market_reaction_state": sig["market_reaction_state"],
            "continuation_state": sig["continuation_state"],
            "technical_confirmation": sig["technical_confirmation"],
            "time_horizon": sig["time_horizon"], "data_quality": sig["data_quality"],
            "risk": sig["risk"], "invalidation": sig["invalidation"],
            "evidence_for": json.loads(sig["evidence_for_json"]) if sig["evidence_for_json"] else [],
            "evidence_against": json.loads(sig["evidence_against_json"]) if sig["evidence_against_json"] else [],
        }
        cross_ref = _cross_ref_for(sig["symbol"], cross_ref_by_symbol)
        opp = build_opportunity(signal, cross_ref)
        by_type[opp["opportunity_type"]] = by_type.get(opp["opportunity_type"], 0) + 1
        by_tier[opp["tier"]] = by_tier.get(opp["tier"], 0) + 1
        updates.append({
            "as_of_date": as_of_date, **{k: v for k, v in opp.items()
                                        if k not in ("evidence_for_json", "evidence_against_json",
                                                     "conflicts_json")},
            "evidence_for_json": json.dumps(opp["evidence_for_json"]),
            "evidence_against_json": json.dumps(opp["evidence_against_json"]),
            "conflicts_json": json.dumps(opp["conflicts_json"]),
        })

    # --- Stream 2: sector-led EMERGING_THEME (Phase 5 said NO_TRADE, but
    # not for lack of a directional thesis) ---
    no_trade = signals[signals["direction"] == "NO_TRADE"]
    no_trade_eligible = no_trade[~no_trade["no_trade_reason"].isin(_EXCLUDED_NO_TRADE_REASONS)]
    for _, sig in no_trade_eligible.iterrows():
        cross_ref = _cross_ref_for(sig["symbol"], cross_ref_by_symbol)
        if cross_ref is None or cross_ref["trade_context"] != "WATCH_CANDIDATE":
            continue
        # Reconstruct a minimal "signal" so build_opportunity's shape stays uniform —
        # direction is sector-implied here, not company-confirmed (documented on the row).
        implied_direction = "LONG" if cross_ref.get("sector_stage") else None
        signal = {
            "symbol": sig["symbol"], "corporate_action_id": sig["corporate_action_id"],
            "event_type": sig["event_type"], "direction": "LONG",  # WATCH_CANDIDATE is bullish-context only
            "signal_strength": "WEAK", "materiality_tier": sig["materiality_tier"],
            "market_reaction_state": sig["market_reaction_state"],
            "continuation_state": sig["continuation_state"],
            "technical_confirmation": sig["technical_confirmation"],
            "time_horizon": "WATCH", "data_quality": sig["data_quality"],
            "risk": "Sector/theme shows a developing story, but this stock's own company event "
                   "did not independently confirm a trade (Phase 5: NO_TRADE).",
            "invalidation": None, "evidence_for": [], "evidence_against": [],
        }
        opp = build_opportunity(signal, cross_ref)
        opp["opportunity_type"] = "EMERGING_THEME"
        opp["tier"] = "SPECULATIVE"  # sector-led only, no independent stock confirmation — never higher
        opp["time_horizon"] = "WATCH"
        by_type["EMERGING_THEME"] = by_type.get("EMERGING_THEME", 0) + 1
        by_tier["SPECULATIVE"] = by_tier.get("SPECULATIVE", 0) + 1
        updates.append({
            "as_of_date": as_of_date, **{k: v for k, v in opp.items()
                                        if k not in ("evidence_for_json", "evidence_against_json",
                                                     "conflicts_json")},
            "evidence_for_json": json.dumps(opp["evidence_for_json"]),
            "evidence_against_json": json.dumps(opp["evidence_against_json"]),
            "conflicts_json": json.dumps(opp["conflicts_json"]),
        })

    stored = repo.upsert_opportunity(updates)
    repo.finish_job(job_id, "ok", rows_in=len(updates), rows_out=stored)
    return {"processed": len(updates), "stored": stored, "as_of_date": str(as_of_date),
           "by_type": by_type, "by_tier": by_tier}
