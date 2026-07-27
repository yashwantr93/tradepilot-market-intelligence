"""
CorpActionsConnector — NSE corporate announcements + structured corporate actions.

Live sources (both reachable):
    https://www.nseindia.com/api/corporate-announcements?index=equities   (free-text)
    https://www.nseindia.com/api/corporates-corporateActions?index=equities (structured)

The announcements feed carries order wins / M&A / management changes / approvals
(classified from text); the corporate-actions feed carries dividend / bonus /
split / rights / buyback (with ex-dates). Both are normalized to a common shape.

OFFLINE_MODE (or a live failure) returns a deterministic sample covering all
tracked event types so the pipeline always completes.

Resources: 'announcements', 'actions'.
Returns columns: date, symbol, company_name, raw_text, source.
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
_URL = {
    "announcements": "https://www.nseindia.com/api/corporate-announcements?index=equities",
    "actions": "https://www.nseindia.com/api/corporates-corporateActions?index=equities",
}
_COLUMNS = ["date", "symbol", "company_name", "raw_text", "source"]


class CorpActionsConnector(BaseConnector):
    name = "corp_actions"
    source_type = "nse_json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_status = "unknown"

    def fetch(self, resource: str, **params) -> pd.DataFrame:
        if resource not in _URL:
            raise ConnectorError(f"CorpActionsConnector: unknown resource '{resource}'")
        if OFFLINE_MODE:
            self.last_status = "offline"
            return self._seed(resource)
        try:
            df = self._with_retries(self._fetch_live, resource)
            self.last_status = "ok" if not df.empty else "empty"
            self.log.info("NSE %s: %d rows", resource, len(df))
            return df
        except ConnectorError:
            self.last_status = "fallback"
            self.log.warning("Live %s failed; using sample", resource)
            return self._seed(resource)

    # -- live ---------------------------------------------------------------
    def _fetch_live(self, resource: str) -> pd.DataFrame:
        import requests

        with requests.Session() as sess:
            sess.headers.update(_HEADERS)
            sess.get("https://www.nseindia.com", timeout=12)
            resp = sess.get(_URL[resource], timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        return (self._normalize_announcements(payload) if resource == "announcements"
                else self._normalize_actions(payload))

    @staticmethod
    def _normalize_announcements(payload: list[dict]) -> pd.DataFrame:
        rows = []
        for a in payload:
            date = _parse_date(a.get("sort_date") or a.get("an_dt"))
            text = " ".join(str(a.get(k, "")) for k in ("desc", "attchmntText"))
            rows.append({
                "date": date, "symbol": a.get("symbol", ""),
                "company_name": a.get("sm_name", ""), "raw_text": text.strip(),
                "source": "NSE_ANN",
            })
        return pd.DataFrame(rows, columns=_COLUMNS)

    @staticmethod
    def _normalize_actions(payload: list[dict]) -> pd.DataFrame:
        rows = []
        for c in payload:
            date = _parse_date(c.get("exDate") or c.get("recDate"))
            rows.append({
                "date": date, "symbol": c.get("symbol", ""),
                "company_name": c.get("comp", ""),
                "raw_text": str(c.get("subject", "")), "source": "NSE_CA",
            })
        return pd.DataFrame(rows, columns=_COLUMNS)

    # -- offline sample -----------------------------------------------------
    @staticmethod
    def _seed(resource: str) -> pd.DataFrame:
        today = dt.date.today()
        if resource == "announcements":
            samples = [
                ("LT", "Larsen & Toubro Ltd", "Bagging/Receiving of orders - bags order worth Rs 15000 Cr"),
                ("HDFCBANK", "HDFC Bank Ltd", "Acquisition of stake in fintech NBFC - scheme of arrangement"),
                ("SUNPHARMA", "Sun Pharma", "Received approval from USFDA for new drug"),
                ("INFY", "Infosys Ltd", "Resignation of Chief Financial Officer"),
                ("YESBANK", "Yes Bank", "Fund raising via QIP of Rs 5000 Cr"),
                ("TATAMOTORS", "Tata Motors", "Preferential allotment of equity shares"),
            ]
        else:
            samples = [
                ("TCS", "Tata Consultancy Services", "Buy Back of Shares"),
                ("INFY", "Infosys Ltd", "Bonus 1:1"),
                ("ITC", "ITC Ltd", "Dividend - Rs 7.50 Per Share"),
                ("VEDL", "Vedanta Ltd", "Rights Issue"),
                ("DMART", "Avenue Supermarts", "Face Value Split from 10 to 2"),
            ]
        return pd.DataFrame(
            [{"date": today, "symbol": s, "company_name": c, "raw_text": t,
              "source": "NSE_ANN" if resource == "announcements" else "NSE_CA"}
             for s, c, t in samples],
            columns=_COLUMNS,
        )


def _parse_date(value) -> dt.date:
    """Parse the various NSE date formats; default to today on failure."""
    if not value or str(value).strip() in ("-", "None"):
        return dt.date.today()
    s = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return dt.date.today()
