"""
Shared price-metric calculations — the single source of truth for the price-based
fields used across pipelines. Both the Deal Flow technicals and the Institutional
pipeline call this module so the numbers are computed identically (no duplication).

Metrics (deterministic, from stored OHLCV — NO scoring/ML):
    current_price · sma_20 · high_52w · low_52w
    dist_52w_high_pct · dist_52w_low_pct
"""

from __future__ import annotations

import pandas as pd

from core.config import TECHNICALS as T
from core.db import repository as repo

FIELDS = ("current_price", "sma_20", "high_52w", "low_52w",
          "dist_52w_high_pct", "dist_52w_low_pct")

_BLANK = {f: None for f in FIELDS}


def metrics_from_history(hist: pd.DataFrame) -> dict:
    """Compute the price metrics from a symbol's OHLCV history DataFrame."""
    if hist is None or hist.empty:
        return dict(_BLANK)

    close = hist["close"].to_numpy()
    current_price = float(close[-1])

    sma_p = T["sma_period"]
    sma_20 = round(float(close[-sma_p:].mean()), 2) if len(close) >= sma_p else None

    hi_lb = min(T["high_52w_lookback"], len(close))
    high_52w = round(float(hist["high"].to_numpy()[-hi_lb:].max()), 2)
    low_52w = round(float(hist["low"].to_numpy()[-hi_lb:].min()), 2)

    dist_high = round((high_52w - current_price) / high_52w * 100, 2) if high_52w else None
    dist_low = round((current_price - low_52w) / low_52w * 100, 2) if low_52w else None

    return {
        "current_price": round(current_price, 2),
        "sma_20": sma_20,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "dist_52w_high_pct": dist_high,
        "dist_52w_low_pct": dist_low,
    }


def compute_price_metrics(symbol: str) -> dict:
    """Load a symbol's stored OHLCV and compute its price metrics."""
    hist = repo.get_price_history(symbol, lookback=T["high_52w_lookback"] + 10)
    return metrics_from_history(hist)
