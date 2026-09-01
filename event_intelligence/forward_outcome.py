"""
Incremental forward-outcome measurement — Phase 4 (validation research).

Deliberately NOT the same thing as `reaction_windows.py`'s cumulative
return_5d/return_10d/return_20d (all measured from the SAME pre-event
close). Those are what Phase 3 uses to CLASSIFY reaction_state/
continuation_state — reusing them again as the "subsequent outcome" for
this validation would be circular: a stock already up 8% by session 5
mechanically has a head start toward a positive cumulative session-10
return, which would look like "reaction predicts outcome" even if nothing
predictive is happening at all.

This module instead measures the return from the END of the classification
window (session +5, where reaction_state/continuation_state/event_alignment
are decided) to a LATER point (+10 or +20) — genuinely new information not
used anywhere in producing the classification. This is what "does an early
reaction predict subsequent, not overlapping, performance" actually
requires.

Look-ahead-bias boundary (see the Phase 4 report's LOOK-AHEAD-BIAS CHECK
for the full statement): the information boundary is session +5. Everything
at or before +5 may inform classification; everything measured here starts
strictly AFTER +5 and is never fed back into it.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from intelligence_v2.processors.shared_relative_strength import (
    performance_between_dates,
    position_at_or_after,
)


def compute_incremental_forward_return(price_df: pd.DataFrame, benchmark_close: pd.Series,
                                       announcement_date: dt.date,
                                       from_session: int, to_session: int) -> dict:
    """Return (and benchmark-relative return) from `from_session` sessions
    after the event's resolved day-0 to `to_session` sessions after it.
    None/None if either endpoint isn't available — never extrapolated.
    """
    if price_df.empty:
        return {"forward_return": None, "benchmark_forward_return": None,
               "relative_forward_return": None}

    close = price_df["close"]
    anchor_pos = position_at_or_after(close.index, announcement_date)
    if anchor_pos is None:
        return {"forward_return": None, "benchmark_forward_return": None,
               "relative_forward_return": None}

    from_pos = anchor_pos + from_session
    to_pos = anchor_pos + to_session
    if from_pos >= len(close) or to_pos >= len(close):
        return {"forward_return": None, "benchmark_forward_return": None,
               "relative_forward_return": None}

    from_close = close.iloc[from_pos]
    to_close = close.iloc[to_pos]
    if pd.isna(from_close) or pd.isna(to_close) or from_close <= 0:
        return {"forward_return": None, "benchmark_forward_return": None,
               "relative_forward_return": None}

    from_date = close.index[from_pos]
    to_date = close.index[to_pos]
    ret = round((to_close / from_close - 1) * 100, 4)
    bench_ret = (performance_between_dates(benchmark_close, from_date, to_date)
                if not benchmark_close.empty else None)
    rel_ret = round(ret - bench_ret, 4) if bench_ret is not None else None

    return {"forward_return": ret, "benchmark_forward_return": bench_ret,
           "relative_forward_return": rel_ret}
