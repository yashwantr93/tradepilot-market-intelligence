"""
Full daily orchestrator — Phase 11. Chains the THREE layers that together
make up "today's refresh," in the dependency order established across
Phases 1-10, so a scheduler needs to call exactly one command:

    1. run_daily.py       V1 (deal flow, institutional, corp actions,
                           results, combined watchlist, signal validation)
    2. run_daily_v2.py     V2 (sector intelligence -> market cycle ->
                           early momentum -> bearish/position opportunity;
                           requires V1's sector_rotation data, hence step 2)
    3. Event Intelligence  (market reaction -> trade signals -> sector/theme
                           -> cross-reference -> opportunity intelligence;
                           requires both V1 corp-actions/price history AND
                           V2's RS primitives, hence step 3)

Before Phase 11, no single script ran all three layers — run_daily.py only
ever covered V1, run_daily_v2.py only V2, and the five event_intelligence
runners had no orchestrator at all and had to be run manually, in the
correct order, every day. See the Phase 11 report's CURRENT REFRESH
ARCHITECTURE / DEPENDENCY FLOW sections for the full audit.

Pure ops/orchestration convenience, matching run_daily.py/run_daily_v2.py's
existing pattern exactly — no trading logic, no rules, no scoring. Each step
runs as its own subprocess so a failure in one cannot corrupt another
step's in-memory state; steps after a failed step still run (each engine
already handles missing/stale upstream data by finding "no context" rather
than crashing, per run_daily_v2.py's own docstring) so a single bad source
doesn't block the rest of the day's evidence accumulation.

Usage:
    python run_daily_all.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# (script, description) in required dependency order across all three layers.
PIPELINE = [
    ("run_daily.py", "V1 - Deal Flow / Institutional / Corp Actions / Results / Combined / Validation"),
    ("run_daily_v2.py", "V2 - Sector Intelligence / Market Cycle / Early Momentum / Bearish & Position Opportunity"),
    ("run_market_reaction.py", "Event Intelligence - Market Reaction"),
    ("run_trade_signals.py", "Event Intelligence - Trade Signals"),
    ("run_sector_theme.py", "Event Intelligence - Sector/Theme Emergence"),
    ("run_sector_stock_crossref.py", "Event Intelligence - Sector/Stock Cross-Reference"),
    ("run_opportunity_intelligence.py", "Event Intelligence - Opportunity Intelligence"),
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
    print(f"=== TradePilot AI - Full Daily Refresh (V1 -> V2 -> Event Intelligence, "
          f"{len(PIPELINE)} steps) ===\n")

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
        print(f"{mark} {desc:75s} {elapsed:7.1f}s")
    n_ok = sum(1 for *_r, ok, _e in results if ok)
    print(f"\n{n_ok}/{len(results)} steps succeeded - total {total:.1f}s")

    if n_ok < len(results):
        print("\nOne or more steps failed - downstream layers that depend on a failed "
              "step's output will find stale or missing upstream data rather than "
              "crash, so the dashboard will show a partial refresh, not a fresh one. "
              "Check the output above, or the job_runs audit trail (Settings page / "
              "data.contracts.refresh_status()) for exactly which layer is behind.")
    else:
        print("\nAll steps succeeded. V1, V2, and the Event Intelligence layer are "
              "all current as of this run.")

    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
