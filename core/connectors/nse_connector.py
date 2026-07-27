"""
NSEConnector — real bulk/block deals via the NSE public archive CSVs.

Live source (reachable without the blocked JSON API):
    https://archives.nseindia.com/content/equities/bulk.csv
    https://archives.nseindia.com/content/equities/block.csv
These files hold the most recent trading day's deals. The connector parses the
real CSV format and returns normalized rows tagged with the file's own date.

If OFFLINE_MODE is on, or the live fetch fails, it returns deterministic seed
deals so the pipeline always completes.

Resources: 'bulk_deals', 'block_deals'.
Returns columns: trade_date, exchange, symbol, client_name, txn_type, quantity, price.
"""

from __future__ import annotations

import datetime as dt
import io

import pandas as pd

from core.config import OFFLINE_MODE
from core.connectors.base import BaseConnector, ConnectorError
from seed import seed_data

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/csv,*/*",
}
_ARCHIVE = {
    "bulk_deals": "https://archives.nseindia.com/content/equities/bulk.csv",
    "block_deals": "https://archives.nseindia.com/content/equities/block.csv",
}


class NSEConnector(BaseConnector):
    name = "nse"
    source_type = "archive_csv"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_status = "unknown"  # ok / empty / fallback / offline

    def fetch(self, resource: str, **params) -> pd.DataFrame:
        if resource not in _ARCHIVE:
            raise ConnectorError(f"NSEConnector: unknown resource '{resource}'")
        kind = "bulk" if resource == "bulk_deals" else "block"

        if OFFLINE_MODE:
            trade_date = params.get("trade_date") or dt.date.today()
            self.log.info("OFFLINE_MODE: serving seed %s for %s", resource, trade_date)
            self.last_status = "offline"
            return seed_data.get_sample_deals(trade_date, kind)

        try:
            df = self._with_retries(self._fetch_archive, resource)
            self.last_status = "ok" if not df.empty else "empty"
            self.log.info("NSE archive %s: %d rows (%s)", resource, len(df),
                          df["trade_date"].iloc[0] if not df.empty else "no rows")
            return df
        except ConnectorError:
            fallback_date = params.get("trade_date") or dt.date.today()
            self.last_status = "fallback"
            self.log.warning("Live %s failed; falling back to seed data", resource)
            return seed_data.get_sample_deals(fallback_date, kind)

    # -- live ---------------------------------------------------------------
    def _fetch_archive(self, resource: str) -> pd.DataFrame:
        import requests  # local import so offline runs need no network stack

        resp = requests.get(_ARCHIVE[resource], headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        return self._normalize_archive(resp.text)

    @staticmethod
    def _normalize_archive(text: str) -> pd.DataFrame:
        cols = ["trade_date", "exchange", "symbol", "client_name",
                "txn_type", "quantity", "price"]
        raw = pd.read_csv(io.StringIO(text))
        raw.columns = [c.strip() for c in raw.columns]
        # Archive uses "NO RECORDS" sentinel rows on empty days.
        raw = raw[raw["Symbol"].notna()]
        raw = raw[~raw["Symbol"].astype(str).str.upper().str.contains("NO RECORD")]
        if raw.empty:
            return pd.DataFrame(columns=cols)

        out = pd.DataFrame()
        out["trade_date"] = pd.to_datetime(raw["Date"].str.strip(),
                                           format="%d-%b-%Y", errors="coerce").dt.date
        out["exchange"] = "NSE"
        out["symbol"] = raw["Symbol"].astype(str).str.strip().str.upper()
        out["client_name"] = raw["Client Name"].astype(str).str.strip()
        out["txn_type"] = raw["Buy/Sell"].astype(str).str.strip().str.upper().map(
            lambda x: "BUY" if x.startswith("B") else "SELL")
        out["quantity"] = pd.to_numeric(
            raw["Quantity Traded"].astype(str).str.replace(",", ""), errors="coerce")
        out["price"] = pd.to_numeric(
            raw["Trade Price / Wght. Avg. Price"].astype(str).str.replace(",", ""),
            errors="coerce")
        return out.dropna(subset=["trade_date", "quantity", "price"])[cols]
