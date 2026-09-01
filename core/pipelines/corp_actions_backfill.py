"""
Corporate-actions historical backfill — Phase 1.5 Event Data Integrity.

Re-derives (event_type, impact_tag, priority) for every EXISTING stored
corporate_actions row against the CURRENT classifier rules, using the
already-stored `event_summary` text (the only text persisted — the original
un-truncated raw_text was never kept, see the Phase 1.5 report's NOT
VERIFIED section). Corrects rows in place — never inserts a duplicate row —
and always stamps the new (event_type-free) dedupe_hash so a future live
re-ingestion of the same real-world announcement matches this same row
instead of creating a duplicate.

Provenance: a row is only touched if its classification would genuinely
change under current rules. When it does, the ORIGINAL event_type/impact_tag
are preserved in `original_event_type`/`original_impact_tag` before being
overwritten, alongside `reclassified_at` and `reclassification_reason` — the
correction is visible, not silently erased.

Safety: `dry_run=True` (the default) computes and reports everything WITHOUT
writing. Only an explicit `dry_run=False` call mutates the database, and
that happens as one atomic transaction (`repo.apply_corporate_action_corrections`).
Callers are expected to back up the database file before a real run — this
module does not do that itself (keeps the concerns separate and testable).
"""

from __future__ import annotations

import datetime as dt

from core.db import repository as repo
from core.pipelines.corp_actions_pipeline import dedupe_hash
from core.processing.event_classifier import classify_event

REASON = "phase1_5_backfill_classifier_correction"


def run_corp_actions_backfill(dry_run: bool = True) -> dict:
    """Audit (and, if dry_run=False, apply) corrections to every stored
    corporate_actions row. Always returns a full report dict; only mutates
    the DB when dry_run is explicitly False."""
    rows = repo.get_corporate_actions_for_backfill()
    now = dt.datetime.utcnow()

    updates: list[dict] = []
    hash_only_count = 0
    classification_corrected: list[dict] = []
    newly_unclassified: list[dict] = []

    for r in rows:
        new_type, new_impact, new_priority = classify_event(r["event_summary"])
        new_hash = dedupe_hash(r["symbol"], r["announcement_date"], r["event_summary"])
        hash_changed = new_hash != r["dedupe_hash"]

        if new_type is None:
            # Classifier no longer matches this stored text at all under
            # current rules (e.g. a keyword was narrowed away). Do NOT
            # overwrite event_type/impact_tag/priority with None — those
            # columns are NOT NULL and the row's existing classification is
            # still the best available answer. Flag for manual review only.
            newly_unclassified.append({
                "id": r["id"], "symbol": r["symbol"], "old_type": r["event_type"],
                "summary": r["event_summary"][:120],
            })
            if hash_changed:
                updates.append({"id": r["id"], "dedupe_hash": new_hash})
                hash_only_count += 1
            continue

        classification_changed = (
            new_type != r["event_type"] or new_impact != r["impact_tag"]
            or new_priority != r["priority"]
        )

        update = {"id": r["id"]}
        if hash_changed:
            update["dedupe_hash"] = new_hash
        if classification_changed:
            update.update({
                "event_type": new_type, "impact_tag": new_impact, "priority": new_priority,
                "original_event_type": r["event_type"], "original_impact_tag": r["impact_tag"],
                "reclassified_at": now, "reclassification_reason": REASON,
            })
            classification_corrected.append({
                "id": r["id"], "symbol": r["symbol"],
                "old": (r["event_type"], r["impact_tag"], r["priority"]),
                "new": (new_type, new_impact, new_priority),
                "summary": r["event_summary"][:120],
            })
        elif hash_changed:
            hash_only_count += 1

        if len(update) > 1:  # more than just "id"
            updates.append(update)

    report = {
        "dry_run": dry_run,
        "total_rows_scanned": len(rows),
        "hash_updates_total": sum(1 for u in updates if "dedupe_hash" in u),
        "hash_only_updates": hash_only_count,
        "classification_corrections": len(classification_corrected),
        "corrected_rows": classification_corrected,
        "newly_unclassified_under_current_rules": newly_unclassified,
    }

    if not dry_run:
        applied = repo.apply_corporate_action_corrections(updates)
        report["rows_written"] = applied

    return report
