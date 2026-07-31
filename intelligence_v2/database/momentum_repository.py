"""
Repository for `early_momentum_daily` — the only place that table is read or
written. Writes are idempotent (upsert on trade_date+symbol).
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
from sqlalchemy import delete, select

from intelligence_v2.database.engine import session_scope
from intelligence_v2.models import EarlyMomentumDaily


def replace_for_date(trade_date: dt.date, rows: list[dict]) -> int:
    """Replace all rows for one date in a single transaction.

    A full replace (rather than per-row upsert) is used because
    `rank_in_category` is only meaningful relative to the whole day's cohort —
    a partial update could leave stale ranks behind.
    """
    with session_scope() as s:
        s.execute(delete(EarlyMomentumDaily).where(
            EarlyMomentumDaily.trade_date == trade_date))
        for r in rows:
            s.add(EarlyMomentumDaily(**r))
    return len(rows)


def get_by_date(trade_date: dt.date, category: str | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(EarlyMomentumDaily).where(EarlyMomentumDaily.trade_date == trade_date)
        if category:
            stmt = stmt.where(EarlyMomentumDaily.category == category)
        rows = s.scalars(stmt.order_by(EarlyMomentumDaily.rank_in_category)).all()
    return _to_df(rows)


def get_latest(category: str | None = None) -> pd.DataFrame:
    with session_scope() as s:
        latest = s.scalar(
            select(EarlyMomentumDaily.trade_date)
            .order_by(EarlyMomentumDaily.trade_date.desc()).limit(1))
    if latest is None:
        return pd.DataFrame()
    return get_by_date(latest, category=category)


def get_symbol_history(symbol: str) -> pd.DataFrame:
    with session_scope() as s:
        rows = s.scalars(
            select(EarlyMomentumDaily)
            .where(EarlyMomentumDaily.symbol == symbol)
            .order_by(EarlyMomentumDaily.trade_date.asc())
        ).all()
    return _to_df(rows)


def get_distinct_dates() -> list[dt.date]:
    with session_scope() as s:
        return list(s.scalars(
            select(EarlyMomentumDaily.trade_date).distinct()
            .order_by(EarlyMomentumDaily.trade_date)).all())


def get_category_counts_by_date() -> pd.DataFrame:
    """Category counts per date — powers the History tab's trend view."""
    with session_scope() as s:
        rows = s.scalars(select(EarlyMomentumDaily)).all()
    if not rows:
        return pd.DataFrame(columns=["trade_date", "category", "count"])
    df = pd.DataFrame([{"trade_date": r.trade_date, "category": r.category} for r in rows])
    return (df.groupby(["trade_date", "category"]).size()
            .reset_index(name="count").sort_values("trade_date"))


def _to_df(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "trade_date": r.trade_date, "symbol": r.symbol, "category": r.category,
            "rank_in_category": r.rank_in_category, "signal_count": r.signal_count,
            "sector": r.sector, "sector_state": r.sector_state, "cycle_stage": r.cycle_stage,
            "close": r.close, "perf_1w": r.perf_1w, "perf_1m": r.perf_1m, "perf_3m": r.perf_3m,
            "rs_1w": r.rs_1w, "rs_1m": r.rs_1m, "rs_3m": r.rs_3m, "rs_slope": r.rs_slope,
            "above_20_sma": r.above_20_sma, "above_50_sma": r.above_50_sma,
            "above_200_sma": r.above_200_sma, "volume_ratio": r.volume_ratio,
            "dist_52w_high_pct": r.dist_52w_high_pct,
            "signals": json.loads(r.signals) if r.signals else {},
            "reasons": json.loads(r.reasons) if r.reasons else [],
            "missing": json.loads(r.missing) if r.missing else [],
            "category_reason": r.category_reason,
        }
        for r in rows
    ])
