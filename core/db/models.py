"""
SQLAlchemy ORM models — the Phase 1 schema.

Dialect-agnostic (SQLite now, Postgres later via DATABASE_URL). No scoring tables
in Phase 1; the watchlist is rule-based only.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> dt.datetime:
    return dt.datetime.utcnow()


class SymbolMaster(Base):
    __tablename__ = "symbol_master"

    isin: Mapped[str] = mapped_column(String, primary_key=True)
    nse_symbol: Mapped[str | None] = mapped_column(String, index=True)
    bse_code: Mapped[str | None] = mapped_column(String, index=True)
    company_name: Mapped[str] = mapped_column(String)
    sector: Mapped[str | None] = mapped_column(String, index=True)
    instrument_token: Mapped[int | None] = mapped_column(Integer, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class PriceHistory(Base):
    """Daily OHLCV per symbol. Feeds all technical fields."""

    __tablename__ = "price_history"
    __table_args__ = (UniqueConstraint("symbol", "trade_date", name="uq_price_sym_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)


class _DealBase:
    """Shared columns for bulk and block deals."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    exchange: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String, index=True)
    isin: Mapped[str | None] = mapped_column(String, index=True)
    client_name: Mapped[str] = mapped_column(String)
    txn_type: Mapped[str] = mapped_column(String)  # BUY / SELL
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    value: Mapped[float] = mapped_column(Float)  # qty * price (₹)
    dedupe_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class BulkDeal(_DealBase, Base):
    __tablename__ = "bulk_deals"


class BlockDeal(_DealBase, Base):
    __tablename__ = "block_deals"


