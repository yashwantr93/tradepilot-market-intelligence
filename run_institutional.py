"""
Institutional Flow runner (FII/DII + Sector Rotation).

Builds the second, independent watchlist source from REAL data:
  * FII/DII flows      -> NSE provisional JSON (latest day, forward-accumulating)
  * Sector rotation    -> yfinance NSE sector indices / baskets (full history)
  * Institutional list -> stocks in Strong/Improving sectors (rule-based RS/trend)

Outputs under reports/:
  1. Daily Institutional Report
  2. Institutional Watchlist CSV
  3. Source Success/Failure Report (institutional)
  4. Validation summary (printed)

NO scoring · NO ML · NO prediction.

Usage:  python run_institutional.py
"""

from __future__ import annotations

import os

os.environ["MID_OFFLINE"] = "0"  # force live before importing core

import datetime as dt  # noqa: E402

from core import reports  # noqa: E402
from core.db import repository as repo  # noqa: E402
from core.db.engine import init_db  # noqa: E402
from core.pipelines.fiidii_pipeline import run_fiidii_ingestion  # noqa: E402
from core.sector_rotation.engine import run_sector_rotation  # noqa: E402
from core.utils.logging import get_logger  # noqa: E402
from core.utils.timeutils import latest_trading_day  # noqa: E402
from core.watchlist.institutional import build_institutional_watchlist  # noqa: E402

log = get_logger("run_institutional")


def main() -> None:
    log.info("=== Institutional Flow run ===")
    init_db()

    # 1) FII/DII flows (real, latest day).
    fii_rows, fii_status = run_fiidii_ingestion()
    flows = repo.get_fii_dii(limit=10)
    trade_date = flows["trade_date"].iloc[-1] if not flows.empty else latest_trading_day()

    # 2) Sector rotation (real, full history).
    rotation = run_sector_rotation(trade_date)

    # 3) Institutional watchlist (stocks in Strong/Improving sectors).
    n_inst = build_institutional_watchlist(trade_date, rotation)

    # 4) Reports.
    report_path = reports.generate_institutional_report(trade_date)
    csv_path, csv_rows = reports.export_institutional_csv(trade_date)

    strong = int((rotation["trend_status"] == "Strong").sum()) if not rotation.empty else 0
    improving = int((rotation["trend_status"] == "Improving").sum()) if not rotation.empty else 0
    weak = int((rotation["trend_status"] == "Weak").sum()) if not rotation.empty else 0
    neutral = int((rotation["trend_status"] == "Neutral").sum()) if not rotation.empty else 0

    sources = [
        {"Source": "NSE FII/DII JSON", "Method": "nse_json",
         "Status": _label(fii_status), "Rows": fii_rows},
        {"Source": "yfinance sector indices/baskets", "Method": "yfinance",
         "Status": "OK" if not rotation.empty else "FAIL", "Rows": len(rotation)},
    ]
    src_path = reports.generate_source_report(trade_date, sources)
    # rename so it doesn't clobber the deal-pipeline source report
    inst_src = src_path.replace("source_report_", "source_report_institutional_")
    os.replace(src_path, inst_src)

    val_stats = {
        "fii_rows": fii_rows, "history_days": len(flows),
        "strong_improving": strong + improving,
    }
    val_path = reports.generate_institutional_validation_report(
        trade_date, val_stats, sources)

    latest = flows.iloc[-1] if not flows.empty else None
    print("\n".join([
        "",
        f"Trade date              : {trade_date}",
        f"FII Net (Rs Cr)         : {latest['fii_net'] if latest is not None else 'NA'}",
        f"DII Net (Rs Cr)         : {latest['dii_net'] if latest is not None else 'NA'}",
        f"FII/DII history (days)   : {len(flows)}",
        f"Sectors  Strong/Improving/Neutral/Weak : {strong}/{improving}/{neutral}/{weak}",
        f"Institutional watchlist  : {n_inst} stocks",
        f"Institutional report     : {report_path}",
        f"Institutional CSV        : {csv_path} ({csv_rows} rows)",
        f"Source report            : {inst_src}",
        f"Validation report        : {val_path}",
    ]))


def _label(s: str) -> str:
    return {"ok": "OK", "empty": "EMPTY", "fallback": "FALLBACK",
            "offline": "OFFLINE"}.get(s, s.upper())


if __name__ == "__main__":
    main()
