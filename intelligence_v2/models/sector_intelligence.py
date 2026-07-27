"""
Sector Intelligence — append-only daily classification table.

Unlike V1's `sector_rotation` (a single overwritten "today" row per sector),
this table grows one row per (sector, trade_date) forever. That is the
structural property that makes "has this sector led for six months?"
answerable — see docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §1.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from intelligence_v2.models.base import Base


class SectorIntelligenceDaily(Base):
    __tablename__ = "sector_intelligence_daily"
    __table_args__ = (UniqueConstraint("trade_date", "sector", name="uq_secint_date_sector"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    sector: Mapped[str] = mapped_column(String, index=True)

    # Synthetic sector "index" value that day (rebased basket average, see
    # processors/sector_prices.py) — kept for charting, not a real tradable level.
    close: Mapped[float] = mapped_column(Float)

    # Absolute performance, per horizon (%).
    perf_1w: Mapped[float | None] = mapped_column(Float)
    perf_1m: Mapped[float | None] = mapped_column(Float)
    perf_3m: Mapped[float | None] = mapped_column(Float)
    perf_6m: Mapped[float | None] = mapped_column(Float)
    perf_1y: Mapped[float | None] = mapped_column(Float)

    # Benchmark (Nifty 50) performance over the identical windows/dates —
    # stored alongside so relative strength is always independently auditable.
    nifty_perf_1w: Mapped[float | None] = mapped_column(Float)
    nifty_perf_1m: Mapped[float | None] = mapped_column(Float)
    nifty_perf_3m: Mapped[float | None] = mapped_column(Float)
    nifty_perf_6m: Mapped[float | None] = mapped_column(Float)
    nifty_perf_1y: Mapped[float | None] = mapped_column(Float)

    # Relative strength = sector perf − nifty perf, per horizon (%).
    rs_1w: Mapped[float | None] = mapped_column(Float)
    rs_1m: Mapped[float | None] = mapped_column(Float)
    rs_3m: Mapped[float | None] = mapped_column(Float)
    rs_6m: Mapped[float | None] = mapped_column(Float)
    rs_1y: Mapped[float | None] = mapped_column(Float)

    momentum_1m: Mapped[float | None] = mapped_column(Float)  # rs_1m(t) - rs_1m(t-20d)

    above_20_sma: Mapped[str | None] = mapped_column(String)   # Y/N/None (insufficient history)
    above_50_sma: Mapped[str | None] = mapped_column(String)
    above_200_sma: Mapped[str | None] = mapped_column(String)

    consistency_pct: Mapped[float | None] = mapped_column(Float)  # % of trailing 120 stored days = "Strong Leader"

    raw_state: Mapped[str] = mapped_column(String)     # pre-hysteresis threshold classification
    state: Mapped[str] = mapped_column(String, index=True)  # confirmed (hysteresis-applied) — one of 7
    days_in_state: Mapped[int] = mapped_column(Integer)

    # Provenance — how many basket members contributed + the source, for
    # transparency when a basket is thin (e.g. Metals: 2/5 members available).
    data_method: Mapped[str] = mapped_column(String)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