class DailyWatchlist(Base):
    """Phase 1 output — rule-based, with descriptive technical fields. No score."""

    __tablename__ = "daily_watchlist"
    __table_args__ = (UniqueConstraint("trade_date", "symbol", name="uq_wl_date_sym"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    isin: Mapped[str | None] = mapped_column(String)
    company_name: Mapped[str | None] = mapped_column(String)
    sector: Mapped[str | None] = mapped_column(String)
    current_price: Mapped[float | None] = mapped_column(Float)
    catalyst_tag: Mapped[str | None] = mapped_column(String)       # primary catalyst
    reasons: Mapped[str | None] = mapped_column(Text)              # JSON list of tags
    above_20_sma: Mapped[str | None] = mapped_column(String)       # "Y" / "N"
    relative_strength: Mapped[str | None] = mapped_column(String)  # Strong/Neutral/Weak
    volume_expansion: Mapped[str | None] = mapped_column(String)   # "Y" / "N"
    sma_20: Mapped[float | None] = mapped_column(Float)
    high_52w: Mapped[float | None] = mapped_column(Float)
    low_52w: Mapped[float | None] = mapped_column(Float)
    dist_52w_high_pct: Mapped[float | None] = mapped_column(Float)
    dist_52w_low_pct: Mapped[float | None] = mapped_column(Float)
    technical_status: Mapped[str | None] = mapped_column(String)   # Ready/Monitor/Avoid
    deal_value: Mapped[float | None] = mapped_column(Float)
    net_qty: Mapped[int | None] = mapped_column(Integer)
    rule_count: Mapped[int] = mapped_column(Integer, default=0)    # display sort, NOT a score
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class FiiDiiActivity(Base):
    """Daily institutional cash-segment flows (₹ Cr). Forward-accumulating."""

    __tablename__ = "fii_dii_activity"
    __table_args__ = (UniqueConstraint("trade_date", "segment", name="uq_fiidii_date_seg"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    segment: Mapped[str] = mapped_column(String, default="CASH")
    fii_buy: Mapped[float] = mapped_column(Float)
    fii_sell: Mapped[float] = mapped_column(Float)
    fii_net: Mapped[float] = mapped_column(Float)
    dii_buy: Mapped[float] = mapped_column(Float)
    dii_sell: Mapped[float] = mapped_column(Float)
    dii_net: Mapped[float] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class SectorRotation(Base):
    """Daily rule-based sector classification (no scores)."""

    __tablename__ = "sector_rotation"
    __table_args__ = (UniqueConstraint("trade_date", "sector", name="uq_sector_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    sector: Mapped[str] = mapped_column(String, index=True)
    perf_20d: Mapped[float | None] = mapped_column(Float)
    nifty_perf_20d: Mapped[float | None] = mapped_column(Float)
    rs_vs_nifty: Mapped[float | None] = mapped_column(Float)
    above_20_sma: Mapped[str | None] = mapped_column(String)  # Y/N
    above_50_sma: Mapped[str | None] = mapped_column(String)  # Y/N
    trend_status: Mapped[str] = mapped_column(String)  # Strong/Improving/Neutral/Weak
    data_method: Mapped[str | None] = mapped_column(String)  # index / proxy / basket
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class InstitutionalWatchlist(Base):
    """Second, independent watchlist source: stocks in strong/improving sectors."""

    __tablename__ = "institutional_watchlist"
    __table_args__ = (UniqueConstraint("trade_date", "symbol", name="uq_instwl_date_sym"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    sector: Mapped[str] = mapped_column(String)
    sector_trend: Mapped[str] = mapped_column(String)       # sector's trend_status
    relative_strength: Mapped[str | None] = mapped_column(String)  # Strong/Neutral/Weak
    above_20_sma: Mapped[str | None] = mapped_column(String)
    current_price: Mapped[float | None] = mapped_column(Float)
    sma_20: Mapped[float | None] = mapped_column(Float)
    high_52w: Mapped[float | None] = mapped_column(Float)
    low_52w: Mapped[float | None] = mapped_column(Float)
    dist_52w_high_pct: Mapped[float | None] = mapped_column(Float)
    dist_52w_low_pct: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class ResultsTracker(Base):
    """Quarterly earnings results — fourth independent watchlist source."""

    __tablename__ = "results_tracker"
    __table_args__ = (UniqueConstraint("symbol", "period_end", name="uq_results_sym_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    company_name: Mapped[str | None] = mapped_column(String)
    quarter: Mapped[str] = mapped_column(String)          # e.g. "Q4 FY26"
    period_end: Mapped[dt.date] = mapped_column(Date, index=True)
    revenue_growth_pct: Mapped[float | None] = mapped_column(Float)
    profit_growth_pct: Mapped[float | None] = mapped_column(Float)
    margin_change_pct: Mapped[float | None] = mapped_column(Float)
    result_classification: Mapped[str] = mapped_column(String, index=True)  # Strong/Neutral/Weak
    basis: Mapped[str | None] = mapped_column(String)     # YoY / QoQ
    source: Mapped[str] = mapped_column(String)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class CorporateAction(Base):
    """Corporate actions & announcements — third independent watchlist source."""

    __tablename__ = "corporate_actions"
    __table_args__ = (UniqueConstraint("dedupe_hash", name="uq_corpaction_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    announcement_date: Mapped[dt.date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    company_name: Mapped[str | None] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String, index=True)
    event_summary: Mapped[str | None] = mapped_column(Text)
    impact_tag: Mapped[str] = mapped_column(String)        # Bullish/Neutral/Bearish
    priority: Mapped[str] = mapped_column(String, index=True)  # High/Medium/Low
    source: Mapped[str] = mapped_column(String)            # NSE_ANN / NSE_CA
    dedupe_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class CombinedWatchlist(Base):
    """Confluence of the deal watchlist and institutional watchlist (tiered)."""

    __tablename__ = "combined_watchlist"
    __table_args__ = (UniqueConstraint("trade_date", "symbol", name="uq_combined_date_sym"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    sector: Mapped[str | None] = mapped_column(String)
    catalyst: Mapped[str | None] = mapped_column(String)
    relative_strength: Mapped[str | None] = mapped_column(String)
    above_20_sma: Mapped[str | None] = mapped_column(String)
    volume_expansion: Mapped[str | None] = mapped_column(String)
    technical_status: Mapped[str | None] = mapped_column(String)
    in_deal: Mapped[str] = mapped_column(String)            # Y/N
    in_institutional: Mapped[str] = mapped_column(String)   # Y/N
    tier: Mapped[int] = mapped_column(Integer, index=True)  # 1 / 2 / 3
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class Signal(Base):
    """Signal Validation Layer — one row per (signal, engine) with forward returns.

    Measurement only: tracks how each engine's signals perform after generation.
    No scoring, no prediction — just stored facts.
    """

    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("signal_date", "symbol", "source_engine",
                                       "signal_type", name="uq_signal_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_date: Mapped[dt.date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    source_engine: Mapped[str] = mapped_column(String, index=True)
    signal_type: Mapped[str | None] = mapped_column(String)
    entry_price: Mapped[float | None] = mapped_column(Float)
    ret_1d: Mapped[float | None] = mapped_column(Float)
    ret_5d: Mapped[float | None] = mapped_column(Float)
    ret_20d: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending/partial/evaluated/no_price
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class JobRun(Base):
    """Audit trail for every pipeline run — powers a future Data-Health panel."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    duration_s: Mapped[float | None] = mapped_column(Float)
    rows_in: Mapped[int | None] = mapped_column(Integer)
    rows_out: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="running")  # running/ok/error
    error: Mapped[str | None] = mapped_column(Text)


class DeadLetter(Base):
    """Quarantine for rows that fail validation."""

    __tablename__ = "dead_letter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String)
    payload_json: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
