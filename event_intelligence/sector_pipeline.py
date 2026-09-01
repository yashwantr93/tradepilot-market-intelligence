"""
Sector/Theme Emergence pipeline — Phase 6. Orchestration only: reads V1
price/corp-action/symbol data (`core.db`) and computes via
`sector_metrics.py`/`sector_state.py` (which reuse V2's calendar-aligned
primitives and V2's own hysteresis function) — the same bridging pattern as
Phase 3/5. Writes an append-only daily history to `sector_theme_state`.

Iterates the last `lookback_sessions` trading sessions (per the benchmark's
own stored date index — real trading-session-aware, not calendar-day
arithmetic) so hysteresis has real history to confirm against and so
Phase 6's historical-validation section has real data to measure.
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from core.config import BENCHMARK_SYMBOL
from core.config import SECTOR_THEME as T
from core.db import repository as repo
from event_intelligence.sector_metrics import aggregate_sector_metrics, compute_constituent_metrics
from event_intelligence.sector_state import (
    DIRECTION_CONTEXT,
    build_evidence,
    classify_participation,
    classify_raw,
)
from event_intelligence.sector_universe import THEME_BASKETS, get_universe
from intelligence_v2.processors.sector_classifier import apply_hysteresis
from intelligence_v2.processors.shared_relative_strength import (
    position_at_or_before,
    sanitize_benchmark_series,
    sanitize_close_series,
)


def _load_benchmark() -> pd.Series:
    df = repo.get_price_history(BENCHMARK_SYMBOL, lookback=5000)
    if df.empty:
        return pd.Series(dtype=float)
    close, _ = sanitize_benchmark_series(df.set_index("trade_date")["close"])
    return close


def _load_clean_price_frame(symbol: str) -> pd.DataFrame:
    df = repo.get_price_history(symbol, lookback=5000)
    if df.empty:
        return df
    df = df.set_index("trade_date")
    clean_close, _ = sanitize_close_series(df["close"])
    return df.loc[clean_close.index]


def _close_series(df: pd.DataFrame) -> pd.Series:
    """Safe accessor — a symbol with no price history at all yields a
    genuinely empty DataFrame (no columns), and `df["close"]` on that
    raises KeyError rather than the empty-Series `compute_constituent_metrics`
    already knows how to handle gracefully."""
    return df["close"] if "close" in df.columns else pd.Series(dtype=float)


def _volume_series(df: pd.DataFrame) -> pd.Series | None:
    return df["volume"] if "volume" in df.columns else None


def _data_quality(measurable: int, total: int) -> str:
    if total == 0:
        return "LOW"
    ratio = measurable / total
    return "HIGH" if ratio >= 0.8 else "MEDIUM" if ratio >= 0.5 else "LOW"


def run_sector_theme(lookback_sessions: int = 90) -> dict:
    """Phase 11: wrapped with the same job_runs audit-trail convention every
    V1 pipeline already uses — see the Phase 11 report's FAILURE RECOVERY
    section."""
    job_id = repo.start_job("sector_theme", source="event_intelligence")
    try:
        return _run_sector_theme(lookback_sessions, job_id)
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        raise


def _run_sector_theme(lookback_sessions: int, job_id: int) -> dict:
    sector_map = repo.get_symbol_sector_map()
    universe = get_universe(sector_map)

    all_symbols = sorted({s for syms in universe.values() for s in syms})
    price_frames = {s: _load_clean_price_frame(s) for s in all_symbols}
    benchmark_close = _load_benchmark()

    if benchmark_close.empty:
        repo.finish_job(job_id, "ok", rows_in=0, rows_out=0, error="no benchmark price history")
        return {"processed": 0, "sectors": 0, "error": "no benchmark price history"}

    trade_dates = list(benchmark_close.index)[-lookback_sessions:]
    if not trade_dates:
        repo.finish_job(job_id, "ok", rows_in=0, rows_out=0, error="insufficient benchmark history")
        return {"processed": 0, "sectors": 0, "error": "insufficient benchmark history"}

    # Prefetch every relevant corporate action once (small table, hundreds
    # of rows) — reuses Phase 1.5's existing accessor rather than adding a
    # second, near-duplicate one, since it already returns dates + impact_tag.
    symbol_set = set(all_symbols)
    events_with_dates = [
        {"symbol": e["symbol"], "impact_tag": e["impact_tag"], "date": e["announcement_date"]}
        for e in repo.get_corporate_actions_for_backfill() if e["symbol"] in symbol_set
    ]

    updates = []
    processed_sectors = 0

    for sector_or_theme, symbols in universe.items():
        taxonomy = "THEME_BASKET" if sector_or_theme in THEME_BASKETS else "GICS_SECTOR"
        processed_sectors += 1
        prior_confirmed_state, prior_days_in_state = None, 0
        recent_raw_states: list[str] = []  # newest first

        for as_of in trade_dates:
            constituent_now = {s: compute_constituent_metrics(
                _close_series(price_frames[s]), _volume_series(price_frames[s]), benchmark_close, as_of
            ) for s in symbols}
            current_agg = aggregate_sector_metrics(constituent_now)

            trend_pos = position_at_or_before(benchmark_close.index, as_of)
            prior_agg = {}
            if trend_pos is not None and trend_pos - T["trend_lookback_sessions"] >= 0:
                prior_date = benchmark_close.index[trend_pos - T["trend_lookback_sessions"]]
                constituent_prior = {s: compute_constituent_metrics(
                    _close_series(price_frames[s]), _volume_series(price_frames[s]), benchmark_close, prior_date
                ) for s in symbols}
                prior_agg = aggregate_sector_metrics(constituent_prior)

            window_start = as_of - dt.timedelta(days=T["event_lookback_days"])
            sector_events = [e for e in events_with_dates
                            if e["symbol"] in symbols and window_start <= e["date"] <= as_of]
            positive_events = sum(1 for e in sector_events if e["impact_tag"] == "Bullish")
            negative_events = sum(1 for e in sector_events if e["impact_tag"] == "Bearish")

            raw_state = classify_raw(current_agg, prior_agg, positive_events, negative_events)
            confirmed_state, days_in_state = apply_hysteresis(
                raw_state, prior_confirmed_state, prior_days_in_state, recent_raw_states
            )

            participation = classify_participation(constituent_now, current_agg.get("avg_rs_1m"))
            evidence_for, evidence_against = build_evidence(
                confirmed_state, current_agg, prior_agg, positive_events, negative_events, participation
            )
            breadth_change = (
                (current_agg["pct_above_20sma"] - prior_agg["pct_above_20sma"])
                if current_agg.get("pct_above_20sma") is not None and prior_agg.get("pct_above_20sma") is not None
                else None
            )
            rs_change = (
                (current_agg["avg_rs_1m"] - prior_agg["avg_rs_1m"])
                if current_agg.get("avg_rs_1m") is not None and prior_agg.get("avg_rs_1m") is not None
                else None
            )

            updates.append({
                "as_of_date": as_of, "sector_or_theme": sector_or_theme, "taxonomy": taxonomy,
                "constituent_count": current_agg["constituent_count"],
                "measurable_count": current_agg["measurable_count"],
                "pct_above_20sma": current_agg["pct_above_20sma"],
                "pct_positive_rs_1w": current_agg["pct_positive_rs_1w"],
                "pct_positive_rs_1m": current_agg["pct_positive_rs_1m"],
                "avg_rs_1w": current_agg["avg_rs_1w"], "avg_rs_1m": current_agg["avg_rs_1m"],
                "avg_rs_3m": current_agg["avg_rs_3m"],
                "breadth_change": breadth_change, "rs_change": rs_change,
                "pct_volume_expansion": current_agg["pct_volume_expansion"],
                "positive_event_count": positive_events, "negative_event_count": negative_events,
                "raw_state": raw_state, "confirmed_state": confirmed_state,
                "days_in_state": days_in_state, "direction_context": DIRECTION_CONTEXT[confirmed_state],
                "leaders_json": json.dumps(participation["leaders"]),
                "early_participants_json": json.dumps(participation["early_participants"]),
                "laggards_json": json.dumps(participation["laggards"]),
                "non_participants_json": json.dumps(participation["non_participants"]),
                "evidence_for_json": json.dumps(evidence_for),
                "evidence_against_json": json.dumps(evidence_against),
                "data_quality": _data_quality(current_agg["measurable_count"], current_agg["constituent_count"]),
                "state_basis": "HEURISTIC",
            })

            recent_raw_states = [raw_state] + recent_raw_states[:2]  # MIN_DWELL_DAYS-1 = 2
            prior_confirmed_state, prior_days_in_state = confirmed_state, days_in_state

    stored = repo.upsert_sector_theme_state(updates)
    repo.finish_job(job_id, "ok", rows_in=len(updates), rows_out=stored)
    return {"processed": len(updates), "sectors": processed_sectors, "stored": stored,
           "trade_dates_covered": len(trade_dates)}
