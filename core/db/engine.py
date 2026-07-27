"""Engine / session factory and schema initialization."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import DATABASE_URL
from core.db.models import Base

_engine = create_engine(DATABASE_URL, future=True)
_SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create all tables if they do not exist (idempotent)."""
    Base.metadata.create_all(_engine)


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
