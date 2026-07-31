"""
Optional, in-process daily-refresh scheduler.

Resolves the Render persistent-disk architecture question by construction:
Render disks attach to exactly one service, so the daily pipeline refresh
runs from WITHIN the same web service that serves the dashboard, instead of
a separate Render Cron Job service (which would need its own disk and
couldn't see this one). One service, one disk, one set of database files —
no cross-service sharing, no extra infrastructure.

Disabled by default (MID_ENABLE_SCHEDULER unset or "0") — the dashboard
behaves identically with the scheduler on or off, exactly as required. Local
development is completely unaffected: this module is imported by app.py but
never starts anything unless the env var is explicitly set.

Pure orchestration glue: it contains no trading logic, no ranking, no
filtering, no calculation. It only decides *when* to invoke the existing,
unmodified run_daily.py / run_daily_v2.py orchestrator scripts, exactly as
you would by hand.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent

# How often the background thread wakes up to check whether it's time to run.
_CHECK_INTERVAL_SECONDS = 15 * 60

# UTC time-of-day the daily refresh runs at, "HH:MM". Default 14:30 UTC =
# 20:00 IST, matching the existing Windows Task Scheduler's local schedule.
_REFRESH_TIME_UTC = os.environ.get("MID_SCHEDULER_UTC_TIME", "14:30")


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour_str, minute_str = value.split(":", 1)
    return int(hour_str), int(minute_str)


def _run_step(script: str, log) -> None:
    log.info("scheduler: starting %s", script)
    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / script)],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    if proc.returncode == 0:
        log.info("scheduler: %s completed OK", script)
    else:
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-10:]
        log.warning("scheduler: %s FAILED (exit %d):\n%s",
                   script, proc.returncode, "\n".join(tail))


def _loop() -> None:
    from core.utils.logging import get_logger
    log = get_logger("scheduler")
    target_hour, target_minute = _parse_hhmm(_REFRESH_TIME_UTC)
    last_run_date: dt.date | None = None
    log.info("scheduler: enabled, daily refresh target %s UTC", _REFRESH_TIME_UTC)

    while True:
        now = dt.datetime.utcnow()
        due = (
            last_run_date != now.date()
            and (now.hour, now.minute) >= (target_hour, target_minute)
        )
        if due:
            _run_step("run_daily.py", log)
            _run_step("run_daily_v2.py", log)
            last_run_date = now.date()
        time.sleep(_CHECK_INTERVAL_SECONDS)


@st.cache_resource
def _scheduler_thread() -> threading.Thread | None:
    """`st.cache_resource` runs this body exactly once per server process,
    no matter how many times Streamlit reruns app.py per user interaction —
    the correct Streamlit-idiomatic way to start exactly one background
    thread for the life of the process."""
    if os.environ.get("MID_ENABLE_SCHEDULER", "0") != "1":
        return None
    thread = threading.Thread(target=_loop, name="tradepilot-scheduler", daemon=True)
    thread.start()
    return thread


def start_if_enabled() -> bool:
    """Call once from app.py at startup. Returns whether the scheduler is
    running. Safe to call on every rerun — starts at most one thread."""
    return _scheduler_thread() is not None
