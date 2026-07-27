"""
Sector lookup for the deal-driven universe (real data via yfinance .info).

Bulk/block deals reference arbitrary symbols, so sectors are resolved on demand.
Any failure falls back to "Unknown" — reported in the data-quality report.
"""

from __future__ import annotations

import warnings

from core.config import OFFLINE_MODE
from core.utils.logging import get_logger

log = get_logger(__name__)


def get_sectors(symbols: list[str]) -> dict[str, str]:
    """Return {symbol: sector}. 'Unknown' when unavailable."""
    out: dict[str, str] = {}
    if OFFLINE_MODE:
        return {s: "Unknown" for s in symbols}
    warnings.filterwarnings("ignore")
    import yfinance as yf

    for i, s in enumerate(symbols, 1):
        sector = "Unknown"
        try:
            info = yf.Ticker(f"{s}.NS").info
            sector = info.get("sector") or "Unknown"
        except Exception as e:  # noqa: BLE001
            log.debug("sector lookup failed for %s: %s", s, e)
        out[s] = sector
        if i % 10 == 0:
            log.info("Sector lookup %d/%d", i, len(symbols))
    return out
