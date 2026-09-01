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
    CorporateActionMateriality,
    DailyWatchlist,
    DeadLetter,
    EventExpectation,
    EventMarketReaction,
    EventTradeSignal,
    FiiDiiActivity,
    InstitutionalWatchlist,
    JobRun,
    Opportunity,
    PriceHistory,
    ResultsQuarterly,
    ResultsTracker,
    SectorRotation,
    SectorStockCrossReference,
    SectorThemeState,
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


def get_results_tracker_all() -> list[dict]:
    """Every stored results_tracker row, full detail — Phase 2.5 audit/cleanup."""
    with session_scope() as s:
        rows = s.scalars(select(ResultsTracker)).all()
    return [
        {"id": r.id, "symbol": r.symbol, "period_end": r.period_end,
         "revenue_growth_pct": r.revenue_growth_pct, "profit_growth_pct": r.profit_growth_pct,
         "basis": r.basis, "source": r.source, "created_at": r.created_at}
        for r in rows
    ]


def delete_results_tracker_rows(ids: list[int]) -> int:
    """Delete specific results_tracker rows by id — Phase 2.5 one-time cleanup.
    Surgical, not a truncate: only the ids the caller explicitly identified
    as contaminated are removed; every other row is untouched."""
    if not ids:
        return 0
    with session_scope() as s:
        n = s.execute(delete(ResultsTracker).where(ResultsTracker.id.in_(ids))).rowcount
    return n


def truncate_results_quarterly() -> int:
    """Phase 2.5: results_quarterly has held ONLY offline-seed data since it
    was created (Phase 1) — no live run ever populated it (see the Phase 2.5
    report's ROOT CAUSE section) — so a full clear loses no real data. Will
    be correctly repopulated by the next live results ingestion."""
    with session_scope() as s:
        n = s.execute(delete(ResultsQuarterly)).rowcount
    return n


def truncate_event_expectations() -> int:
    """Phase 2.5: every stored event_expectations row was computed against
    contaminated/offline-only history and is UNKNOWN anyway (see the Phase
    2.5 report) — a full clear loses no trustworthy signal. Will be
    correctly repopulated once results_tracker has a clean baseline."""
    with session_scope() as s:
        n = s.execute(delete(EventExpectation)).rowcount
    return n


def latest_results_period() -> dt.date | None:
    with session_scope() as s:
        return s.scalar(select(ResultsTracker.period_end)
                        .order_by(ResultsTracker.period_end.desc()).limit(1))


