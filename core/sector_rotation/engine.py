"""
Rule-based sector rotation engine.

For each tracked sector it computes, from real index/basket data:
  * 20-day performance (%)
  * relative strength vs Nifty (sector 20d return − Nifty 20d return)
  * trend status vs 20/50-day SMA + short-term acceleration

…then classifies into Strong / Improving / Neutral / Weak using transparent
threshold rules. No scores, no probabilities, no ML.

Classification rules
--------------------
  STRONG    : RS ≥ +rs_strong  AND above 20-SMA AND above 50-SMA
  WEAK      : RS ≤ −rs_weak     AND below 20-SMA AND below 50-SMA
  IMPROVING : not Strong, and momentum is turning up —
              (RS > 0) OR (recent 10d return > prior 10d return AND above 20-SMA)
  NEUTRAL   : everything else
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from core.config import (
    NIFTY_INDEX_TICKER,
    SECTOR_ROTATION as R,
    SECTORS,
)
from core.db import repository as repo
from core.processing import market_data
from core.utils.logging import get_logger

log = get_logger(__name__)


def _perf(series: pd.Series, lookback: int) -> float | None:
    if len(series) <= lookback:
        return None
    return (series.iloc[-1] / series.iloc[-1 - lookback] - 1) * 100


def _above_sma(series: pd.Series, period: int) -> str | None:
    if len(series) < period:
        return None
    return "Y" if series.iloc[-1] > series.iloc[-period:].mean() else "N"


def _accelerating(series: pd.Series, window: int) -> bool:
    if len(series) <= 2 * window:
        return False
    recent = series.iloc[-1] / series.iloc[-1 - window] - 1
    prior = series.iloc[-1 - window] / series.iloc[-1 - 2 * window] - 1
    return recent > prior


def _classify(rs: float | None, a20: str | None, a50: str | None,
              accel: bool) -> str:
    if rs is None:
        return "Neutral"
    if rs >= R["rs_strong_pct"] and a20 == "Y" and a50 == "Y":
        return "Strong"
    if rs <= R["rs_weak_pct"] and a20 == "N" and a50 == "N":
        return "Weak"
    if rs > 0 or (accel and a20 == "Y"):
        return "Improving"
    return "Neutral"


def run_sector_rotation(trade_date: dt.date) -> pd.DataFrame:
    """Classify all sectors for the trade date and persist. Returns the frame."""
    job_id = repo.start_job("sector_rotation", source="yfinance")
    try:
        lookback = R["perf_lookback_days"]
        nifty = market_data.get_close_series(NIFTY_INDEX_TICKER, days=90)
        nifty_perf = _perf(nifty, lookback)

        rows = []
        for sector, cfg in SECTORS.items():
            method = "index"
            series = pd.Series(dtype=float)
            if cfg.get("index"):
                series = market_data.get_close_series(cfg["index"], days=90)
                method = "proxy" if cfg.get("proxy") else "index"
            if series.empty or len(series) <= lookback:
                series = market_data.get_basket_series(cfg["basket"], days=90)
                method = "basket"
            if series.empty or len(series) <= lookback:
                log.warning("Sector %s: insufficient data, marked Neutral", sector)
                rows.append(_blank_row(trade_date, sector, nifty_perf))
                continue

            perf = _perf(series, lookback)
            rs = None if (perf is None or nifty_perf is None) else round(perf - nifty_perf, 2)
            a20 = _above_sma(series, R["sma_short"])
            a50 = _above_sma(series, R["sma_long"])
            accel = _accelerating(series, R["accel_lookback"])
            status = _classify(rs, a20, a50, accel)

            rows.append({
                "trade_date": trade_date, "sector": sector,
                "perf_20d": None if perf is None else round(perf, 2),
                "nifty_perf_20d": None if nifty_perf is None else round(nifty_perf, 2),
                "rs_vs_nifty": rs, "above_20_sma": a20, "above_50_sma": a50,
                "trend_status": status, "data_method": method,
            })

        repo.replace_sector_rotation(trade_date, rows)
        repo.finish_job(job_id, "ok", rows_in=len(SECTORS), rows_out=len(rows))
        df = repo.get_sector_rotation(trade_date)
        log.info("Sector rotation for %s: %s", trade_date,
                 df["trend_status"].value_counts().to_dict())
        return df
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("Sector rotation failed")
        raise


def _blank_row(trade_date: dt.date, sector: str, nifty_perf: float | None) -> dict:
    return {
        "trade_date": trade_date, "sector": sector, "perf_20d": None,
        "nifty_perf_20d": None if nifty_perf is None else round(nifty_perf, 2),
        "rs_vs_nifty": None, "above_20_sma": None, "above_50_sma": None,
        "trend_status": "Neutral", "data_method": "none",
    }
