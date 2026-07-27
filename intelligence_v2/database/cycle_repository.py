"""
Repository for `market_cycle_daily` and `market_cycle_transitions` — the only
place those tables are read or written. All writes are idempotent (upsert on
natural keys), so re-running a backfill is always safe.
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
from sqlalchemy import select

from intelligence_v2.database.engine import session_scope
from intelligence_v2.models import MarketCycleDaily, MarketCycleTransition


# ---------------------------------------------------------------------------
# Daily cycle rows
# ---------------------------------------------------------------------------
def upsert_cycle(row: dict) -> None:
    with session_scope() as s:
        existing = s.scalar(
            select(MarketCycleDaily).where(
                MarketCycleDaily.trade_date == row["trade_date"],
                MarketCycleDaily.sector == row["sector"],
            )
        )
        if existing is None:
            s.add(MarketCycleDaily(**row))
        else:
            for k, v in row.items():
                setattr(existing, k, v)


def get_prior_cycle_row(sector: str, before_date: dt.date) -> dict | None:
    """Most recent stored cycle row for a sector strictly BEFORE `before_date`
    (no look-ahead during backfill)."""
    with session_scope() as s:
        r = s.scalar(
            select(MarketCycleDaily)
            .where(MarketCycleDaily.sector == sector,
                   MarketCycleDaily.trade_date < before_date)
            .order_by(MarketCycleDaily.trade_date.desc())
            .limit(1)
        )
        if r is None:
            return None
        return {"trade_date": r.trade_date, "stage": r.stage, "raw_stage": r.raw_stage,
                "days_in_stage": r.days_in_stage, "stage_start_date": r.stage_start_date}


def get_recent_raw_stages(sector: str, n: int, before_date: dt.date) -> list[str]:
    """Raw (pre-hysteresis) stages of the last `n` stored rows before a date,
    newest first — the streak evidence hysteresis needs."""
    with session_scope() as s:
        rows = s.scalars(
            select(MarketCycleDaily)
            .where(MarketCycleDaily.sector == sector,
                   MarketCycleDaily.trade_date < before_date)
            .order_by(MarketCycleDaily.trade_date.desc())
            .limit(n)
        ).all()
        return [r.raw_stage for r in rows]


def get_latest_all_sectors() -> pd.DataFrame:
    with session_scope() as s:
        latest = s.scalar(
            select(MarketCycleDaily.trade_date)
            .order_by(MarketCycleDaily.trade_date.desc()).limit(1)
        )
        if latest is None:
            return pd.DataFrame()
        rows = s.scalars(
            select(MarketCycleDaily).where(MarketCycleDaily.trade_date == latest)
        ).all()
    return _cycle_rows_to_df(rows)


def get_cycle_history(sector: str) -> pd.DataFrame:
    with session_scope() as s:
        rows = s.scalars(
            select(MarketCycleDaily)
            .where(MarketCycleDaily.sector == sector)
            .order_by(MarketCycleDaily.trade_date.asc())
        ).all()
    return _cycle_rows_to_df(rows)


def get_distinct_cycle_dates() -> list[dt.date]:
    with session_scope() as s:
        return list(s.scalars(
            select(MarketCycleDaily.trade_date).distinct()
            .order_by(MarketCycleDaily.trade_date)
        ).all())


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------
def record_transition(row: dict) -> None:
    with session_scope() as s:
        existing = s.scalar(
            select(MarketCycleTransition).where(
                MarketCycleTransition.sector == row["sector"],
                MarketCycleTransition.transition_date == row["transition_date"],
                MarketCycleTransition.to_stage == row["to_stage"],
            )
        )
        if existing is None:
            s.add(MarketCycleTransition(**row))
        else:
            for k, v in row.items():
                setattr(existing, k, v)


def get_transitions(sector: str | None = None, limit: int | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(MarketCycleTransition)
        if sector:
            stmt = stmt.where(MarketCycleTransition.sector == sector)
        stmt = stmt.order_by(MarketCycleTransition.transition_date.desc(),
                            MarketCycleTransition.sector.asc())
        if limit:
            stmt = stmt.limit(limit)
        rows = s.scalars(stmt).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"sector": r.sector, "transition_date": r.transition_date,
         "from_stage": r.from_stage, "to_stage": r.to_stage,
         "days_in_previous_stage": r.days_in_previous_stage,
         "reasons": json.loads(r.reasons) if r.reasons else []}
        for r in rows
    ])


def _cycle_rows_to_df(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {
            "trade_date": r.trade_date, "sector": r.sector,
            "stage": r.stage, "raw_stage": r.raw_stage, "prior_stage": r.prior_stage,
            "days_in_stage": r.days_in_stage, "stage_start_date": r.stage_start_date,
            "reasons": json.loads(r.reasons) if r.reasons else [],
            "possible_behaviour": r.possible_behaviour,
            "confidence_notes": json.loads(r.confidence_notes) if r.confidence_notes else [],
            "rule_order": r.rule_order, "matched_by_fallback": r.matched_by_fallback,
        }
        for r in rows
    ])
