"""
V2 daily orchestrator — runs every V2 intelligence engine pipeline in the
correct dependency order with one command, mirroring run_daily.py's exact
pattern for V1.

Pure ops/orchestration convenience. It does NOT contain any trading logic,
rules, scoring, or data-source code — it only invokes the existing runners
exactly as you would manually, in the required dependency order, and reports
pass/fail. Provides a single command a scheduler (cron, Task Scheduler, a
Render Cron Job) can call for the full V2 refresh.

    run_v2_sector_intelligence.py   (Phase 1 — requires V1's sector_rotation data)
    run_v2_market_cycle.py          (Phase 2 — requires Phase 1)
    run_v2_early_momentum.py        (Phase 3 — requires Phase 1 + 2)
    run_v2_bearish_opportunity.py   (Phase 4 — requires Phase 1 + 2)
    run_v2_position_opportunity.py  (Phase 5 — requires Phase 1 + 2 + 3)

Each step runs as its own subprocess (identical to running it by hand), so a
failure in one step is reported clearly rather than silently corrupting the
next step's state — though a failure in an earlier phase will generally cause
later phases to legitimately find "no context" rather than crash (each V2
service already handles missing upstream data gracefully).

Usage:
    python run_daily_v2.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# (script, description) in required dependency order.
PIPELINE = [
    ("run_v2_sector_intelligence.py", "Sector Intelligence (Phase 1)"),
    ("run_v2_market_cycle.py", "Market Cycle (Phase 2)"),
    ("run_v2_early_momentum.py", "Early Momentum (Phase 3)"),
    ("run_v2_bearish_opportunity.py", "Bearish Opportunity (Phase 4)"),
    ("run_v2_position_opportunity.py", "Position Opportunity (Phase 5)"),
]


def _run_step(script: str) -> tuple[bool, float, str]:
    """Run one pipeline script as a subprocess. Returns (ok, seconds, tail_output)."""
    start = time.time()
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / script)],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    elapsed = time.time() - start
    ok = proc.returncode == 0
    tail = (proc.stdout or "") + (proc.stderr or "")
    tail_lines = "\n".join(tail.strip().splitlines()[-6:])
    return ok, elapsed, tail_lines


def main() -> int:
    print(f"=== TradePilot AI — V2 Intelligence Stack — Daily Run "
          f"({len(PIPELINE)} steps) ===\n")

    results = []
    overall_start = time.time()
    for script, desc in PIPELINE:
        print(f"-> {desc} [{script}] ...", flush=True)
        ok, elapsed, tail = _run_step(script)
        status = "OK" if ok else "FAILED"
        print(f"   {status} ({elapsed:.1f}s)")
        if not ok:
            print("   --- last output ---")
            for line in tail.splitlines():
                print(f"   {line}")
            print("   --------------------")
        results.append((script, desc, ok, elapsed))
        print()

    total = time.time() - overall_start

    print("=== Summary ===")
    for script, desc, ok, elapsed in results:
        mark = "[OK]    " if ok else "[FAILED]"
        print(f"{mark} {desc:35s} {elapsed:6.1f}s")
    n_ok = sum(1 for *_r, ok, _e in results if ok)
    print(f"\n{n_ok}/{len(results)} V2 pipelines succeeded — total {total:.1f}s")

    if n_ok < len(results):
        print("\nOne or more V2 pipelines failed — the V2 dashboard pages will still "
              "show whatever data was already in market_v2.db (older / partial).")
    else:
        print("\nAll V2 pipelines succeeded. V2 data is fresh.")

    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
