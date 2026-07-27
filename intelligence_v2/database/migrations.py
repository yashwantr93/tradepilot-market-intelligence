"""
Schema-version tracking for market_v2.db.

Phase 0 establishes the pattern only: one row is inserted at version 1 the
first time init_db() runs. Future phases that need a schema change append a
new row (and, if a structural change is required, add real migration steps
here) — history is never mutated, only appended to.
"""

from __future__ import annotations

from sqlalchemy import select

from intelligence_v2.config.settings import CURRENT_SCHEMA_VERSION
from intelligence_v2.database.engine import session_scope
from intelligence_v2.models import SchemaVersion
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("database.migrations")

# Append-only history of what each schema version introduced.
_VERSION_NOTES = {
    1: "Phase 0 — Foundation (package skeleton, V2 DB, V1 read-only bridge, health checks).",
    2: "Phase 1 — Sector Intelligence (sector_intelligence_daily table).",
    3: "Phase 2 — Market Cycle Engine (market_cycle_daily + market_cycle_transitions).",
}


def ensure_schema_version() -> int:
    """Insert the current schema version row if not already present.

    Returns the latest recorded version number.
    """
    with session_scope() as s:
        existing = s.scalar(
            select(SchemaVersion).where(SchemaVersion.version == CURRENT_SCHEMA_VERSION)
        )
        if existing is None:
            s.add(SchemaVersion(
                version=CURRENT_SCHEMA_VERSION,
                description=_VERSION_NOTES.get(
                    CURRENT_SCHEMA_VERSION, f"Schema version {CURRENT_SCHEMA_VERSION}"),
            ))
            log.info("Recorded schema version %d", CURRENT_SCHEMA_VERSION)

        latest = s.scalar(
            select(SchemaVersion.version).order_by(SchemaVersion.version.desc()).limit(1)
        )
        return latest or 0


def get_latest_schema_version() -> int | None:
    with session_scope() as s:
        return s.scalar(
            select(SchemaVersion.version).order_by(SchemaVersion.version.desc()).limit(1)
        )
