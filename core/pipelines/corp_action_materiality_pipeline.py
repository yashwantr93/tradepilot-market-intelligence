"""
Corporate-action materiality pipeline — Phase 2 Event Materiality.

Computes and stores materiality for every stored Dividend / Large Order Win
corporate_actions row (the two categories Phase 2's audit found have both a
reliably extractable magnitude and a reliable denominator — see
core/processing/corp_action_materiality.py). Every row gets a result,
including UNKNOWN ones — absence of a row means "not yet attempted", a
stored UNKNOWN means "attempted, evidence was insufficient".

`action_ids=None` (the default) processes every stored row of the two
categories — used once as a backfill for pre-Phase-2 history, and safe to
re-run (upsert on corporate_action_id, idempotent). Pass specific ids to
process only the rows a live `corp_actions_pipeline` run just inserted.
"""

from __future__ import annotations

from core.db import repository as repo
from core.processing.corp_action_materiality import (
    compute_dividend_materiality,
    compute_large_order_materiality,
)
from core.utils.logging import get_logger

log = get_logger(__name__)

_WIRED_TYPES = ["Dividend", "Large Order Win"]


def run_corp_action_materiality(action_ids: list[int] | None = None) -> dict:
    """Returns {"processed": N, "by_tier": {...}, "unknown_reasons": {...}}."""
    rows = repo.get_corporate_actions_by_type(_WIRED_TYPES, ids=action_ids)
    updates = []
    by_tier: dict[str, int] = {}

    for r in rows:
        if r["event_type"] == "Dividend":
            close = repo.get_latest_close(r["symbol"])
            result = compute_dividend_materiality(r["event_summary"], close)
            denom_asof = None  # latest close's own date isn't tracked here; see report limitations
        else:  # Large Order Win
            trailing_rev = repo.get_trailing_revenue(r["symbol"])
            result = compute_large_order_materiality(r["event_summary"], trailing_rev)
            denom_asof = None

        tier = result["materiality_tier"]
        by_tier[tier] = by_tier.get(tier, 0) + 1
        updates.append({
            "corporate_action_id": r["id"], "symbol": r["symbol"], "event_type": r["event_type"],
            "magnitude_value": result["magnitude_value"], "magnitude_unit": result["magnitude_unit"],
            "denominator_value": result["denominator_value"],
            "denominator_type": result["denominator_type"], "denominator_asof": denom_asof,
            "materiality_tier": tier, "materiality_reason": result["materiality_reason"],
        })

    stored = repo.upsert_corp_action_materiality(updates)
    log.info("Corp action materiality: %d processed, %d stored, tiers=%s",
             len(rows), stored, by_tier)
    return {"processed": len(rows), "stored": stored, "by_tier": by_tier}
