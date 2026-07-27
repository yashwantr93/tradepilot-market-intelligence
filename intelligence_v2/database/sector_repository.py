"""
Repository helpers for `sector_intelligence_daily` — the only place that reads
or writes that table. All writes are idempotent (upsert on trade_date+sector),
so re-running a backfill is always safe.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import select

from intelligence_v2.database.engine import session_scope
from intelligence_v2.models import SectorIntelligenceDaily


def upsert_snapshot(row: dict) -> None:
    """Insert or update one (trade_date, sector) row."""
    with session_scope() as s:
        existing = s.scalar(
            select(SectorIntelligenceDaily).where(
                SectorIntelligenceDaily.trade_date == row["trade_date"],
                SectorIntelligenceDaily.sector == row["sector"],
            )
        )
        if existing is None:
            s.add(SectorIntelligenceDaily(**row))
        else:
            for k, v in row.items():
                setattr(existing, k, v)


def get_last_n_rows(sector: str, n: int, before_date: dt.date | None = None) -> list[dict]:
    """Most recent stored rows for a sector, newest first. Used for hysteresis
    (raw_state agreement check) and consistency_pct — reads only rows strictly
    before `before_date` when given, so a backfill never looks ahead."""
    with session_scope() as s:
        stmt = select(SectorIntelligenceDaily).where(SectorIntelligenceDaily.sector == sector)
        if before_date is not None:
            stmt = stmt.where(SectorIntelligenceDaily.trade_date < before_date)
        stmt = stmt.order_by(SectorIntelligenceDaily.trade_date.desc()).limit(n)
        rows = s.scalars(stmt).all()
        return [
            {"trade_date": r.trade_date, "raw_state": r.raw_state, "state": r.state,
             "days_in_state": r.days_in_state}
            for r in rows
        ]


def count_recent_state(sector: str, state_name: str, lookback_days: int,
                       before_date: dt.date | None = None) -> tuple[int, int]:
    """(matches, total) of the trailing `lookback_days` STORED rows for a
    sector where state == state_name. `total` may be < lookback_days early on
    — that's expected (classification history is only just starting)."""
    rows = get_last_n_rows(sector, lookback_days, before_date=before_date)
    matches = sum(1 for r in rows if r["state"] == state_name)
    return matches, len(rows)


def get_history(sector: str, limit: int | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = (select(SectorIntelligenceDaily)
                .where(SectorIntelligenceDaily.sector == sector)
                .order_by(SectorIntelligenceDaily.trade_date.asc()))
        if limit is not None:
            stmt = stmt.order_by(SectorIntelligenceDaily.trade_date.desc()).limit(limit)
        rows = s.scalars(stmt).all()
    df = _rows_to_df(rows)
    return df.sort_values("trade_date").reset_index(drop=True) if not df.empty else df


def get_latest_all_sectors() -> pd.DataFrame:
    """Latest trade_date's row for every sector (the Overview tab's source)."""
    with session_scope() as s:
        latest_date = s.scalar(
            select(SectorIntelligenceDaily.trade_date)
            .order_by(SectorIntelligenceDaily.trade_date.desc()).limit(1)
        )
        if latest_date is None:
            return pd.DataFrame()
        rows = s.scalars(
            select(SectorIntelligenceDaily).where(SectorIntelligenceDaily.trade_date == latest_date)
        ).all()
    return _rows_to_df(rows)


def get_distinct_dates() -> list[dt.date]:
    with session_scope() as s:
        dates = s.scalars(
            select(SectorIntelligenceDaily.trade_date).distinct().order_by(SectorIntelligenceDaily.trade_date)
        ).all()
        return list(dates)


def _rows_to_df(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "trade_date": r.trade_date, "sector": r.sector, "close": r.close,
            "perf_1w": r.perf_1w, "perf_1m": r.perf_1m, "perf_3m": r.perf_3m,
            "perf_6m": r.perf_6m, "perf_1y": r.perf_1y,
            "rs_1w": r.rs_1w, "rs_1m": r.rs_1m, "rs_3m": r.rs_3m,
            "rs_6m": r.rs_6m, "rs_1y": r.rs_1y, "momentum_1m": r.momentum_1m,
            "above_20_sma": r.above_20_sma, "above_50_sma": r.above_50_sma,
            "above_200_sma": r.above_200_sma, "consistency_pct": r.consistency_pct,
            "raw_state": r.raw_state, "state": r.state, "days_in_state": r.days_in_state,
            "data_method": r.data_method,
        }
        for r in rows
    ])
