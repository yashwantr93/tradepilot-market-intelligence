"""
Market Cycle tables.

  * `market_cycle_daily`        — append-only, one row per (sector, trade_date).
  * `market_cycle_transitions`  — append-only log of CONFIRMED stage changes only,
                                  so "when did Banking leave Strong Trend, and why?"
                                  is answerable without scanning the daily table.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Date, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from intelligence_v2.models.base import Base


class MarketCycleDaily(Base):
    __tablename__ = "market_cycle_daily"
    __table_args__ = (UniqueConstraint("trade_date", "sector", name="uq_cycle_date_sector"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[dt.date] = mapped_column(Date, index=True)
    sector: Mapped[str] = mapped_column(String, index=True)

    raw_stage: Mapped[str] = mapped_column(String)          # pre-hysteresis threshold result
    stage: Mapped[str] = mapped_column(String, index=True)  # confirmed stage (one of 7)
    prior_stage: Mapped[str | None] = mapped_column(String)
    days_in_stage: Mapped[int] = mapped_column(Integer)
    stage_start_date: Mapped[dt.date | None] = mapped_column(Date)

    # Explainability payloads (JSON-encoded list / plain strings).
    reasons: Mapped[str] = mapped_column(Text)              # JSON list of bullet strings
    possible_behaviour: Mapped[str | None] = mapped_column(Text)
    confidence_notes: Mapped[str | None] = mapped_column(Text)  # JSON list of caveats

    # Rule provenance — which documented rule number fired, for auditability.
    rule_order: Mapped[int | None] = mapped_column(Integer)
    matched_by_fallback: Mapped[str] = mapped_column(String, default="N")  # Y/N

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class MarketCycleTransition(Base):
    __tablename__ = "market_cycle_transitions"
    __table_args__ = (
        UniqueConstraint("sector", "transition_date", "to_stage", name="uq_transition"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector: Mapped[str] = mapped_column(String, index=True)
    transition_date: Mapped[dt.date] = mapped_column(Date, index=True)
    from_stage: Mapped[str | None] = mapped_column(String)
    to_stage: Mapped[str] = mapped_column(String)
    days_in_previous_stage: Mapped[int | None] = mapped_column(Integer)
    reasons: Mapped[str] = mapped_column(Text)  # JSON list — why the new stage was assigned
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
