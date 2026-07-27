"""
Daily orchestrator — runs every engine pipeline in the correct order with one command.

Pure ops/orchestration convenience. It does NOT contain any trading logic, rules,
scoring, or data-source code — it only invokes the existing runners exactly as you
would manually, in the required dependency order, and reports pass/fail.

    run_live.py            (Deal Flow: bulk/block deals + technicals)
    run_institutional.py   (FII/DII + Sector Rotation + Institutional watchlist)
    run_corp_actions.py    (Corporate Actions)
    run_results.py          (Quarterly Results)
    run_combined.py         (Confluence: tiered combined watchlist)
    run_validation.py       (Signal capture + forward-return evaluation)

Each step runs as its own subprocess (identical to running it by hand), so a
failure in one step cannot corrupt another step's state. Steps after a failed
step still run where they don't hard-depend on it (e.g. Corporate Actions and
Results don't need Deal Flow to have succeeded).

Usage:
    python run_daily.py              # run all pipelines, then print next steps
    python run_daily.py --serve      # ...then launch the Streamlit dashboard
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# (script, description) in required order.
PIPELINE = [
    ("run_live.py", "Deal Flow - bulk/block deals + technicals"),
    ("run_institutional.py", "Institutional - FII/DII + Sector Rotation"),
    ("run_corp_actions.py", "Corporate Actions"),
    ("run_results.py", "Quarterly Results"),
    ("run_combined.py", "Combined Watchlist (confluence, tiered)"),
    ("run_validation.py", "Signal Validation (forward returns)"),
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
    ap = argparse.ArgumentParser(description="Run all engine pipelines in order")
    ap.add_argument("--serve", action="store_true",
                    help="Launch the Streamlit dashboard after the run")
    args = ap.parse_args()

    print(f"=== TradePilot AI - Market Intelligence Platform - Daily Run "
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
        print(f"{mark} {desc:45s} {elapsed:6.1f}s")
    n_ok = sum(1 for *_r, ok, _e in results if ok)
    print(f"\n{n_ok}/{len(results)} pipelines succeeded - total {total:.1f}s")

    if n_ok < len(results):
        print("\nOne or more pipelines failed - the dashboard will still show whatever "
              "data was already in the database (older / partial). Check the output "
              "above or logs/backend.log for details.")
    else:
        print("\nAll pipelines succeeded. Data is fresh.")

    print("\nNext step: streamlit run app.py")

    if args.serve:
        print("\nLaunching dashboard (Ctrl+C to stop) ...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"],
                       cwd=PROJECT_ROOT)

    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
