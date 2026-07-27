"""
Signal Validation Layer runner.

Captures every watchlist entry from all five engines as a tracked signal, then
measures real 1/5/20-day forward returns and writes the Engine Performance report.

Pure measurement & feedback — NO scoring, NO ranking, NO prediction. Reads the
existing engine tables; does not modify any engine.

Prerequisite: run the engine pipelines first so their tables are populated:
    run_live.py · run_institutional.py · run_corp_actions.py · run_results.py · run_combined.py

Usage:  python run_validation.py
"""

from __future__ import annotations

import os

os.environ["MID_OFFLINE"] = "0"  # use real prices for forward returns

import datetime as dt  # noqa: E402

from core import reports  # noqa: E402
from core.db import repository as repo  # noqa: E402
from core.db.engine import init_db  # noqa: E402
from core.utils.logging import get_logger  # noqa: E402
from core.validation.signal_tracker import capture_signals, evaluate_signals  # noqa: E402

log = get_logger("run_validation")


def main() -> None:
    log.info("=== Signal Validation run ===")
    init_db()

    captured = capture_signals()
    if captured == 0:
        log.error("No signals captured. Run the engine pipelines first.")
        return

    stats = evaluate_signals()
    run_date = dt.date.today()

    report_path = reports.generate_signal_validation_report(run_date, stats)
    csv_path, csv_rows = reports.export_signals_csv(run_date)

    sig = repo.get_signals()
    per_engine = sig.groupby("source_engine").size().to_dict()

    print("\n".join([
        "",
        f"Signals tracked      : {stats.get('signals', 0)}",
        "  by engine          : " + ", ".join(f"{k}={v}" for k, v in per_engine.items()),
        f"Fully evaluated       : {stats.get('evaluated', 0)}",
        f"Partial               : {stats.get('partial', 0)}",
        f"No price              : {stats.get('no_price', 0)}",
        f"Engine report         : {report_path}",
        f"Signals CSV           : {csv_path} ({csv_rows} rows)",
    ]))


if __name__ == "__main__":
    main()
