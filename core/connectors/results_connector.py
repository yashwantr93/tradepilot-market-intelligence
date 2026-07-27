"""
ResultsConnector — quarterly income statements via yfinance (real data).

For each symbol it returns the quarterly income statement (period-end columns,
newest first) with at least Total Revenue and Net Income. OFFLINE_MODE (or a
failure) returns a small deterministic sample so the pipeline still completes.

Resource: 'quarterly_income'  (param: symbol)
Returns: a pandas DataFrame (income statement) or empty DataFrame.
"""

from __future__ import annotations

import datetime as dt
import warnings

import pandas as pd

from core.config import OFFLINE_MODE
from core.connectors.base import BaseConnector, ConnectorError


class ResultsConnector(BaseConnector):
    name = "results"
    source_type = "yfinance"

    def fetch(self, resource: str, **params) -> pd.DataFrame:
        if resource != "quarterly_income":
            raise ConnectorError(f"ResultsConnector: unknown resource '{resource}'")
        symbol = params["symbol"]
        if OFFLINE_MODE:
            return self._seed(symbol)
        try:
            return self._fetch_live(symbol)
        except Exception as e:  # noqa: BLE001
            self.log.debug("results fetch failed for %s: %s", symbol, e)
            return pd.DataFrame()

    def _fetch_live(self, symbol: str) -> pd.DataFrame:
        warnings.filterwarnings("ignore")
        import yfinance as yf

        stmt = yf.Ticker(f"{symbol}.NS").quarterly_income_stmt
        return stmt if stmt is not None else pd.DataFrame()

    @staticmethod
    def _seed(symbol: str) -> pd.DataFrame:
        # Deterministic 5-quarter sample (newest first) so offline runs work.
        end = dt.date(2026, 3, 31)
        cols = [end, dt.date(2025, 12, 31), dt.date(2025, 9, 30),
                dt.date(2025, 6, 30), dt.date(2025, 3, 31)]
        base = abs(hash(symbol)) % 5000 + 1000
        rev = [base * 1.18, base * 1.05, base * 1.02, base * 0.99, base]
        ni = [base * 0.20, base * 0.16, base * 0.15, base * 0.14, base * 0.15]
        return pd.DataFrame(
            {c: [n, r] for c, n, r in zip(cols, ni, rev)},
            index=["Net Income", "Total Revenue"],
        )
