"""
Market-data helper for sector rotation (real data via yfinance).

Provides daily close series for an index ticker, or an equal-weighted rebased
series for a basket of stocks (used where no usable index exists, e.g. Defence).
Returns plain pandas Series indexed by date so the rotation engine stays simple.
"""

from __future__ import annotations

import warnings

import pandas as pd

from core.utils.logging import get_logger

log = get_logger(__name__)


def get_close_series(ticker: str, days: int = 90) -> pd.Series:
    """Daily close series for a single Yahoo ticker (empty Series on failure)."""
    warnings.filterwarnings("ignore")
    import yfinance as yf

    try:
        df = yf.download(ticker, period=f"{max(days, 80)}d", progress=False,
                         auto_adjust=True, threads=False)
        if df is None or df.empty:
            return pd.Series(dtype=float)
        s = df["Close"]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        s.index = pd.to_datetime(s.index).date
        return s.dropna()
    except Exception as e:  # noqa: BLE001
        log.debug("close series failed for %s: %s", ticker, e)
        return pd.Series(dtype=float)


def get_basket_series(symbols: list[str], days: int = 90) -> pd.Series:
    """Equal-weighted, rebased (=100) daily series for a basket of NSE stocks."""
    warnings.filterwarnings("ignore")
    import yfinance as yf

    tickers = [f"{s}.NS" for s in symbols]
    try:
        raw = yf.download(tickers, period=f"{max(days, 80)}d", progress=False,
                          auto_adjust=True, group_by="ticker", threads=True)
    except Exception as e:  # noqa: BLE001
        log.debug("basket fetch failed: %s", e)
        return pd.Series(dtype=float)

    cols = []
    for s in symbols:
        t = f"{s}.NS"
        try:
            if t in raw.columns.get_level_values(0):
                c = raw[t]["Close"].dropna()
                if not c.empty:
                    cols.append((c / c.iloc[0]) * 100)  # rebase to 100
        except Exception:  # noqa: BLE001
            continue
    if not cols:
        return pd.Series(dtype=float)
    basket = pd.concat(cols, axis=1).dropna(how="all")
    series = basket.mean(axis=1)  # equal-weighted
    series.index = pd.to_datetime(series.index).date
    return series.dropna()
