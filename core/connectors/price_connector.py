"""
PriceConnector — daily OHLCV history for the symbol universe.

Live path uses yfinance (NSE tickers as '<SYMBOL>.NS'); falls back to the
deterministic seed generator if yfinance is unavailable or returns nothing.
This is what feeds every technical field (20 SMA, RS, volume, 52w high).

Resource: 'history'  (params: symbols: list[str], days: int)
Returns columns: symbol, trade_date, open, high, low, close, volume.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from core.config import OFFLINE_MODE
from core.connectors.base import BaseConnector
from seed import seed_data


class PriceConnector(BaseConnector):
    name = "price"
    source_type = "yfinance|seed"

    def fetch(self, resource: str, **params) -> pd.DataFrame:
        days = int(params.get("days", 280))
        end = params.get("end") or dt.date.today()
        if OFFLINE_MODE:
            self.log.info("OFFLINE_MODE: generating seed price history (%d days)", days)
            return seed_data.get_price_history(days=days, end=end)
        try:
            symbols = params["symbols"]
            df = self._with_retries(self._fetch_yf, symbols, days)
            if df.empty:
                raise ValueError("yfinance returned empty")
            return df
        except Exception as e:  # noqa: BLE001
            self.log.warning("Live price fetch failed (%s); using seed history", e)
            return seed_data.get_price_history(days=days, end=end)

    def _fetch_yf(self, symbols: list[str], days: int) -> pd.DataFrame:
        import yfinance as yf

        tickers = [f"{s}.NS" for s in symbols] + ["^NSEI"]
        raw = yf.download(tickers, period=f"{max(days, 300)}d",
                          group_by="ticker", auto_adjust=True, progress=False, threads=True)
        frames = []
        for s in symbols:
            t = f"{s}.NS"
            if t not in raw.columns.get_level_values(0):
                continue
            sub = raw[t].dropna().reset_index()
            sub["symbol"] = s
            frames.append(sub.rename(columns={
                "Date": "trade_date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })[["symbol", "trade_date", "open", "high", "low", "close", "volume"]])
        # Benchmark mapped to NIFTY 50 name expected by config.BENCHMARK_SYMBOL.
        if "^NSEI" in raw.columns.get_level_values(0):
            b = raw["^NSEI"].dropna().reset_index()
            b["symbol"] = "NIFTY 50"
            frames.append(b.rename(columns={
                "Date": "trade_date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })[["symbol", "trade_date", "open", "high", "low", "close", "volume"]])
        if not frames:
            return pd.DataFrame()
        out = pd.concat(frames, ignore_index=True)
        out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
        out["volume"] = out["volume"].fillna(0).astype(int)
        return out
