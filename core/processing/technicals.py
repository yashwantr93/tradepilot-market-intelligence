"""
Rule-based technical fields for the watchlist.

NO scoring, NO prediction, NO ML — every field is a deterministic computation or
threshold on stored OHLCV. Outputs map 1:1 to the requested watchlist columns:
  current_price, above_20_sma (Y/N), relative_strength (Strong/Neutral/Weak),
  volume_expansion (Y/N), dist_52w_high_pct, technical_status (Ready/Monitor/Avoid).
"""

from __future__ import annotations

import pandas as pd

from core.config import BENCHMARK_SYMBOL, TECHNICALS as T
from core.db import repository as repo
from core.processing import price_metrics


def _benchmark_return(lookback: int) -> float | None:
    bench = repo.get_price_history(BENCHMARK_SYMBOL, lookback=lookback + 5)
    if bench.empty or len(bench) <= lookback:
        return None
    closes = bench["close"].to_numpy()
    return (closes[-1] / closes[-1 - lookback] - 1) * 100


def compute_technicals(symbol: str, benchmark_ret: float | None) -> dict:
    """Compute all technical fields for one symbol from its price history.

    Price metrics (price/SMA/52w high-low/distances) come from the shared
    ``price_metrics`` module so Deal Flow and Institutional pipelines stay
    identical; this function adds the deal-flow-specific RS / volume / status.
    """
    hist = repo.get_price_history(symbol, lookback=T["high_52w_lookback"] + 10)
    metrics = price_metrics.metrics_from_history(hist)
    if hist.empty:
        return {**metrics, "above_20_sma": "N", "relative_strength": "Neutral",
                "volume_expansion": "N", "technical_status": "Monitor"}

    close = hist["close"].to_numpy()
    volume = hist["volume"].to_numpy()
    current_price = metrics["current_price"]

    # --- Price above 20 SMA (reuse shared SMA value) -----------------------
    above_sma = "N"
    if metrics["sma_20"] is not None:
        above_sma = "Y" if current_price > metrics["sma_20"] else "N"

    # --- Relative strength vs benchmark ------------------------------------
    rs = "Neutral"
    rs_lb = T["rs_lookback_days"]
    if len(close) > rs_lb and benchmark_ret is not None:
        stock_ret = (close[-1] / close[-1 - rs_lb] - 1) * 100
        diff = stock_ret - benchmark_ret
        if diff >= T["rs_strong_outperf_pct"]:
            rs = "Strong"
        elif diff <= T["rs_weak_underperf_pct"]:
            rs = "Weak"

    # --- Volume expansion ---------------------------------------------------
    vol_exp = "N"
    vlb = T["vol_expansion_lookback"]
    if len(volume) > vlb:
        avg_vol = volume[-vlb - 1:-1].mean()
        if avg_vol > 0 and volume[-1] >= T["vol_expansion_mult"] * avg_vol:
            vol_exp = "Y"

    # --- Technical status (rule-based combination) -------------------------
    status = _technical_status(above_sma, rs, vol_exp, metrics["dist_52w_high_pct"])

    return {**metrics, "above_20_sma": above_sma, "relative_strength": rs,
            "volume_expansion": vol_exp, "technical_status": status}


def _technical_status(above_sma: str, rs: str, vol_exp: str,
                      dist_pct: float | None) -> str:
    """
    Ready  — uptrend & leadership: above 20 SMA, RS not Weak, and near 52w high
             OR confirming volume expansion.
    Avoid  — clear weakness: below 20 SMA and Weak RS.
    Monitor — everything in between.
    """
    near_high = dist_pct is not None and dist_pct <= T["ready_max_dist_52w_high"]
    if above_sma == "Y" and rs != "Weak" and (near_high or vol_exp == "Y"):
        return "Ready"
    if above_sma == "N" and rs == "Weak":
        return "Avoid"
    return "Monitor"


def benchmark_return(lookback: int | None = None) -> float | None:
    return _benchmark_return(lookback or T["rs_lookback_days"])
