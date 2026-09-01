"""
Event-relative reaction measurement — pure computation, no DB access.

Reuses V2's calendar-aligned primitives (`intelligence_v2.processors.
shared_relative_strength`) rather than re-deriving date-alignment logic —
see `event_intelligence/__init__.py` for why this package, specifically, is
allowed to import from both `core.db` and `intelligence_v2`.

Trading-session-aware by construction: every lookup goes through
`position_at_or_after`/`position_at_or_before`, which operate on the
ACTUAL stored trading-session index (whatever `price_history` contains),
never on calendar-day arithmetic. A weekend or holiday announcement date
resolves FORWARD to the next real session — the market's first opportunity
to react — never backward to a session that already happened before the
news (see `position_at_or_after`'s docstring).

Known, documented limitation: `corporate_actions.announcement_date` is a
DATE with no time-of-day. An announcement made after market close on a
trading day is therefore indistinguishable from one made before the open —
both resolve to the same "day 0". This is a real precision limit of the
current data, not an oversight; event-study literature commonly accepts the
same ambiguity for the identical reason.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from intelligence_v2.processors.shared_relative_strength import (
    performance_between_dates,
    position_at_or_after,
)

WINDOWS = (0, 1, 5, 10, 20)  # 0 = the event day's own close-to-close return
VOLUME_LOOKBACK = 20


def _insufficient(reason: str) -> dict:
    out = {
        "anchor_date": None, "pre_event_close": None, "pre_event_close_date": None,
        "gap_pct": None, "volume_ratio_day0": None,
        "mfe_pct": None, "mae_pct": None, "max_window_available": None,
        "insufficient_reason": reason,
    }
    for w in WINDOWS:
        out[f"return_{w}d"] = None
        out[f"benchmark_return_{w}d"] = None
        out[f"relative_return_{w}d"] = None
    return out


def compute_event_reaction(price_df: pd.DataFrame, benchmark_close: pd.Series,
                           announcement_date: dt.date, windows: tuple[int, ...] = WINDOWS,
                           volume_lookback: int = VOLUME_LOOKBACK) -> dict:
    """`price_df` — one symbol's OHLCV, indexed by trade_date (ascending,
    already sanitized by the caller — this function does not sanitize).
    `benchmark_close` — the benchmark's close series, same indexing
    convention, ALSO already sanitized by the caller (via
    `sanitize_benchmark_series`) — this module never sanitizes on its own,
    to keep sanitization defined in exactly one place per the Shared RS
    Engine's own design rule.

    Returns a flat dict — see `_insufficient()` for the complete key set,
    always present regardless of outcome (values are None where data is
    insufficient, per the "UNKNOWN must propagate honestly" requirement).
    """
    if price_df.empty:
        return _insufficient("no price history for this symbol")

    close = price_df["close"]
    anchor_pos = position_at_or_after(close.index, announcement_date)
    if anchor_pos is None:
        return _insufficient("no trading session on or after the announcement date "
                             "(event is beyond the end of stored price history)")
    if anchor_pos - 1 < 0:
        return _insufficient("no trading session before the announcement date "
                             "(no pre-event baseline available)")

    pre_pos = anchor_pos - 1
    pre_close = close.iloc[pre_pos]
    pre_date = close.index[pre_pos]
    anchor_date = close.index[anchor_pos]

    if pd.isna(pre_close) or pre_close <= 0:
        return _insufficient("pre-event close price is missing or non-positive")

    out = {
        "anchor_date": anchor_date, "pre_event_close": float(pre_close),
        "pre_event_close_date": pre_date, "insufficient_reason": None,
    }

    # --- gap: day-0 open vs. pre-event close ---
    day0_open = price_df["open"].iloc[anchor_pos] if "open" in price_df.columns else None
    out["gap_pct"] = (round((day0_open / pre_close - 1) * 100, 4)
                      if day0_open is not None and pd.notna(day0_open) and day0_open > 0 else None)

    # --- volume ratio: day-0 volume vs. trailing average BEFORE the event ---
    out["volume_ratio_day0"] = None
    if "volume" in price_df.columns:
        vol = price_df["volume"]
        lookback_start = pre_pos - volume_lookback + 1
        if lookback_start >= 0:
            prior_avg = vol.iloc[lookback_start: pre_pos + 1].mean()
            day0_vol = vol.iloc[anchor_pos]
            if pd.notna(prior_avg) and prior_avg > 0 and pd.notna(day0_vol):
                out["volume_ratio_day0"] = round(day0_vol / prior_avg, 4)

    # --- windowed returns ---
    # None (not 0) means "not even the event day is measurable" — shouldn't
    # happen once `anchor_pos` itself was found, but kept as an honest
    # sentinel rather than assumed. 0 is a legitimate, meaningful value: "we
    # can only measure the event day itself, no forward window yet."
    max_window_available = None
    for w in windows:
        post_pos = anchor_pos + w
        if post_pos >= len(close):
            out[f"return_{w}d"] = None
            out[f"benchmark_return_{w}d"] = None
            out[f"relative_return_{w}d"] = None
            continue
        post_close = close.iloc[post_pos]
        post_date = close.index[post_pos]
        if pd.isna(post_close):
            out[f"return_{w}d"] = None
            out[f"benchmark_return_{w}d"] = None
            out[f"relative_return_{w}d"] = None
            continue
        ret = round((post_close / pre_close - 1) * 100, 4)
        bench_ret = (performance_between_dates(benchmark_close, pre_date, post_date)
                    if not benchmark_close.empty else None)
        rel_ret = round(ret - bench_ret, 4) if bench_ret is not None else None
        out[f"return_{w}d"] = ret
        out[f"benchmark_return_{w}d"] = bench_ret
        out[f"relative_return_{w}d"] = rel_ret
        max_window_available = w
    out["max_window_available"] = max_window_available

    # --- max favourable / adverse excursion over the longest available window ---
    longest_pos = anchor_pos + max_window_available if max_window_available is not None else anchor_pos
    if longest_pos >= anchor_pos and "high" in price_df.columns and "low" in price_df.columns:
        window_high = price_df["high"].iloc[anchor_pos: longest_pos + 1].max()
        window_low = price_df["low"].iloc[anchor_pos: longest_pos + 1].min()
        out["mfe_pct"] = (round((window_high / pre_close - 1) * 100, 4)
                          if pd.notna(window_high) else None)
        out["mae_pct"] = (round((window_low / pre_close - 1) * 100, 4)
                          if pd.notna(window_low) else None)
    else:
        out["mfe_pct"] = None
        out["mae_pct"] = None

    return out