def get_results_history(symbol: str, before: dt.date | None = None,
                        basis: str | None = "YoY") -> list[dict]:
    """Prior `results_tracker` rows for one symbol, NEWEST first.

    Used by the expectation baseline (core/processing/expectation.py) to
    source a company's own prior YoY growth prints. `before` excludes the
    period currently being evaluated so it's never used as its own prior
    sample; `basis` defaults to "YoY" since a QoQ print is not a valid
    trailing-expectation input (see expectation.py's seasonality-bias note).
    """
    with session_scope() as s:
        stmt = select(ResultsTracker).where(ResultsTracker.symbol == symbol)
        if before is not None:
            stmt = stmt.where(ResultsTracker.period_end < before)
        if basis is not None:
            stmt = stmt.where(ResultsTracker.basis == basis)
        rows = s.scalars(stmt.order_by(ResultsTracker.period_end.desc())).all()
    return [
        {"period_end": r.period_end, "revenue_growth_pct": r.revenue_growth_pct,
         "profit_growth_pct": r.profit_growth_pct}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Results quarterly (raw, Phase 1) + Event expectations (Phase 1)
# ---------------------------------------------------------------------------
def upsert_results_quarterly(rows: list[dict]) -> int:
    """Upsert raw per-quarter figures on (symbol, period_end)."""
    if not rows:
        return 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(ResultsQuarterly).where(
                    ResultsQuarterly.symbol == r["symbol"],
                    ResultsQuarterly.period_end == r["period_end"],
                )
            )
            if existing is None:
                s.add(ResultsQuarterly(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
    return len(rows)


def upsert_event_expectations(rows: list[dict]) -> int:
    """Upsert expectation/surprise/materiality rows on their natural key."""
    if not rows:
        return 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(EventExpectation).where(
                    EventExpectation.event_source_type == r["event_source_type"],
                    EventExpectation.symbol == r["symbol"],
                    EventExpectation.period_end == r["period_end"],
                    EventExpectation.metric == r["metric"],
                )
            )
            if existing is None:
                s.add(EventExpectation(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
    return len(rows)


def get_event_expectations(symbol: str | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(EventExpectation)
        if symbol is not None:
            stmt = stmt.where(EventExpectation.symbol == symbol)
        rows = s.scalars(stmt.order_by(EventExpectation.period_end.desc())).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"event_source_type": r.event_source_type, "symbol": r.symbol,
         "period_end": r.period_end, "metric": r.metric, "actual_pct": r.actual_pct,
         "expectation_pct": r.expectation_pct, "expectation_source": r.expectation_source,
         "expectation_confidence": r.expectation_confidence,
         "expectation_samples": r.expectation_samples, "surprise_pct": r.surprise_pct,
         "materiality_tier": r.materiality_tier, "materiality_reason": r.materiality_reason}
        for r in rows
    ])


# ---------------------------------------------------------------------------
# Corporate actions
# ---------------------------------------------------------------------------
def upsert_corporate_actions(rows: list[dict]) -> tuple[int, list[int]]:
    """Insert classified corporate actions, skipping duplicates by
    dedupe_hash. Returns (inserted_count, inserted_ids) — the ids let the
    caller run incremental materiality (Phase 2) on just the new rows."""
    if not rows:
        return 0, []
    inserted_ids: list[int] = []
    with session_scope() as s:
        existing = set(s.scalars(select(CorporateAction.dedupe_hash)).all())
        for r in rows:
            if r["dedupe_hash"] in existing:
                continue
            obj = CorporateAction(**r)
            s.add(obj)
            existing.add(r["dedupe_hash"])
            s.flush()  # assign obj.id before commit
            inserted_ids.append(obj.id)
    return len(inserted_ids), inserted_ids


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


def get_corporate_actions_for_backfill() -> list[dict]:
    """Every stored corporate_actions row with the fields the Phase 1.5
    backfill needs to re-derive and (where warranted) correct a
    classification: id, current classification, and the stored summary text
    (the only text persisted — the original un-truncated raw_text is not
    kept anywhere, a documented limitation, not something this function can
    fix)."""
    with session_scope() as s:
        rows = s.scalars(select(CorporateAction)).all()
    return [
        {"id": r.id, "symbol": r.symbol, "announcement_date": r.announcement_date,
         "event_summary": r.event_summary, "event_type": r.event_type,
         "impact_tag": r.impact_tag, "priority": r.priority, "dedupe_hash": r.dedupe_hash}
        for r in rows
    ]


def apply_corporate_action_corrections(updates: list[dict]) -> int:
    """Apply a batch of per-row updates by id (Phase 1.5 backfill).

    Each dict must have "id" plus whichever of dedupe_hash / event_type /
    impact_tag / priority / original_event_type / original_impact_tag /
    reclassified_at / reclassification_reason it wants to set. One
    transaction for the whole batch — atomic, rolls back entirely on error.
    """
    if not updates:
        return 0
    with session_scope() as s:
        for u in updates:
            obj = s.get(CorporateAction, u["id"])
            if obj is None:
                continue
            for k, v in u.items():
                if k == "id":
                    continue
                setattr(obj, k, v)
    return len(updates)


def get_corporate_actions_by_type(event_types: list[str],
                                  ids: list[int] | None = None) -> list[dict]:
    """corporate_actions rows of the given event_type(s), optionally
    restricted to specific ids (used for incremental materiality after a
    live ingestion) — Phase 2."""
    with session_scope() as s:
        stmt = select(CorporateAction).where(CorporateAction.event_type.in_(event_types))
        if ids is not None:
            stmt = stmt.where(CorporateAction.id.in_(ids))
        rows = s.scalars(stmt).all()
    return [
        {"id": r.id, "symbol": r.symbol, "announcement_date": r.announcement_date,
         "event_summary": r.event_summary, "event_type": r.event_type}
        for r in rows
    ]


def get_latest_close(symbol: str) -> float | None:
    with session_scope() as s:
        row = s.scalar(
            select(PriceHistory)
            .where(PriceHistory.symbol == symbol)
            .order_by(PriceHistory.trade_date.desc())
            .limit(1)
        )
    return row.close if row else None


def get_trailing_revenue(symbol: str, quarters: int = 4) -> float | None:
    """Sum of the most recent `quarters` raw revenue figures from
    results_quarterly (Phase 1) — the denominator for Large Order Win
    materiality. None if no rows exist for this symbol at all."""
    with session_scope() as s:
        rows = s.scalars(
            select(ResultsQuarterly)
            .where(ResultsQuarterly.symbol == symbol)
            .order_by(ResultsQuarterly.period_end.desc())
            .limit(quarters)
        ).all()
    if not rows:
        return None
    values = [r.revenue_actual for r in rows if r.revenue_actual is not None]
    return sum(values) if values else None


def upsert_corp_action_materiality(rows: list[dict]) -> int:
    """Upsert on corporate_action_id (1:1 with corporate_actions)."""
    if not rows:
        return 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(CorporateActionMateriality).where(
                    CorporateActionMateriality.corporate_action_id == r["corporate_action_id"]
                )
            )
            if existing is None:
                s.add(CorporateActionMateriality(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
    return len(rows)


def get_corp_action_materiality(event_type: str | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(CorporateActionMateriality)
        if event_type is not None:
            stmt = stmt.where(CorporateActionMateriality.event_type == event_type)
        rows = s.scalars(stmt).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {"corporate_action_id": r.corporate_action_id, "symbol": r.symbol,
         "event_type": r.event_type, "magnitude_value": r.magnitude_value,
         "magnitude_unit": r.magnitude_unit, "denominator_value": r.denominator_value,
         "denominator_type": r.denominator_type, "materiality_tier": r.materiality_tier,
         "materiality_reason": r.materiality_reason}
        for r in rows
    ])


def upsert_event_market_reaction(rows: list[dict]) -> int:
    """Upsert on corporate_action_id (1:1 with corporate_actions) — Phase 3."""
    if not rows:
        return 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(EventMarketReaction).where(
                    EventMarketReaction.corporate_action_id == r["corporate_action_id"]
                )
            )
            if existing is None:
                s.add(EventMarketReaction(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
    return len(rows)


def get_event_market_reaction(reaction_state: str | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(EventMarketReaction)
        if reaction_state is not None:
            stmt = stmt.where(EventMarketReaction.reaction_state == reaction_state)
        rows = s.scalars(stmt).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {c.name: getattr(r, c.name) for c in EventMarketReaction.__table__.columns}
        for r in rows
    ])


def get_events_for_signal_engine(ids: list[int] | None = None) -> list[dict]:
    """Every corporate_actions row merged with its materiality (Phase 2) and
    market reaction (Phase 3) rows, where they exist — Phase 5's evidence
    input. Uses plain Python-side joins (small tables, simplicity over
    micro-optimizing a SQL join) rather than a new denormalized view.
    Missing materiality/reaction is represented as None fields, never
    fabricated — the signal engine turns that into UNKNOWN evidence."""
    with session_scope() as s:
        ca_stmt = select(CorporateAction)
        if ids is not None:
            ca_stmt = ca_stmt.where(CorporateAction.id.in_(ids))
        actions = s.scalars(ca_stmt).all()
        materiality_by_id = {
            m.corporate_action_id: m for m in s.scalars(select(CorporateActionMateriality)).all()
        }
        reaction_by_id = {
            r.corporate_action_id: r for r in s.scalars(select(EventMarketReaction)).all()
        }

    out = []
    for a in actions:
        m = materiality_by_id.get(a.id)
        r = reaction_by_id.get(a.id)
        out.append({
            "id": a.id, "symbol": a.symbol, "event_type": a.event_type,
            "impact_tag": a.impact_tag, "announcement_date": a.announcement_date,
            "materiality_tier": m.materiality_tier if m else "UNKNOWN",
            "reaction_state": r.reaction_state if r else "UNKNOWN",
            "continuation_state": r.continuation_state if r else "INSUFFICIENT_DATA",
            "event_alignment": r.event_alignment if r else "UNKNOWN",
            "relative_return_5d": r.relative_return_5d if r else None,
            "volume_ratio_day0": r.volume_ratio_day0 if r else None,
        })
    return out


def get_nearby_expectation_surprise(symbol: str, before: dt.date) -> dict | None:
    """The most recent event_expectations row for this symbol at or before
    `before` (a corporate action's own date), used to cross-reference a
    Results-based surprise as supporting/contradicting evidence for a
    corp-action-driven signal. None if nothing exists — never fabricated;
    given Phase 2.5's finding that expectation is currently UNKNOWN for
    virtually every symbol, this will usually return None today."""
    with session_scope() as s:
        row = s.scalar(
            select(EventExpectation)
            .where(EventExpectation.symbol == symbol, EventExpectation.period_end <= before,
                  EventExpectation.expectation_pct.is_not(None))
            .order_by(EventExpectation.period_end.desc())
            .limit(1)
        )
    if row is None:
        return None
    return {"metric": row.metric, "surprise_pct": row.surprise_pct,
           "expectation_source": row.expectation_source, "period_end": row.period_end}


def upsert_event_trade_signal(rows: list[dict]) -> int:
    """Upsert on corporate_action_id (1:1 with corporate_actions) — Phase 5."""
    if not rows:
        return 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(EventTradeSignal).where(
                    EventTradeSignal.corporate_action_id == r["corporate_action_id"]
                )
            )
            if existing is None:
                s.add(EventTradeSignal(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
    return len(rows)


def get_event_trade_signals(direction: str | None = None) -> pd.DataFrame:
    with session_scope() as s:
        stmt = select(EventTradeSignal)
        if direction is not None:
            stmt = stmt.where(EventTradeSignal.direction == direction)
        rows = s.scalars(stmt).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {c.name: getattr(r, c.name) for c in EventTradeSignal.__table__.columns}
        for r in rows
    ])


