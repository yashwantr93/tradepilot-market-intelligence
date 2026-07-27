"""
V2 Foundation health-check runner.

Initializes the V2 database (if missing) and runs every Phase-0 health check,
printing a clear pass/fail report. Never touches V1's database for writing.

Usage:
    python run_v2_healthcheck.py
"""

from __future__ import annotations

import sys

from intelligence_v2.database.engine import init_db
from intelligence_v2.services.health import run_health_check


def main() -> int:
    print("=== TradePilot AI V2 - Foundation Health Check ===\n")

    print("Ensuring V2 database schema exists...")
    init_db()
    print()

    results = run_health_check()

    order = [
        "v1_database_available",
        "v2_database_available",
        "read_only_bridge_working",
        "read_only_enforced",
        "required_folders_exist",
    ]
    for key in order:
        r = results[key]
        mark = "[PASS]" if r["ok"] else "[FAIL]"
        print(f"{mark} {key:28s} {r['detail']}")

    overall = results["_overall"]
    print()
    print(f"{'[PASS]' if overall['ok'] else '[FAIL]'} OVERALL: {overall['detail']}")

    return 0 if overall["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
