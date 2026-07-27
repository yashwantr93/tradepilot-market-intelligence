"""
FiiDiiConnector — daily FII/FPI and DII cash-segment flows.

Live source (reachable): NSE provisional FII/DII JSON
    https://www.nseindia.com/api/fiidiiTradeReact
This endpoint exposes the most recent trading day only (two records: FII/FPI and
DII). Historical depth therefore accumulates forward as the pipeline runs daily.

OFFLINE_MODE (or a live failure) returns a deterministic seed row so the pipeline
still completes.

Resource: 'fii_dii'.
Returns one row: trade_date, fii_buy, fii_sell, fii_net, dii_buy, dii_sell, dii_net.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from core.config import OFFLINE_MODE
from core.connectors.base import BaseConnector, ConnectorError

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
_URL = "https://www.nseindia.com/api/fiidiiTradeReact"


class FiiDiiConnector(BaseConnector):
    name = "fiidii"
    source_type = "nse_json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_status = "unknown"

    def fetch(self, resource: str = "fii_dii", **params) -> pd.DataFrame:
        if resource != "fii_dii":
            raise ConnectorError(f"FiiDiiConnector: unknown resource '{resource}'")
        if OFFLINE_MODE:
            self.last_status = "offline"
            return self._seed()
        try:
            df = self._with_retries(self._fetch_live)
            self.last_status = "ok" if not df.empty else "empty"
            return df
        except ConnectorError:
            self.last_status = "fallback"
            self.log.warning("Live FII/DII failed; falling back to seed row")
            return self._seed()

    # -- live ---------------------------------------------------------------
    def _fetch_live(self) -> pd.DataFrame:
        import requests

        with requests.Session() as sess:
            sess.headers.update(_HEADERS)
            sess.get("https://www.nseindia.com", timeout=12)  # prime cookies
            resp = sess.get(_URL, timeout=12)
            resp.raise_for_status()
            payload = resp.json()
        return self._normalize(payload)

    @staticmethod
    def _normalize(payload: list[dict]) -> pd.DataFrame:
        rec = {"fii": None, "dii": None, "date": None}
        for row in payload:
            cat = str(row.get("category", "")).upper()
            vals = {
                "buy": float(str(row.get("buyValue", 0)).replace(",", "") or 0),
                "sell": float(str(row.get("sellValue", 0)).replace(",", "") or 0),
                "net": float(str(row.get("netValue", 0)).replace(",", "") or 0),
            }
            rec["date"] = row.get("date")
            if "FII" in cat or "FPI" in cat:
                rec["fii"] = vals
            elif "DII" in cat:
                rec["dii"] = vals
        if not rec["fii"] or not rec["dii"]:
            return pd.DataFrame()
        trade_date = dt.datetime.strptime(rec["date"], "%d-%b-%Y").date()
        return pd.DataFrame([{
            "trade_date": trade_date,
            "fii_buy": rec["fii"]["buy"], "fii_sell": rec["fii"]["sell"],
            "fii_net": rec["fii"]["net"],
            "dii_buy": rec["dii"]["buy"], "dii_sell": rec["dii"]["sell"],
            "dii_net": rec["dii"]["net"],
        }])

    @staticmethod
    def _seed() -> pd.DataFrame:
        return pd.DataFrame([{
            "trade_date": dt.date.today(),
            "fii_buy": 10000.0, "fii_sell": 10500.0, "fii_net": -500.0,
            "dii_buy": 12000.0, "dii_sell": 11000.0, "dii_net": 1000.0,
        }])