def get_symbol_sector_map() -> dict[str, list[str]]:
    """{sector: [nse_symbol, ...]} from symbol_master.sector — Phase 6's
    breadth universe. Includes "Unknown" and small groups; the caller
    (event_intelligence.sector_universe.get_universe) applies the
    MIN_CONSTITUENTS / "Unknown" exclusion, not this raw accessor."""
    with session_scope() as s:
        rows = s.scalars(select(SymbolMaster).where(SymbolMaster.nse_symbol.is_not(None))).all()
    out: dict[str, list[str]] = {}
    for r in rows:
        sector = r.sector or "Unknown"
        out.setdefault(sector, []).append(r.nse_symbol)
    return out


def upsert_sector_theme_state(rows: list[dict]) -> int:
    """Upsert on (as_of_date, sector_or_theme) — Phase 6."""
    if not rows:
        return 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(SectorThemeState).where(
                    SectorThemeState.as_of_date == r["as_of_date"],
                    SectorThemeState.sector_or_theme == r["sector_or_theme"],
                )
            )
            if existing is None:
                s.add(SectorThemeState(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
    return len(rows)


def get_sector_theme_history(sector_or_theme: str) -> list[dict]:
    """Full stored history for one sector/theme, oldest first — used by the
    pipeline for hysteresis (needs `recent_raw_states`) and by historical
    validation."""
    with session_scope() as s:
        rows = s.scalars(
            select(SectorThemeState)
            .where(SectorThemeState.sector_or_theme == sector_or_theme)
            .order_by(SectorThemeState.as_of_date.asc())
        ).all()
    return [{"as_of_date": r.as_of_date, "raw_state": r.raw_state,
            "confirmed_state": r.confirmed_state, "days_in_state": r.days_in_state}
           for r in rows]


def get_latest_sector_theme_state() -> pd.DataFrame:
    with session_scope() as s:
        latest_date = s.scalar(select(SectorThemeState.as_of_date)
                               .order_by(SectorThemeState.as_of_date.desc()).limit(1))
        if latest_date is None:
            return pd.DataFrame()
        rows = s.scalars(
            select(SectorThemeState).where(SectorThemeState.as_of_date == latest_date)
        ).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {c.name: getattr(r, c.name) for c in SectorThemeState.__table__.columns}
        for r in rows
    ])


