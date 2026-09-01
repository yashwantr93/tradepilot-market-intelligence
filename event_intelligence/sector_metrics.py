"""
Sector/theme breadth & relative-strength metrics — Phase 6. Pure
computation, no DB access. Reuses V2's `shared_relative_strength.py`
primitives per-constituent (no new date-alignment/RS math) — sector-level
relative strength here is the MEAN of constituent relative strengths, a
simple, transparent, and explainable aggregation, not a synthetic
sector-index price series (no such series exists for `symbol_master.sector`
categories — building one would require basket-rebasing logic this phase
doesn't need).
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from core.config import TECHNICALS as TECH_T
from intelligence_v2.processors.shared_relative_strength import (
    above_moving_average,
    rs_as_of,
)

RS_HORIZONS = {"1w": 5, "1m": 21, "3m": 63}
VOLUME_LOOKBACK = 20


def _volume_ratio(volume: pd.Series, as_of_pos: int) -> float | None:
    if as_of_pos - VOLUME_LOOKBACK < 0:
        return None
    window = volume.iloc[as_of_pos - VOLUME_LOOKBACK: as_of_pos]
    avg = window.mean()
    today = volume.iloc[as_of_pos]
    if pd.isna(avg) or avg <= 0 or pd.isna(today):
        return None
    return round(today / avg, 4)


def compute_constituent_metrics(close: pd.Series, volume: pd.Series | None,
                                benchmark_close: pd.Series, as_of: dt.date) -> dict | None:
    """Metrics for ONE constituent as of one date. None if the symbol has
    no price data at or before `as_of` at all."""
    if close.empty:
        return None
    pos = None
    for i, d in enumerate(close.index):
        if d <= as_of:
            pos = i
        else:
            break
    if pos is None:
        return None

    out = {"above_20sma": above_moving_average(close, as_of, TECH_T["sma_period"])}
    for label, lookback in RS_HORIZONS.items():
        _, _, rs = rs_as_of(close, benchmark_close, as_of, lookback)
        out[f"rs_{label}"] = rs
    out["volume_ratio"] = _volume_ratio(volume, pos) if volume is not None else None
    return out


def aggregate_sector_metrics(constituent_metrics: dict[str, dict]) -> dict:
    """`constituent_metrics` — {symbol: compute_constituent_metrics() result
    or None}. Aggregates only over symbols with a real (non-None) result —
    missing constituents reduce the denominator, they are never treated as
    "not participating" (that would silently conflate missing data with
    negative evidence)."""
    measurable = {s: m for s, m in constituent_metrics.items() if m is not None}
    n = len(measurable)
    if n == 0:
        return {
            "constituent_count": 0, "measurable_count": 0,
            "pct_above_20sma": None, "pct_positive_rs_1w": None, "pct_positive_rs_1m": None,
            "avg_rs_1w": None, "avg_rs_1m": None, "avg_rs_3m": None,
            "pct_volume_expansion": None,
        }

    def _pct(pred) -> float | None:
        vals = [pred(m) for m in measurable.values()]
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals) * 100, 2) if vals else None

    def _avg(key: str) -> float | None:
        vals = [m[key] for m in measurable.values() if m.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    return {
        "constituent_count": len(constituent_metrics), "measurable_count": n,
        "pct_above_20sma": _pct(lambda m: 1 if m["above_20sma"] == "Y" else 0
                                if m["above_20sma"] is not None else None),
        "pct_positive_rs_1w": _pct(lambda m: 1 if (m["rs_1w"] or 0) > 0 else 0
                                   if m["rs_1w"] is not None else None),
        "pct_positive_rs_1m": _pct(lambda m: 1 if (m["rs_1m"] or 0) > 0 else 0
                                   if m["rs_1m"] is not None else None),
        "avg_rs_1w": _avg("rs_1w"), "avg_rs_1m": _avg("rs_1m"), "avg_rs_3m": _avg("rs_3m"),
        "pct_volume_expansion": _pct(lambda m: 1 if (m["volume_ratio"] or 0) >= TECH_T["vol_expansion_mult"]
                                     else 0 if m["volume_ratio"] is not None else None),
    }
