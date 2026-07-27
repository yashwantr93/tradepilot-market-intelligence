"""
Institutional watchlist — the second, independent candidate source.

Takes the sectors classified Strong/Improving by the rotation engine, pulls their
basket constituents, and tags each with rule-based relative strength and 20-SMA
trend. No scores, no predictions — a transparent "where institutions are likely
rotating" research list that complements the bulk/block-deal watchlist.
"""

from __future__ import annotations

import datetime as dt
import warnings

import pandas as pd

from core.config import INSTITUTIONAL as I, NIFTY_INDEX_TICKER, SECTORS
from core.db import repository as repo
from core.pipelines.price_pipeline import run_price_ingestion
from core.processing.price_metrics import FIELDS as PM_FIELDS, compute_price_metrics
from core.utils.logging import get_logger

log = get_logger(__name__)


def _rs_label(stock_ret: float, bench_ret: float) -> str:
    diff = stock_ret - bench_ret
    if diff >= I["rs_strong_outperf_pct"]:
        return "Strong"
    if diff <= I["rs_weak_underperf_pct"]:
        return "Weak"
    return "Neutral"


def build_institutional_watchlist(trade_date: dt.date,
                                  rotation: pd.DataFrame) -> int:
    """Build & persist the institutional watchlist. Returns row count."""
    job_id = repo.start_job("institutional_watchlist", source="rules")
    try:
        if rotation.empty:
            repo.finish_job(job_id, "ok", rows_out=0)
            return 0

        target = rotation[rotation["trend_status"].isin(I["include_trends"])]
        sector_trend = dict(zip(target["sector"], target["trend_status"]))
        if not sector_trend:
            log.info("No Strong/Improving sectors — institutional watchlist empty")
            repo.replace_institutional_watchlist(trade_date, [])
            repo.finish_job(job_id, "ok", rows_out=0)
            return 0

        # Unique basket symbols across qualifying sectors.
        sym_sector = {}
        for sector in sector_trend:
            for sym in SECTORS[sector]["basket"]:
                sym_sector.setdefault(sym, sector)
        symbols = list(sym_sector.keys())

        prices = _download_closes(symbols)
        nifty = _download_closes(["__NIFTY__"], nifty=True).get("__NIFTY__")
        lb = I["rs_lookback_days"]
        bench_ret = _ret(nifty, lb)

        # Data-completeness: ingest full OHLCV for this universe into price_history
        # so the SHARED price-metrics module can compute the same fields the Deal
        # Flow pipeline stores (current_price, 20-SMA, 52w high/low, distances).
        try:
            run_price_ingestion(days=400, end=trade_date, symbols=symbols)
        except Exception as e:  # noqa: BLE001 - metrics are enrichment, never fatal
            log.warning("Price-history ingestion for institutional metrics failed: %s", e)

        rows = []
        for sym in symbols:
            s = prices.get(sym)
            if s is None or len(s) <= lb:
                continue
            stock_ret = _ret(s, lb)
            rs = _rs_label(stock_ret, bench_ret) if bench_ret is not None else "Neutral"
            above20 = "Y" if s.iloc[-1] > s.iloc[-20:].mean() else "N"
            sector = sym_sector[sym]
            metrics = compute_price_metrics(sym)  # shared logic from price_history
            row = {
                "trade_date": trade_date, "symbol": sym, "sector": sector,
                "sector_trend": sector_trend[sector],
                "relative_strength": rs, "above_20_sma": above20,
            }
            # current_price + sma_20 + 52w high/low + distances (identical logic).
            for f in PM_FIELDS:
                row[f] = metrics[f]
            rows.append(row)

        # Sort: Strong sectors first, then strong-RS stocks.
        trend_rank = {"Strong": 0, "Improving": 1}
        rs_rank = {"Strong": 0, "Neutral": 1, "Weak": 2}
        rows.sort(key=lambda x: (trend_rank.get(x["sector_trend"], 9),
                                 rs_rank.get(x["relative_strength"], 9)))
        n = repo.replace_institutional_watchlist(trade_date, rows)
        repo.finish_job(job_id, "ok", rows_in=len(symbols), rows_out=n)
        log.info("Institutional watchlist: %d stocks from %d Strong/Improving sectors",
                 n, len(sector_trend))
        return n
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("Institutional watchlist failed")
        raise


def _ret(series: pd.Series | None, lookback: int) -> float | None:
    if series is None or len(series) <= lookback:
        return None
    return (series.iloc[-1] / series.iloc[-1 - lookback] - 1) * 100


def _download_closes(symbols: list[str], nifty: bool = False) -> dict[str, pd.Series]:
    warnings.filterwarnings("ignore")
    import yfinance as yf

    tickers = [NIFTY_INDEX_TICKER] if nifty else [f"{s}.NS" for s in symbols]
    out: dict[str, pd.Series] = {}
    try:
        raw = yf.download(tickers, period="90d", progress=False, auto_adjust=True,
                          group_by="ticker", threads=True)
    except Exception as e:  # noqa: BLE001
        log.debug("institutional price fetch failed: %s", e)
        return out
    if nifty:
        try:
            c = raw["Close"] if "Close" in raw.columns else raw[NIFTY_INDEX_TICKER]["Close"]
            if isinstance(c, pd.DataFrame):
                c = c.iloc[:, 0]
            out["__NIFTY__"] = c.dropna()
        except Exception:  # noqa: BLE001
            pass
        return out
    for s in symbols:
        t = f"{s}.NS"
        try:
            if t in raw.columns.get_level_values(0):
                c = raw[t]["Close"].dropna()
                if not c.empty:
                    out[s] = c
        except Exception:  # noqa: BLE001
            continue
    return out
