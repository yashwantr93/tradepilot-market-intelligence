"""
Repository helpers — typed read/write access to the DB.

All writes are idempotent (upsert on natural keys) so re-running any job is safe.
The rest of the backend talks to the DB only through these functions.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Iterable

import pandas as pd
from sqlalchemy import delete, select

from core.db.engine import session_scope
from core.db.models import (
    BlockDeal,
    BulkDeal,
    CombinedWatchlist,
    CorporateAction,
    DailyWatchlist,
    DeadLetter,
    FiiDiiActivity,
    InstitutionalWatchlist,
    JobRun,
    PriceHistory,
    ResultsTracker,
    SectorRotation,
    Signal,
    SymbolMaster,
)


# ---------------------------------------------------------------------------
# Symbol master
# ---------------------------------------------------------------------------
def upsert_symbols(rows: Iterable[dict]) -> int:
    n = 0
    with session_scope() as s:
        for r in rows:
            obj = s.get(SymbolMaster, r["isin"])
            if obj is None:
                s.add(SymbolMaster(**r))
            else:
                for k, v in r.items():
                    setattr(obj, k, v)
            n += 1
    return n


def get_symbol_map() -> dict[str, dict]:
    """Return {nse_symbol: {isin, company_name, sector, ...}}."""
    with session_scope() as s:
        out = {}
        for row in s.scalars(select(SymbolMaster)).all():
            if row.nse_symbol:
                out[row.nse_symbol] = {
                    "isin": row.isin,
                    "company_name": row.company_name,
                    "sector": row.sector,
                }
        return out


# ---------------------------------------------------------------------------
# Price history
# ---------------------------------------------------------------------------
def upsert_prices(df: pd.DataFrame) -> int:
    """df columns: symbol, trade_date, open, high, low, close, volume."""
    if df.empty:
        return 0
    with session_scope() as s:
        # Replace any existing rows for these (symbol, date) pairs cheaply.
        for _, r in df.iterrows():
            existing = s.scalar(
                select(PriceHistory).where(
                    PriceHistory.symbol == r["symbol"],
                    PriceHistory.trade_date == r["trade_date"],
                )
            )
            payload = dict(
                symbol=r["symbol"], trade_date=r["trade_date"],
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
                volume=int(r["volume"]),
            )
            if existing is None:
                s.add(PriceHistory(**payload))
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
    return len(df)


def get_symbols_with_prices() -> set[str]:
    """Distinct symbols that have at least one price_history row."""
    with session_scope() as s:
        return set(s.scalars(select(PriceHistory.symbol).distinct()).all())


def count_dead_letters() -> int:
    with session_scope() as s:
        from sqlalchemy import func
        return int(s.scalar(select(func.count()).select_from(DeadLetter)) or 0)


def get_price_history(symbol: str, lookback: int = 300) -> pd.DataFrame:
    with session_scope() as s:
        rows = s.scalars(
            select(PriceHistory)
            .where(PriceHistory.symbol == symbol)
            .order_by(PriceHistory.trade_date.desc())
            .limit(lookback)
        ).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(
        [
            {"trade_date": r.trade_date, "open": r.open, "high": r.high,
             "low": r.low, "close": r.close, "volume": r.volume}
            for r in rows
        ]
    ).sort_values("trade_date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------
def upsert_deals(df: pd.DataFrame, kind: str) -> int:
    """Insert deals, skipping duplicates by dedupe_hash. kind: 'bulk'|'block'."""
    if df.empty:
        return 0
    model = BulkDeal if kind == "bulk" else BlockDeal
    inserted = 0
    with session_scope() as s:
        existing = set(s.scalars(select(model.dedupe_hash)).all())
        for _, r in df.iterrows():
            if r["dedupe_hash"] in existing:
                continue
            s.add(model(
                trade_date=r["trade_date"], exchange=r["exchange"],
                symbol=r["symbol"], isin=r.get("isin"),
                client_name=r["client_name"], txn_type=r["txn_type"],
                quantity=int(r["quantity"]), price=float(r["price"]),
                value=float(r["value"]), dedupe_hash=r["dedupe_hash"],
            ))
            existing.add(r["dedupe_hash"])
            inserted += 1
    return inserted


def get_latest_deal_date() -> dt.date | None:
    """Most recent trade_date across bulk and block deals."""
    with session_scope() as s:
        dates = []
        for model in (BulkDeal, BlockDeal):
            d = s.scalar(select(model.trade_date).order_by(model.trade_date.desc()).limit(1))
            if d is not None:
                dates.append(d)
        return max(dates) if dates else None


def get_deals(kind: str, since: dt.date) -> pd.DataFrame:
    model = BulkDeal if kind == "bulk" else BlockDeal
    with session_scope() as s:
        rows = s.scalars(
            select(model).where(model.trade_date >= since)
        ).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"trade_date": r.trade_date, "exchange": r.exchange, "symbol": r.symbol,
         "isin": r.isin, "client_name": r.client_name, "txn_type": r.txn_type,
         "quantity": r.quantity, "price": r.price, "value": r.value}
        for r in rows
    ])


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------
def replace_watchlist(trade_date: dt.date, rows: list[dict]) -> int:
    with session_scope() as s:
        s.execute(delete(DailyWatchlist).where(DailyWatchlist.trade_date == trade_date))
        for r in rows:
            r = dict(r)
            if isinstance(r.get("reasons"), (list, tuple)):
                r["reasons"] = json.dumps(list(r["reasons"]))
            s.add(DailyWatchlist(**r))
    return len(rows)


def get_watchlist(trade_date: dt.date | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(DailyWatchlist)
        if trade_date is not None:
            stmt = stmt.where(DailyWatchlist.trade_date == trade_date)
        rows = s.scalars(stmt.order_by(DailyWatchlist.rule_count.desc())).all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([
        {
            "trade_date": r.trade_date, "symbol": r.symbol, "company_name": r.company_name,
            "sector": r.sector, "current_price": r.current_price,
            "catalyst_tag": r.catalyst_tag,
            "reasons": json.loads(r.reasons) if r.reasons else [],
            "above_20_sma": r.above_20_sma, "relative_strength": r.relative_strength,
            "volume_expansion": r.volume_expansion, "sma_20": r.sma_20,
            "high_52w": r.high_52w, "low_52w": r.low_52w,
            "dist_52w_high_pct": r.dist_52w_high_pct, "dist_52w_low_pct": r.dist_52w_low_pct,
            "technical_status": r.technical_status, "deal_value": r.deal_value,
            "net_qty": r.net_qty, "rule_count": r.rule_count,
        }
        for r in rows
    ])
    return df


# ---------------------------------------------------------------------------
# FII/DII activity
# ---------------------------------------------------------------------------
def upsert_fii_dii(df: pd.DataFrame, segment: str = "CASH",
                   source: str = "NSE") -> int:
    if df.empty:
        return 0
    with session_scope() as s:
        for _, r in df.iterrows():
            existing = s.scalar(
                select(FiiDiiActivity).where(
                    FiiDiiActivity.trade_date == r["trade_date"],
                    FiiDiiActivity.segment == segment,
                )
            )
            payload = dict(
                trade_date=r["trade_date"], segment=segment,
                fii_buy=float(r["fii_buy"]), fii_sell=float(r["fii_sell"]),
                fii_net=float(r["fii_net"]), dii_buy=float(r["dii_buy"]),
                dii_sell=float(r["dii_sell"]), dii_net=float(r["dii_net"]),
                source=source,
            )
            if existing is None:
                s.add(FiiDiiActivity(**payload))
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
    return len(df)


def get_fii_dii(segment: str = "CASH", limit: int = 30) -> pd.DataFrame:
    with session_scope() as s:
        rows = s.scalars(
            select(FiiDiiActivity)
            .where(FiiDiiActivity.segment == segment)
            .order_by(FiiDiiActivity.trade_date.desc())
            .limit(limit)
        ).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"trade_date": r.trade_date, "fii_buy": r.fii_buy, "fii_sell": r.fii_sell,
         "fii_net": r.fii_net, "dii_buy": r.dii_buy, "dii_sell": r.dii_sell,
         "dii_net": r.dii_net}
        for r in rows
    ]).sort_values("trade_date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Sector rotation
# ---------------------------------------------------------------------------
def replace_sector_rotation(trade_date: dt.date, rows: list[dict]) -> int:
    with session_scope() as s:
        s.execute(delete(SectorRotation).where(SectorRotation.trade_date == trade_date))
        for r in rows:
            s.add(SectorRotation(**r))
    return len(rows)


def get_sector_rotation(trade_date: dt.date) -> pd.DataFrame:
    with session_scope() as s:
        rows = s.scalars(
            select(SectorRotation).where(SectorRotation.trade_date == trade_date)
        ).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"sector": r.sector, "perf_20d": r.perf_20d, "nifty_perf_20d": r.nifty_perf_20d,
         "rs_vs_nifty": r.rs_vs_nifty, "above_20_sma": r.above_20_sma,
         "above_50_sma": r.above_50_sma, "trend_status": r.trend_status,
         "data_method": r.data_method}
        for r in rows
    ])


# ---------------------------------------------------------------------------
# Institutional watchlist
# ---------------------------------------------------------------------------
def replace_institutional_watchlist(trade_date: dt.date, rows: list[dict]) -> int:
    with session_scope() as s:
        s.execute(delete(InstitutionalWatchlist).where(
            InstitutionalWatchlist.trade_date == trade_date))
        for r in rows:
            s.add(InstitutionalWatchlist(**r))
    return len(rows)


def get_institutional_watchlist(trade_date: dt.date) -> pd.DataFrame:
    with session_scope() as s:
        rows = s.scalars(
            select(InstitutionalWatchlist)
            .where(InstitutionalWatchlist.trade_date == trade_date)
        ).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"symbol": r.symbol, "sector": r.sector, "sector_trend": r.sector_trend,
         "relative_strength": r.relative_strength, "above_20_sma": r.above_20_sma,
         "current_price": r.current_price, "sma_20": r.sma_20,
         "high_52w": r.high_52w, "low_52w": r.low_52w,
         "dist_52w_high_pct": r.dist_52w_high_pct, "dist_52w_low_pct": r.dist_52w_low_pct}
        for r in rows
    ])


# ---------------------------------------------------------------------------
# Signals (validation layer)
# ---------------------------------------------------------------------------
def upsert_signal(row: dict) -> None:
    """Upsert a signal on its natural key; updates entry/returns on re-run."""
    with session_scope() as s:
        existing = s.scalar(
            select(Signal).where(
                Signal.signal_date == row["signal_date"],
                Signal.symbol == row["symbol"],
                Signal.source_engine == row["source_engine"],
                Signal.signal_type == row.get("signal_type"),
            )
        )
        if existing is None:
            s.add(Signal(**row))
        else:
            for k, v in row.items():
                setattr(existing, k, v)


def get_signals(source_engine: str | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(Signal)
        if source_engine is not None:
            stmt = stmt.where(Signal.source_engine == source_engine)
        rows = s.scalars(stmt).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"signal_date": r.signal_date, "symbol": r.symbol,
         "source_engine": r.source_engine, "signal_type": r.signal_type,
         "entry_price": r.entry_price, "ret_1d": r.ret_1d, "ret_5d": r.ret_5d,
         "ret_20d": r.ret_20d, "status": r.status}
        for r in rows
    ])


# ---------------------------------------------------------------------------
# Results tracker
# ---------------------------------------------------------------------------
def upsert_results(rows: list[dict]) -> int:
    """Upsert quarterly results on (symbol, period_end)."""
    if not rows:
        return 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(ResultsTracker).where(
                    ResultsTracker.symbol == r["symbol"],
                    ResultsTracker.period_end == r["period_end"],
                )
            )
            if existing is None:
                s.add(ResultsTracker(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
    return len(rows)


def get_results(period_end: dt.date | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(ResultsTracker)
        if period_end is not None:
            stmt = stmt.where(ResultsTracker.period_end == period_end)
        rows = s.scalars(stmt.order_by(ResultsTracker.period_end.desc())).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"symbol": r.symbol, "company_name": r.company_name, "quarter": r.quarter,
         "period_end": r.period_end, "revenue_growth_pct": r.revenue_growth_pct,
         "profit_growth_pct": r.profit_growth_pct, "margin_change_pct": r.margin_change_pct,
         "result_classification": r.result_classification, "basis": r.basis,
         "source": r.source}
        for r in rows
    ])


def latest_results_period() -> dt.date | None:
    with session_scope() as s:
        return s.scalar(select(ResultsTracker.period_end)
                        .order_by(ResultsTracker.period_end.desc()).limit(1))


# ---------------------------------------------------------------------------
# Corporate actions
# ---------------------------------------------------------------------------
def upsert_corporate_actions(rows: list[dict]) -> int:
    """Insert classified corporate actions, skipping duplicates by dedupe_hash."""
    if not rows:
        return 0
    inserted = 0
    with session_scope() as s:
        existing = set(s.scalars(select(CorporateAction.dedupe_hash)).all())
        for r in rows:
            if r["dedupe_hash"] in existing:
                continue
            s.add(CorporateAction(**r))
            existing.add(r["dedupe_hash"])
            inserted += 1
    return inserted


def get_corporate_actions(since: dt.date | None = None,
                          on_date: dt.date | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(CorporateAction)
        if on_date is not None:
            stmt = stmt.where(CorporateAction.announcement_date == on_date)
        elif since is not None:
            stmt = stmt.where(CorporateAction.announcement_date >= since)
        rows = s.scalars(stmt.order_by(CorporateAction.announcement_date.desc())).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"announcement_date": r.announcement_date, "symbol": r.symbol,
         "company_name": r.company_name, "event_type": r.event_type,
         "event_summary": r.event_summary, "impact_tag": r.impact_tag,
         "priority": r.priority, "source": r.source}
        for r in rows
    ])


def latest_corp_action_date() -> dt.date | None:
    with session_scope() as s:
        return s.scalar(select(CorporateAction.announcement_date)
                        .order_by(CorporateAction.announcement_date.desc()).limit(1))


# ---------------------------------------------------------------------------
# Combined watchlist
# ---------------------------------------------------------------------------
def replace_combined_watchlist(trade_date: dt.date, rows: list[dict]) -> int:
    with session_scope() as s:
        s.execute(delete(CombinedWatchlist).where(
            CombinedWatchlist.trade_date == trade_date))
        for r in rows:
            s.add(CombinedWatchlist(**r))
    return len(rows)


def get_combined_watchlist(trade_date: dt.date) -> pd.DataFrame:
    with session_scope() as s:
        rows = s.scalars(
            select(CombinedWatchlist)
            .where(CombinedWatchlist.trade_date == trade_date)
            .order_by(CombinedWatchlist.tier.asc())
        ).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"symbol": r.symbol, "sector": r.sector, "catalyst": r.catalyst,
         "relative_strength": r.relative_strength, "above_20_sma": r.above_20_sma,
         "volume_expansion": r.volume_expansion, "technical_status": r.technical_status,
         "in_deal": r.in_deal, "in_institutional": r.in_institutional, "tier": r.tier}
        for r in rows
    ])


def latest_watchlist_date() -> dt.date | None:
    """Most recent date present in either watchlist source."""
    with session_scope() as s:
        dates = []
        for model in (DailyWatchlist, InstitutionalWatchlist):
            d = s.scalar(select(model.trade_date).order_by(model.trade_date.desc()).limit(1))
            if d is not None:
                dates.append(d)
        return max(dates) if dates else None


# ---------------------------------------------------------------------------
# Job runs / dead letter
# ---------------------------------------------------------------------------
def start_job(job_name: str, source: str | None = None) -> int:
    with session_scope() as s:
        job = JobRun(job_name=job_name, source=source, status="running")
        s.add(job)
        s.flush()
        return job.id


def finish_job(job_id: int, status: str, rows_in: int = 0,
               rows_out: int = 0, error: str | None = None) -> None:
    with session_scope() as s:
        job = s.get(JobRun, job_id)
        if job is None:
            return
        job.finished_at = dt.datetime.utcnow()
        job.duration_s = (job.finished_at - job.started_at).total_seconds()
        job.status = status
        job.rows_in = rows_in
        job.rows_out = rows_out
        job.error = error


def add_dead_letter(source: str, payload: dict, reason: str) -> None:
    with session_scope() as s:
        s.add(DeadLetter(source=source, payload_json=json.dumps(payload, default=str),
                         reason=reason))
