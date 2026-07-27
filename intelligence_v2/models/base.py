"""
Shared declarative base + schema-version bookkeeping table.

This is the only table Phase 0 creates. It exists purely so schema upgrades
are trackable later (requirement: "migration/version tracking") — it carries
no business logic and no calculations.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base every V2 table subclasses (separate from V1's Base)."""


class SchemaVersion(Base):
    """Single-row-per-version history of the V2 database schema.

    `intelligence_v2.database.migrations.ensure_schema_version()` inserts the
    initial row on first run and is the extension point for future upgrades:
    each future migration appends a new row rather than mutating history.
    """

    __tablename__ = "schema_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    applied_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    description: Mapped[str] = mapped_column(String)