def get_latest_event_signal_per_symbol(symbols: set[str],
                                       since: dt.date) -> dict[str, dict]:
    """The most recent event_trade_signal row (by announcement_date) for
    each of `symbols`, restricted to events on or after `since` (the
    recency window — Phase 7 does not treat a stale, months-old event as
    "the company's current catalyst"). {symbol: row_dict}; a symbol with no
    qualifying row is simply absent — never fabricated as an empty entry."""
    with session_scope() as s:
        rows = s.scalars(
            select(EventTradeSignal).where(
                EventTradeSignal.symbol.in_(symbols),
                EventTradeSignal.announcement_date >= since,
            ).order_by(EventTradeSignal.announcement_date.desc())
        ).all()
    out: dict[str, dict] = {}
    for r in rows:
        if r.symbol in out:
            continue  # already have this symbol's MOST RECENT row (rows are date-descending)
        out[r.symbol] = {
            "corporate_action_id": r.corporate_action_id, "event_type": r.event_type,
            "event_direction": r.event_direction, "materiality_tier": r.materiality_tier,
            "expectation_available": r.expectation_available, "surprise_pct": r.surprise_pct,
            "market_reaction_state": r.market_reaction_state,
            "continuation_state": r.continuation_state,
            "technical_confirmation": r.technical_confirmation,
            "signal_direction": r.direction, "time_horizon": r.time_horizon,
            "evidence_for": json.loads(r.evidence_for_json) if r.evidence_for_json else [],
            "evidence_against": json.loads(r.evidence_against_json) if r.evidence_against_json else [],
        }
    return out


