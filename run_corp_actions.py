"""
Corporate Actions runner — third independent watchlist source.

Ingests REAL NSE corporate announcements + structured corporate actions,
classifies each by transparent rules into event type / impact / priority, and
writes four artifacts under reports/:
  1. Corporate Action Watchlist CSV   (sorted High -> Medium -> Low)
  2. Daily Corporate Actions Report
  3. Validation Report
  4. Source Success/Failure Report

NO scoring · NO ML · NO prediction. Does not touch the other watchlist engines.

Usage:  python run_corp_actions.py
"""

from __future__ import annotations

import os

os.environ["MID_OFFLINE"] = "0"  # force live before importing core

from core import reports  # noqa: E402
from core.db import repository as repo  # noqa: E402
from core.db.engine import init_db  # noqa: E402
from core.pipelines.corp_actions_pipeline import run_corp_actions_ingestion  # noqa: E402
from core.utils.logging import get_logger  # noqa: E402
from core.utils.timeutils import latest_trading_day  # noqa: E402

log = get_logger("run_corp_actions")


def main() -> None:
    log.info("=== Corporate Actions run ===")
    init_db()

    stored, status, counts = run_corp_actions_ingestion()

    trade_date = repo.latest_corp_action_date() or latest_trading_day()
    # Watchlist = recent tracked actions (last 7 days window for the daily view).
    import datetime as dt
    df = repo.get_corporate_actions(since=trade_date - dt.timedelta(days=7))

    sources = [
        {"Source": "NSE corporate-announcements", "Method": "nse_json",
         "Status": _label(status.get("announcements", "?"))},
        {"Source": "NSE corporate-actions", "Method": "nse_json",
         "Status": _label(status.get("actions", "?"))},
    ]
    stats = {"raw": counts["raw"], "classified": counts["classified"],
             "stored": len(df)}

    csv_path, csv_rows = reports.export_corp_actions_csv(trade_date, df)
    report_path = reports.generate_corp_actions_report(trade_date, df)
    val_path = reports.generate_corp_actions_validation(trade_date, df, stats, sources)
    src_path = reports.generate_source_report(trade_date, sources)
    ca_src = src_path.replace("source_report_", "source_report_corp_actions_")
    os.replace(src_path, ca_src)

    high = int((df["priority"] == "High").sum()) if not df.empty else 0
    med = int((df["priority"] == "Medium").sum()) if not df.empty else 0
    low = int((df["priority"] == "Low").sum()) if not df.empty else 0

    print("\n".join([
        "",
        f"Trade date            : {trade_date}",
        f"Tracked CA events      : {len(df)}",
        f"  High / Medium / Low  : {high} / {med} / {low}",
        f"Watchlist CSV          : {csv_path} ({csv_rows} rows)",
        f"Daily report           : {report_path}",
        f"Validation report      : {val_path}",
        f"Source report          : {ca_src}",
    ]))


def _label(s: str) -> str:
    return {"ok": "OK", "empty": "EMPTY", "fallback": "FALLBACK",
            "offline": "OFFLINE"}.get(s, str(s).upper())


if __name__ == "__main__":
    main()
