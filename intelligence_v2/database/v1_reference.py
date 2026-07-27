"""
The V1 read-only bridge — THE ONLY place in the entire V2 codebase permitted
to open V1's database (data_store/market.db).

Enforcement is NOT a coding convention — it is enforced by SQLite itself:
the connection is opened with the URI `file:<path>?mode=ro`, which puts
SQLite into a mode where the OS-level file handle itself has no write access.
Any INSERT/UPDATE/DELETE/CREATE/ALTER attempted through this connection fails
with `sqlite3.OperationalError: attempt to write a readonly database`,
regardless of what Python code asks for it. There is no write method exposed
by this module at all — by construction, not just by omission.

Phase 0 provides only the generic bridge (connect, read, self-verify). Table-
specific convenience readers (e.g. "get V1's latest sector_rotation row") are
added by the modules that actually need them, in later phases — that is
business logic, and Phase 0 builds none.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from intelligence_v2.config.settings import V1_DB_PATH
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("v1_reference")


class V1BridgeError(Exception):
    """Raised when the read-only bridge to V1's database cannot be established."""


def _make_readonly_connection() -> sqlite3.Connection:
    """Open V1's database via SQLite's own read-only URI mode.

    This is the actual enforcement mechanism: `mode=ro` is a SQLite/OS-level
    flag, not an application convention. A write attempted through the
    resulting connection is rejected by SQLite itself.
    """
    uri = f"file:{V1_DB_PATH.as_posix()}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as e:
        raise V1BridgeError(
            f"Cannot open V1 database read-only at {V1_DB_PATH}: {e}"
        ) from e


def v1_database_exists() -> bool:
    return V1_DB_PATH.exists()


def get_v1_readonly_engine() -> Engine:
    """A SQLAlchemy engine whose every connection is SQLite-enforced read-only.

    NullPool is used deliberately: no connection is ever kept/reused past a
    single operation, so there is no path by which a pooled connection could
    be reused in an unexpected (write) context.
    """
    if not v1_database_exists():
        raise V1BridgeError(f"V1 database not found at {V1_DB_PATH}")
    return create_engine("sqlite://", creator=_make_readonly_connection, poolclass=NullPool)


@contextmanager
def v1_readonly_session() -> Iterator[sqlite3.Connection]:
    """Context-managed raw connection, guaranteed read-only, always closed."""
    conn = _make_readonly_connection()
    try:
        yield conn
    finally:
        conn.close()


def read_v1(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a read-only SQL query against V1's database. SELECT only in practice
    (any non-SELECT statement will simply fail — see module docstring)."""
    engine = get_v1_readonly_engine()
    return pd.read_sql_query(sql, engine, params=params or {})


def verify_read_only() -> tuple[bool, str]:
    """Self-test: prove writes are actually rejected, not just avoided.

    Attempts a harmless CREATE TABLE against V1's database through the bridge
    and expects SQLite to refuse it. Returns (is_read_only_enforced, detail).
    """
    try:
        with v1_readonly_session() as conn:
            conn.execute("CREATE TABLE __v2_write_probe__ (id INTEGER)")
            conn.commit()
        # If we reach here, the write SUCCEEDED — that is a critical failure.
        log.error("CRITICAL: write through the V1 bridge succeeded — read-only "
                  "enforcement is NOT working. Investigate immediately.")
        return False, "Write succeeded through the read-only bridge (should be impossible)."
    except sqlite3.OperationalError as e:
        if "readonly" in str(e).lower():
            log.info("V1 read-only bridge verified: write attempt correctly rejected (%s)", e)
            return True, f"Write correctly rejected by SQLite: {e}"
        log.warning("V1 bridge write attempt failed for an unexpected reason: %s", e)
        return False, f"Unexpected error (not a read-only rejection): {e}"
    except V1BridgeError as e:
        return False, f"Could not even open the bridge: {e}"


def verify_read_works() -> tuple[bool, str]:
    """Self-test: prove the bridge can actually read real V1 data."""
    from intelligence_v2.config.settings import V1_HEALTH_CHECK_TABLE

    try:
        df = read_v1(f"SELECT COUNT(*) AS n FROM {V1_HEALTH_CHECK_TABLE}")
        n = int(df["n"].iloc[0])
        return True, f"Read {V1_HEALTH_CHECK_TABLE}: {n} rows"
    except Exception as e:  # noqa: BLE001
        return False, f"Read failed: {e}"
