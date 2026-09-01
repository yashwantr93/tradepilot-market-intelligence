"""Engine / session factory and schema initialization."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from core.config import DATABASE_URL
from core.db.models import Base

_engine = create_engine(DATABASE_URL, future=True)
_SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)

# Phase 1.5 — columns added to a table that already holds production rows,
# so `create_all()` alone won't add them (it only creates missing tables).
# Each entry is (table, column, sql_type) for a plain, nullable ADD COLUMN —
# the only kind of migration this project needs so far; deliberately NOT a
# general migration framework (no Alembic) since this is the first and only
# case of it, per the Phase 1.5 "smallest appropriate change" brief.
_COLUMN_MIGRATIONS = [
    ("corporate_actions", "original_event_type", "VARCHAR"),
    ("corporate_actions", "original_impact_tag", "VARCHAR"),
    ("corporate_actions", "reclassified_at", "DATETIME"),
    ("corporate_actions", "reclassification_reason", "VARCHAR"),
]


def _run_column_migrations() -> None:
    """Idempotently ADD COLUMN for anything in _COLUMN_MIGRATIONS that a
    pre-existing table is missing. A no-op on a fresh DB (create_all already
    creates the column) and a no-op on a DB that's already been migrated."""
    inspector = inspect(_engine)
    for table, column, sql_type in _COLUMN_MIGRATIONS:
        if table not in inspector.get_table_names():
            continue  # brand-new DB — create_all() already added the column
        existing_cols = {c["name"] for c in inspector.get_columns(table)}
        if column in existing_cols:
            continue
        with _engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))


def init_db() -> None:
    """Create all tables if they do not exist, then apply any pending
    column migrations (both idempotent — safe to call on every startup)."""
    Base.metadata.create_all(_engine)
    _run_column_migrations()


def get_engine():
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session context: commit on success, rollback on error."""
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