def upsert_sector_stock_cross_reference(rows: list[dict]) -> int:
    """Upsert on (as_of_date, sector_or_theme, symbol) — Phase 7."""
    if not rows:
        return 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(SectorStockCrossReference).where(
                    SectorStockCrossReference.as_of_date == r["as_of_date"],
                    SectorStockCrossReference.sector_or_theme == r["sector_or_theme"],
                    SectorStockCrossReference.symbol == r["symbol"],
                )
            )
            if existing is None:
                s.add(SectorStockCrossReference(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
    return len(rows)


def get_sector_stock_cross_reference(trade_context: str | None = None) -> pd.DataFrame:
    """ALL stored snapshots (every as_of_date ever written), unfiltered by
    date. Phase 9 (live refresh) discovered that a naive caller taking
    `.iloc[0]` of this for "the current as_of_date" breaks the moment a
    second real snapshot accumulates — use
    `get_latest_sector_stock_cross_reference()` instead when only the
    current state is wanted (which is every caller so far)."""
    with session_scope() as s:
        stmt = select(SectorStockCrossReference)
        if trade_context is not None:
            stmt = stmt.where(SectorStockCrossReference.trade_context == trade_context)
        rows = s.scalars(stmt).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {c.name: getattr(r, c.name) for c in SectorStockCrossReference.__table__.columns}
        for r in rows
    ])


def get_latest_sector_stock_cross_reference() -> pd.DataFrame:
    """Only the MOST RECENT as_of_date's rows — mirrors
    `get_latest_sector_theme_state()`'s existing pattern (Phase 6). Added
    Phase 9 after a live refresh produced a second real snapshot and
    exposed that `opportunity_pipeline.py` was implicitly relying on there
    being only one snapshot ever (see the Phase 9 report's DISCOVERED
    ISSUES)."""
    with session_scope() as s:
        latest_date = s.scalar(select(SectorStockCrossReference.as_of_date)
                               .order_by(SectorStockCrossReference.as_of_date.desc()).limit(1))
        if latest_date is None:
            return pd.DataFrame()
        rows = s.scalars(
            select(SectorStockCrossReference).where(SectorStockCrossReference.as_of_date == latest_date)
        ).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {c.name: getattr(r, c.name) for c in SectorStockCrossReference.__table__.columns}
        for r in rows
    ])


