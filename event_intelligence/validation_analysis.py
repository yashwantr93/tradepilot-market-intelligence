"""
Event Reaction → Forward Outcome validation — Phase 4 (research only).

Answers: after a material event, do different reaction/alignment/
continuation states correspond to meaningfully different SUBSEQUENT
(session +5 -> +10 and +5 -> +20, non-overlapping with the classification
window) price outcomes?

This module does NOT persist a new production table and does NOT feed any
result back into `event_market_reaction`, `opportunity_hub`, or any other
consumer — it is a research/statistics tool, run on demand, whose output is
a DataFrame plus grouped summary statistics for a human to read. See the
Phase 4 report's hard boundary: no new trading signal this phase.

Reuses `event_intelligence.pipeline`'s existing price/benchmark loading
(same sanitization, same primitives) rather than re-deriving it — the only
new computation is `forward_outcome.compute_incremental_forward_return`.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from core.db import repository as repo
from event_intelligence.forward_outcome import compute_incremental_forward_return
from event_intelligence.pipeline import _load_benchmark, _load_clean_price_frame


def build_analysis_dataset() -> pd.DataFrame:
    """One row per event_market_reaction row that has a real (non-UNKNOWN)
    reaction_state, with incremental +5->+10 and +5->+20 forward outcomes
    attached. Rows without enough forward price history get None outcomes —
    never dropped silently, so sample-size accounting stays honest."""
    reactions = repo.get_event_market_reaction()
    if reactions.empty:
        return pd.DataFrame()

    classified = reactions[reactions["reaction_state"] != "UNKNOWN"].copy()
    if classified.empty:
        return classified

    benchmark_close = _load_benchmark()
    price_cache: dict[str, pd.DataFrame] = {}

    rows = []
    for _, r in classified.iterrows():
        symbol = r["symbol"]
        if symbol not in price_cache:
            price_cache[symbol] = _load_clean_price_frame(symbol)
        price_df = price_cache[symbol]

        adate = r["announcement_date"]
        if isinstance(adate, str):
            adate = dt.date.fromisoformat(adate)

        fwd_5_10 = compute_incremental_forward_return(price_df, benchmark_close, adate, 5, 10)
        fwd_5_20 = compute_incremental_forward_return(price_df, benchmark_close, adate, 5, 20)

        rows.append({
            "corporate_action_id": r["corporate_action_id"], "symbol": symbol,
            "event_type": r["event_type"], "impact_tag": r["impact_tag"],
            "reaction_state": r["reaction_state"], "continuation_state": r["continuation_state"],
            "event_alignment": r["event_alignment"],
            "relative_return_5d": r["relative_return_5d"],
            "forward_return_5_10": fwd_5_10["forward_return"],
            "relative_forward_return_5_10": fwd_5_10["relative_forward_return"],
            "forward_return_5_20": fwd_5_20["forward_return"],
            "relative_forward_return_5_20": fwd_5_20["relative_forward_return"],
        })
    return pd.DataFrame(rows)


def summarize_by_group(df: pd.DataFrame, group_col: str, outcome_col: str) -> pd.DataFrame:
    """N, mean, median, %positive, %negative for each value of `group_col`,
    using only rows where `outcome_col` is not None. Groups with N=0 are
    still listed (with N=0), never silently omitted — an absent group would
    read as "no data to report" when it's actually "zero events reached
    this state," a different and important fact."""
    if df.empty:
        return pd.DataFrame(columns=[group_col, "N", "mean", "median", "pct_positive", "pct_negative"])

    all_groups = sorted(df[group_col].dropna().unique())
    out = []
    for g in all_groups:
        sub = df[(df[group_col] == g) & df[outcome_col].notna()]
        n = len(sub)
        if n == 0:
            out.append({group_col: g, "N": 0, "mean": None, "median": None,
                       "pct_positive": None, "pct_negative": None})
            continue
        vals = sub[outcome_col]
        out.append({
            group_col: g, "N": n,
            "mean": round(vals.mean(), 3), "median": round(vals.median(), 3),
            "pct_positive": round((vals > 0).mean() * 100, 1),
            "pct_negative": round((vals < 0).mean() * 100, 1),
        })
    return pd.DataFrame(out)
