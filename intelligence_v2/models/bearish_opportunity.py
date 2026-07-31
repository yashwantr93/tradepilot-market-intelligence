"""
Bearish Opportunity — append-only daily stock classification table.

One row per (symbol, trade_date). Mirrors `EarlyMomentumDaily`'s shape exactly
(same metric fields, since both are computed by the same shared
`momentum_metrics.compute_stock_metrics()`), storing the category, every
signal's boolean outcome, the human-readable reasons, the within-category
rank, and the raw metrics behind them so any classification can be audited
without recomputation.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from intelligence_v2.models.base import Base


class BearishOpportunityDaily(Base):
    __tablename__ = "bearish_opportunity_daily"
    __table_args__ = (UniqueConstraint("trade_date", "symbol", name="uq_bearish_date_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)

    category: Mapped[str] = mapped_column(String, index=True)
    rank_in_category: Mapped[int] = mapped_column(Integer)
    signal_count: Mapped[int] = mapped_column(Integer)

    # Context (from Phase 1 / Phase 2 / V1 symbol master)
    sector: Mapped[str | None] = mapped_column(String)
    sector_state: Mapped[str | None] = mapped_column(String)
    cycle_stage: Mapped[str | None] = mapped_column(String)

    # Metrics (computed from V1 price_history via the shared RS engine — no new indicators)
    close: Mapped[float | None] = mapped_column(Float)
    perf_1w: Mapped[float | None] = mapped_column(Float)
    perf_1m: Mapped[float | None] = mapped_column(Float)
    perf_3m: Mapped[float | None] = mapped_column(Float)
    rs_1w: Mapped[float | None] = mapped_column(Float)
    rs_1m: Mapped[float | None] = mapped_column(Float)
    rs_3m: Mapped[float | None] = mapped_column(Float)
    rs_slope: Mapped[float | None] = mapped_column(Float)
    above_20_sma: Mapped[str | None] = mapped_column(String)
    above_50_sma: Mapped[str | None] = mapped_column(String)
    above_200_sma: Mapped[str | None] = mapped_column(String)
    volume_ratio: Mapped[float | None] = mapped_column(Float)
    dist_52w_high_pct: Mapped[float | None] = mapped_column(Float)
    sector_rs_1m: Mapped[float | None] = mapped_column(Float)  # ranking key only (Phase 1's field)

    # Explainability
    signals: Mapped[str] = mapped_column(Text)   # JSON {signal_key: bool}
    reasons: Mapped[str] = mapped_column(Text)   # JSON list of satisfied-signal labels
    missing: Mapped[str | None] = mapped_column(Text)  # JSON list of unsatisfied labels
    category_reason: Mapped[str | None] = mapped_column(Text)  # why this category

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
