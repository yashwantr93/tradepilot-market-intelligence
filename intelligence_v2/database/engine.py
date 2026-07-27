"""
V2's own database engine (data_store/market_v2.db) — fully separate from V1's
engine (core/db/engine.py, market.db). Read-write, but only ever writes to
V2's own file; V1's file is never referenced here.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from intelligence_v2.config.settings import DATA_STORE_DIR, V2_DB_PATH
from intelligence_v2.models import Base
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("database.engine")

_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def get_v2_engine() -> Engine:
    """Lazily create the V2 engine (auto-creates data_store/ if missing)."""
    global _engine, _SessionFactory
    if _engine is None:
        DATA_STORE_DIR.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{V2_DB_PATH}", future=True)
        _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
        log.info("V2 engine initialized at %s", V2_DB_PATH)
    return _engine


def init_db() -> None:
    """Create every V2 table if missing (idempotent). Auto-creates the DB file
    and data_store/ directory on first run. Does not touch V1's database."""
    engine = get_v2_engine()
    Base.metadata.create_all(engine)
    log.info("V2 schema ensured (create_all complete) at %s", V2_DB_PATH)

    from intelligence_v2.database.migrations import ensure_schema_version
    ensure_schema_version()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional V2 session: commit on success, rollback on error."""
    if _SessionFactory is None:
        get_v2_engine()
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def v2_database_exists() -> bool:
    return V2_DB_PATH.exists()