def upsert_opportunity(rows: list[dict]) -> int:
    """Upsert on (as_of_date, corporate_action_id) — Phase 8."""
    if not rows:
        return 0
    with session_scope() as s:
        for r in rows:
            existing = s.scalar(
                select(Opportunity).where(
                    Opportunity.as_of_date == r["as_of_date"],
                    Opportunity.corporate_action_id == r["corporate_action_id"],
                )
            )
            if existing is None:
                s.add(Opportunity(**r))
            else:
                for k, v in r.items():
                    setattr(existing, k, v)
    return len(rows)


def get_opportunities(tier: str | None = None, opportunity_type: str | None = None) -> pd.DataFrame:
    """ALL stored snapshots (every as_of_date ever written), unfiltered by
    date — `opportunity` is keyed on (as_of_date, corporate_action_id), the
    same snapshot-table shape as `sector_stock_cross_reference`. No caller
    exists yet (Phase 11 audit: this table isn't wired into any page or
    script), but the moment one is added it must use
    `get_latest_opportunities()` below, not this one — see the Phase 9/
    Phase 10 reports for the identical bug this would otherwise reproduce."""
    with session_scope() as s:
        stmt = select(Opportunity)
        if tier is not None:
            stmt = stmt.where(Opportunity.tier == tier)
        if opportunity_type is not None:
            stmt = stmt.where(Opportunity.opportunity_type == opportunity_type)
        rows = s.scalars(stmt).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {c.name: getattr(r, c.name) for c in Opportunity.__table__.columns}
        for r in rows
    ])


def get_latest_opportunities(tier: str | None = None, opportunity_type: str | None = None) -> pd.DataFrame:
    """Only the MOST RECENT as_of_date's rows — mirrors
    `get_latest_sector_stock_cross_reference()`'s established pattern.
    Added Phase 11 pre-emptively (no caller yet) so that when `opportunity`
    is eventually wired into a page or downstream script, the correct
    latest-only accessor already exists rather than being discovered as a
    bug after a second real snapshot accumulates, as happened twice before."""
    with session_scope() as s:
        latest_date = s.scalar(select(Opportunity.as_of_date)
                               .order_by(Opportunity.as_of_date.desc()).limit(1))
        if latest_date is None:
            return pd.DataFrame()
        stmt = select(Opportunity).where(Opportunity.as_of_date == latest_date)
        if tier is not None:
            stmt = stmt.where(Opportunity.tier == tier)
        if opportunity_type is not None:
            stmt = stmt.where(Opportunity.opportunity_type == opportunity_type)
        rows = s.scalars(stmt).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([
        {c.name: getattr(r, c.name) for c in Opportunity.__table__.columns}
        for r in rows
    ])


def get_recent_corp_action_symbols(days: int = 90) -> list[str]:
    """Distinct symbols with a corporate action in the last `days` days —
    Phase 10's event-driven price universe. Deliberately a SEPARATE query
    from the deal-derived universe `run_live.py` already builds: deals and
    general corporate announcements are different NSE feeds with very
    different symbol breadth (see the Phase 10 report's ROOT CAUSES) — this
    function exists specifically to union the two, not replace either.
    Bounded by `days` (not "ever appeared") so the price-fetch universe
    stays self-maintaining as corporate_actions accumulates history,
    rather than growing without bound."""
    since = dt.datetime.utcnow().date() - dt.timedelta(days=days)
    with session_scope() as s:
        rows = s.scalars(
            select(CorporateAction.symbol)
            .where(CorporateAction.announcement_date >= since)
            .distinct()
        ).all()
    return sorted(rows)


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
