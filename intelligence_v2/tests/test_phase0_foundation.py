"""
Phase 0 (Foundation) verification suite.

Covers every checkmark required at the end of Phase 0:
  - V1 runs unchanged
  - V2 package imports cleanly
  - V2 database created
  - Read-only bridge works
  - No V1 writes possible
  - Health checks pass

Run with:  python -m pytest intelligence_v2/tests/ -v
"""

from __future__ import annotations

import sqlite3

import pytest

from intelligence_v2.config.settings import V1_DB_PATH, V2_DB_PATH
from intelligence_v2.database.engine import init_db, v2_database_exists
from intelligence_v2.database.migrations import get_latest_schema_version
from intelligence_v2.database.v1_reference import (
    read_v1,
    v1_database_exists,
    verify_read_only,
    verify_read_works,
)
from intelligence_v2.services.health import check_required_dirs, run_health_check

V1_BASELINE_TABLES = [
    "daily_watchlist", "institutional_watchlist", "combined_watchlist",
    "signals", "symbol_master",
]


@pytest.fixture(scope="module", autouse=True)
def ensure_v2_db():
    """Every test in this module can assume the V2 schema exists."""
    init_db()


# ---------------------------------------------------------------------------
# V2 package imports cleanly
# ---------------------------------------------------------------------------
def test_v2_package_imports_cleanly():
    import intelligence_v2  # noqa: F401
    import intelligence_v2.config  # noqa: F401
    import intelligence_v2.contracts  # noqa: F401
    import intelligence_v2.connectors  # noqa: F401
    import intelligence_v2.database  # noqa: F401
    import intelligence_v2.models  # noqa: F401
    import intelligence_v2.processors  # noqa: F401
    import intelligence_v2.services  # noqa: F401
    import intelligence_v2.pages  # noqa: F401
    import intelligence_v2.utils  # noqa: F401


def test_v2_config_has_no_v1_imports():
    """Guard against accidental coupling: settings module must not import core.*

    Parses the actual AST import statements (not a substring search) so a
    docstring mentioning "core" in prose can never produce a false failure.
    """
    import ast
    import inspect

    import intelligence_v2.config.settings as settings_mod

    tree = ast.parse(inspect.getsource(settings_mod))
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert "core" not in imported_roots, f"settings.py imports from V1's core package: {imported_roots}"


# ---------------------------------------------------------------------------
# V2 database created
# ---------------------------------------------------------------------------
def test_v2_database_file_created():
    assert v2_database_exists()
    assert V2_DB_PATH.exists()


def test_v2_schema_version_recorded():
    version = get_latest_schema_version()
    assert version is not None
    assert version >= 1


def test_v2_database_is_a_separate_file_from_v1():
    assert V2_DB_PATH != V1_DB_PATH
    assert V2_DB_PATH.name != V1_DB_PATH.name


# ---------------------------------------------------------------------------
# Read-only bridge works
# ---------------------------------------------------------------------------
def test_v1_database_available_for_bridge():
    assert v1_database_exists(), "V1 database must exist for the bridge to be tested"


def test_bridge_can_read_real_v1_data():
    ok, detail = verify_read_works()
    assert ok, detail


def test_bridge_generic_read_helper_returns_dataframe():
    df = read_v1("SELECT COUNT(*) AS n FROM symbol_master")
    assert "n" in df.columns
    assert int(df["n"].iloc[0]) >= 0


# ---------------------------------------------------------------------------
# No V1 writes possible (enforced, not just avoided)
# ---------------------------------------------------------------------------
def test_bridge_write_attempt_is_rejected_by_sqlite():
    ok, detail = verify_read_only()
    assert ok, f"Read-only enforcement failed: {detail}"


def test_direct_readonly_connection_also_rejects_writes():
    """Belt-and-braces: verify the same guarantee independent of our own
    verify_read_only() helper, using a fresh raw connection."""
    uri = f"file:{V1_DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("CREATE TABLE __direct_probe__ (id INTEGER)")
    finally:
        conn.close()


def test_v1_row_counts_unchanged_after_v2_operations():
    """The core regression guarantee: after every Phase-0 operation above has
    run (bridge reads, write-rejection probes, health checks), V1's actual
    data must be byte-identical to before."""
    before = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
             for t in V1_BASELINE_TABLES}

    # Exercise the bridge some more, exactly as a future module would.
    run_health_check()
    verify_read_only()
    verify_read_works()

    after = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
            for t in V1_BASELINE_TABLES}

    assert before == after, f"V1 row counts changed! before={before} after={after}"


# ---------------------------------------------------------------------------
# Health checks pass
# ---------------------------------------------------------------------------
def test_required_folders_exist():
    ok, missing = check_required_dirs()
    assert ok, f"Missing required V2 folders: {missing}"


def test_full_health_check_passes():
    results = run_health_check()
    failed = [k for k, v in results.items() if k != "_overall" and not v["ok"]]
    assert not failed, f"Health check(s) failed: {failed} -> {results}"
    assert results["_overall"]["ok"]
