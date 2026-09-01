"""
Market Reaction pipeline — Phase 3. Orchestration only: reads V1 event/price
data (`core.db.repository`), computes via `reaction_windows.py` (which in
turn reuses V2's calendar-aligned primitives), classifies via
`reaction_classifier.py`, writes back to V1 (`event_market_reaction`).

This is the one module in the whole codebase allowed to import both
`core.db` and `intelligence_v2.processors` — see `event_intelligence/
__init__.py` for why that doesn't violate the V1/V2 isolation rule.

`action_ids=None` (default) processes every stored corporate_actions row —
used for the initial backfill and safe to re-run (upsert on
corporate_action_id). Pass specific ids to process only rows a live
`corp_actions_pipeline` run just inserted (mirrors the Phase 2 materiality
pipeline's incremental pattern).
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

import pandas as pd

from core.config import BENCHMARK_SYMBOL
from core.db import repository as repo
from event_intelligence.reaction_classifier import (
    classify_continuation,
    classify_event_alignment,
    classify_reaction_state,
)
from event_intelligence.reaction_windows import compute_event_reaction
from intelligence_v2.processors.shared_relative_strength import (
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


def run_market_reaction(action_ids: list[int] | None = None) -> dict:
    """Returns {"processed": N, "by_state": {...}, "coverage": {...}}.

    Phase 11: wrapped with the same job_runs audit-trail convention every V1
    pipeline already uses (see corp_actions_pipeline.py) — this and the
    other four event_intelligence pipelines previously ran invisibly to the
    Settings page / job_runs table, so a silent failure here left no trace
    anywhere in the app."""
    job_id = repo.start_job("market_reaction", source="event_intelligence")
    try:
        return _run_market_reaction(action_ids, job_id)
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        raise


def _run_market_reaction(action_ids: list[int] | None, job_id: int) -> dict:
    events = repo.get_corporate_actions_for_backfill()  # id/symbol/announcement_date/event_type/impact_tag (+extras, unused here)
    if action_ids is not None:
        wanted = set(action_ids)
        events = [e for e in events if e["id"] in wanted]

    benchmark_close = _load_benchmark()

    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_symbol[e["symbol"]].append(e)

    updates: list[dict] = []
    by_state: dict[str, int] = {}
    have_1d = have_5d = have_10d = have_20d = 0

    for symbol, symbol_events in by_symbol.items():
        price_df = _load_clean_price_frame(symbol)
        for e in symbol_events:
            adate = e["announcement_date"]
            if isinstance(adate, str):
                adate = dt.date.fromisoformat(adate)

            metrics = compute_event_reaction(price_df, benchmark_close, adate)

            reaction_state, reason = classify_reaction_state(metrics["relative_return_5d"])
            continuation = classify_continuation(metrics["relative_return_1d"],
                                                 metrics["relative_return_5d"])
            alignment = classify_event_alignment(e["impact_tag"], reaction_state)

            by_state[reaction_state] = by_state.get(reaction_state, 0) + 1
            if metrics["return_1d"] is not None:
                have_1d += 1
            if metrics["return_5d"] is not None:
                have_5d += 1
            if metrics["return_10d"] is not None:
                have_10d += 1
            if metrics["return_20d"] is not None:
                have_20d += 1

            updates.append({
                "corporate_action_id": e["id"], "symbol": symbol, "event_type": e["event_type"],
                "impact_tag": e["impact_tag"], "announcement_date": adate,
                "anchor_date": metrics["anchor_date"],
                "pre_event_close": metrics["pre_event_close"],
                "pre_event_close_date": metrics["pre_event_close_date"],
                "gap_pct": metrics["gap_pct"], "volume_ratio_day0": metrics["volume_ratio_day0"],
                "return_1d": metrics["return_1d"], "benchmark_return_1d": metrics["benchmark_return_1d"],
                "relative_return_1d": metrics["relative_return_1d"],
                "return_5d": metrics["return_5d"], "benchmark_return_5d": metrics["benchmark_return_5d"],
                "relative_return_5d": metrics["relative_return_5d"],
                "return_10d": metrics["return_10d"], "benchmark_return_10d": metrics["benchmark_return_10d"],
                "relative_return_10d": metrics["relative_return_10d"],
                "return_20d": metrics["return_20d"], "benchmark_return_20d": metrics["benchmark_return_20d"],
                "relative_return_20d": metrics["relative_return_20d"],
                "mfe_pct": metrics["mfe_pct"], "mae_pct": metrics["mae_pct"],
                "max_window_available": metrics["max_window_available"],
                "reaction_state": reaction_state, "reaction_reason": reason,
                "continuation_state": continuation, "event_alignment": alignment,
            })

    stored = repo.upsert_event_market_reaction(updates)
    total = len(events)
    coverage = {
        "total_events": total,
        "1d_pct": round(have_1d / total * 100, 1) if total else 0.0,
        "5d_pct": round(have_5d / total * 100, 1) if total else 0.0,
        "10d_pct": round(have_10d / total * 100, 1) if total else 0.0,
        "20d_pct": round(have_20d / total * 100, 1) if total else 0.0,
    }
    repo.finish_job(job_id, "ok", rows_in=total, rows_out=stored)
    return {"processed": total, "stored": stored, "by_state": by_state, "coverage": coverage}
