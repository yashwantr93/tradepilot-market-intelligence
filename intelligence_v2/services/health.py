"""
V2 foundation health check.

Verifies every Phase-0 requirement in one pass:
  - V1 database available
  - V2 database available
  - Read-only bridge working (can read V1 data)
  - Read-only bridge enforced (a write attempt is actually rejected)
  - Required folders exist

Returns a plain dict — no Streamlit, no business logic. Run standalone via
run_v2_healthcheck.py at the project root.
"""

from __future__ import annotations

from intelligence_v2.config.settings import REQUIRED_DIRS
from intelligence_v2.database.engine import v2_database_exists
from intelligence_v2.database.v1_reference import (
    v1_database_exists,
    verify_read_only,
    verify_read_works,
)
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("services.health")


def check_required_dirs() -> tuple[bool, list[str]]:
    missing = [str(p) for p in REQUIRED_DIRS if not p.exists()]
    return (len(missing) == 0), missing


def run_health_check() -> dict:
    """Run every Phase-0 health check and return a structured result."""
    results: dict[str, dict] = {}

    # 1. V1 database available
    v1_ok = v1_database_exists()
    results["v1_database_available"] = {
        "ok": v1_ok,
        "detail": "Found" if v1_ok else "V1 database file not found (V2 cannot proceed)",
    }

    # 2. V2 database available
    v2_ok = v2_database_exists()
    results["v2_database_available"] = {
        "ok": v2_ok,
        "detail": "Found" if v2_ok else "Not yet created — run init_db() first",
    }

    # 3 & 4. Read-only bridge: can it read, and is a write actually rejected?
    if v1_ok:
        read_ok, read_detail = verify_read_works()
        write_rejected_ok, write_detail = verify_read_only()
    else:
        read_ok, read_detail = False, "Skipped — V1 database not available"
        write_rejected_ok, write_detail = False, "Skipped — V1 database not available"

    results["read_only_bridge_working"] = {"ok": read_ok, "detail": read_detail}
    results["read_only_enforced"] = {"ok": write_rejected_ok, "detail": write_detail}

    # 5. Required folders
    dirs_ok, missing_dirs = check_required_dirs()
    results["required_folders_exist"] = {
        "ok": dirs_ok,
        "detail": "All present" if dirs_ok else f"Missing: {missing_dirs}",
    }

    overall = all(r["ok"] for r in results.values())
    results["_overall"] = {"ok": overall, "detail": "All checks passed" if overall else "One or more checks failed"}

    log.info("Health check: overall=%s", overall)
    return results
