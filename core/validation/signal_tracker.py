"""
Signal capture + forward-return evaluation.

CAPTURE: reads the five engine tables and records one signal per watchlist entry
         (signal_date, symbol, source_engine, signal_type).
EVALUATE: for each signal, computes 1/5/20 trading-day forward returns from REAL
          daily closes (yfinance). Horizons whose window hasn't elapsed stay None
          (status 'pending'/'partial'). Pure measurement — no scoring/ML.

Results signals use the actual earnings ANNOUNCEMENT date (not quarter-end) so the
forward window reflects the post-results reaction.
"""

from __future__ import annotations

import datetime as dt
import warnings

import pandas as pd

from core.db import repository as repo
from core.utils.logging import get_logger

log = get_logger(__name__)

HORIZONS = {"ret_1d": 1, "ret_5d": 5, "ret_20d": 20}


# ---------------------------------------------------------------------------
# CAPTURE
# ---------------------------------------------------------------------------
def capture_signals() -> int:
    """Read all engine tables → signal rows. Returns number captured."""
    captured = 0
    captured += _capture_deal_flow()
    captured += _capture_institutional()
    captured += _capture_corp_actions()
    captured += _capture_results()
    captured += _capture_confluence()
    log.info("Captured %d signals across engines", captured)
    return captured


def _add(signal_date, symbol, engine, signal_type) -> int:
    if not symbol or pd.isna(signal_date):
        return 0
    repo.upsert_signal({
        "signal_date": signal_date, "symbol": str(symbol).strip().upper(),
        "source_engine": engine, "signal_type": signal_type,
        "entry_price": None, "ret_1d": None, "ret_5d": None, "ret_20d": None,
        "status": "pending",
    })
    return 1


def _capture_deal_flow() -> int:
    df = repo.get_watchlist()  # all dates
    n = 0
    for _, r in df.iterrows():
        n += _add(r["trade_date"], r["symbol"], "Deal Flow", r.get("catalyst_tag"))
    return n


def _capture_institutional() -> int:
    n = 0
    period = repo.latest_watchlist_date()
    if period is None:
        return 0
    df = repo.get_institutional_watchlist(period)
    for _, r in df.iterrows():
        n += _add(r["trade_date"] if "trade_date" in r else period, r["symbol"],
                  "Institutional Flow", r.get("sector_trend"))
    return n


def _capture_corp_actions() -> int:
    df = repo.get_corporate_actions()
    n = 0
    for _, r in df.iterrows():
        n += _add(r["announcement_date"], r["symbol"], "Corporate Actions",
                  r.get("event_type"))
    return n


def _capture_results() -> int:
    df = repo.get_results()
    if df.empty:
        return 0
    ann = _earnings_dates(df["symbol"].unique().tolist())
    n = 0
    for _, r in df.iterrows():
        sym = r["symbol"]
        signal_date = ann.get((sym, r["period_end"])) or r["period_end"]
        n += _add(signal_date, sym, "Results", r.get("result_classification"))
    return n


def _capture_confluence() -> int:
    period = repo.latest_watchlist_date()
    if period is None:
        return 0
    df = repo.get_combined_watchlist(period)
    n = 0
    for _, r in df.iterrows():
        n += _add(period, r["symbol"], "Confluence", f"Tier {r['tier']}")
    return n


def _earnings_dates(symbols: list[str]) -> dict:
    """Map (symbol, period_end) -> actual earnings announcement date via yfinance."""
    warnings.filterwarnings("ignore")
    import yfinance as yf

    out = {}
    for sym in symbols:
        try:
            ed = yf.Ticker(f"{sym}.NS").get_earnings_dates(limit=12)
            if ed is None or ed.empty:
                continue
            dates = sorted(pd.to_datetime(ed.index).date)
            # The announcement for a quarter ends ~0-75 days AFTER period end.
            # We attach below per period in the caller via closest match.
            out[sym] = dates
        except Exception:  # noqa: BLE001
            continue
    # Build (symbol, period_end) -> announcement date using each result's period.
    mapping = {}
    res = repo.get_results()
    for _, r in res.iterrows():
        sym, pe = r["symbol"], r["period_end"]
        cand = [d for d in out.get(sym, []) if 0 <= (d - pe).days <= 75]
        if cand:
            mapping[(sym, pe)] = min(cand)
    return mapping


# ---------------------------------------------------------------------------
# EVALUATE
# ---------------------------------------------------------------------------
def evaluate_signals() -> dict:
    """Fill 1/5/20d forward returns from real prices. Returns coverage stats."""
    sig = repo.get_signals()
    if sig.empty:
        return {"signals": 0, "evaluated": 0}

    symbols = sorted(sig["symbol"].unique())
    start = min(sig["signal_date"]) - dt.timedelta(days=10)
    closes = _download_closes(symbols, start)

    evaluated = partial = no_price = 0
    for _, r in sig.iterrows():
        series = closes.get(r["symbol"])
        if series is None or series.empty:
            repo.upsert_signal(_row(r, status="no_price"))
            no_price += 1
            continue
        entry_idx = _entry_index(series, r["signal_date"])
        if entry_idx is None:
            repo.upsert_signal(_row(r, status="no_price"))
            no_price += 1
            continue
        entry_price = float(series.iloc[entry_idx])
        rets, filled = {}, 0
        for col, k in HORIZONS.items():
            tgt = entry_idx + k
            if tgt < len(series):
                rets[col] = round((float(series.iloc[tgt]) / entry_price - 1) * 100, 2)
                filled += 1
            else:
                rets[col] = None
        status = "evaluated" if filled == len(HORIZONS) else (
            "partial" if filled > 0 else "pending")
        repo.upsert_signal(_row(r, entry_price=entry_price, status=status, **rets))
        if status == "evaluated":
            evaluated += 1
        elif status == "partial":
            partial += 1

    stats = {"signals": len(sig), "evaluated": evaluated, "partial": partial,
             "no_price": no_price}
    log.info("Evaluated signals: %s", stats)
    return stats


def _row(r, **overrides) -> dict:
    base = {
        "signal_date": r["signal_date"], "symbol": r["symbol"],
        "source_engine": r["source_engine"], "signal_type": r["signal_type"],
        "entry_price": r.get("entry_price"), "ret_1d": r.get("ret_1d"),
        "ret_5d": r.get("ret_5d"), "ret_20d": r.get("ret_20d"),
        "status": r.get("status", "pending"),
    }
    base.update(overrides)
    return base


def _entry_index(series: pd.Series, signal_date: dt.date) -> int | None:
    """First index on or after signal_date (next trading day if needed)."""
    for i, d in enumerate(series.index):
        if d >= signal_date:
            return i
    return None


def _download_closes(symbols: list[str], start: dt.date) -> dict[str, pd.Series]:
    warnings.filterwarnings("ignore")
    import yfinance as yf

    tickers = [f"{s}.NS" for s in symbols]
    out: dict[str, pd.Series] = {}
    try:
        raw = yf.download(tickers, start=start.isoformat(), progress=False,
                          auto_adjust=True, group_by="ticker", threads=True)
    except Exception as e:  # noqa: BLE001
        log.warning("price download failed: %s", e)
        return out
    for s in symbols:
        t = f"{s}.NS"
        try:
            if len(symbols) == 1:
                c = raw["Close"]
            elif t in raw.columns.get_level_values(0):
                c = raw[t]["Close"]
            else:
                continue
            c = c.dropna()
            if not c.empty:
                c.index = pd.to_datetime(c.index).date
                out[s] = c
        except Exception:  # noqa: BLE001
            continue
    return out
