"""
Results Tracker runner — fourth independent watchlist source.

Ingests REAL quarterly income statements (yfinance) across the universe,
computes YoY revenue/profit growth + margin change, classifies Strong/Neutral/Weak
by transparent rules, and writes four artifacts under reports/:
  1. Results Watchlist CSV     (sorted Strong -> Neutral -> Weak)
  2. Daily Results Report
  3. Validation Report
  4. Source Success/Failure Report

NO scoring · NO ML · NO prediction. Does not touch the other engines.

Usage:  python run_results.py
"""

from __future__ import annotations

import os

os.environ["MID_OFFLINE"] = "0"  # force live before importing core

from core import reports  # noqa: E402
from core.db import repository as repo  # noqa: E402
from core.db.engine import init_db  # noqa: E402
from core.pipelines.results_pipeline import run_results_ingestion  # noqa: E402
from core.utils.logging import get_logger  # noqa: E402
from core.utils.timeutils import latest_trading_day  # noqa: E402

log = get_logger("run_results")


def main() -> None:
    log.info("=== Results Tracker run ===")
    init_db()

    stored, counts = run_results_ingestion()
    period_end = repo.latest_results_period() or latest_trading_day()
    df = repo.get_results(period_end=period_end)

    sources = [{"Source": "yfinance quarterly income statements",
                "Method": "yfinance", "Status": "OK" if stored else "FAIL",
                "Rows": counts.get("with_data", 0)}]

    csv_path, csv_rows = reports.export_results_csv(period_end, df)
    report_path = reports.generate_results_report(period_end, df)
    val_path = reports.generate_results_validation(period_end, df, counts, sources)
    src_path = reports.generate_source_report(period_end, sources)
    res_src = src_path.replace("source_report_", "source_report_results_")
    os.replace(src_path, res_src)

    strong = int((df["result_classification"] == "Strong").sum()) if not df.empty else 0
    neutral = int((df["result_classification"] == "Neutral").sum()) if not df.empty else 0
    weak = int((df["result_classification"] == "Weak").sum()) if not df.empty else 0

    print("\n".join([
        "",
        f"Reporting period       : {period_end}",
        f"Universe processed      : {counts.get('processed', 0)}",
        f"With usable financials  : {counts.get('with_data', 0)}",
        f"Results stored          : {len(df)}",
        f"  Strong/Neutral/Weak   : {strong} / {neutral} / {weak}",
        f"Results watchlist CSV    : {csv_path} ({csv_rows} rows)",
        f"Daily report            : {report_path}",
        f"Validation report       : {val_path}",
        f"Source report           : {res_src}",
    ]))


if __name__ == "__main__":
    main()
