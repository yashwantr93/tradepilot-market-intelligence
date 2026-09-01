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
    impact_tag: Mapped[str] = mapped_column(String)        # Bullish/Neutral/Bearish/Ambiguous
    priority: Mapped[str] = mapped_column(String, index=True)  # High/Medium/Low
    source: Mapped[str] = mapped_column(String)            # NSE_ANN / NSE_CA
    dedupe_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

    # --- Phase 1.5 provenance (nullable — populated ONLY when a backfill
    # correction actually changes a row's classification; a row nobody has
    # ever corrected keeps all four as NULL). See
    # core/pipelines/corp_actions_backfill.py. Added via a small idempotent
    # ALTER TABLE migration in core/db/engine.py, since this table already
    # holds production rows (unlike Phase 1's brand-new tables).
    original_event_type: Mapped[str | None] = mapped_column(String)
    original_impact_tag: Mapped[str | None] = mapped_column(String)
    reclassified_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    reclassification_reason: Mapped[str | None] = mapped_column(String)


class ResultsQuarterly(Base):
    """Raw per-quarter figures — Phase 1 Event Intelligence Foundation.

    Purely additive alongside `results_tracker` (never modified): stores the
    RAW revenue/profit/margin for every quarter returned by a fetch, not just
    the single latest-quarter growth comparison `results_tracker` has always
    stored. This is what lets a future trailing-average expectation baseline
    (see `EventExpectation` below) be computed without re-fetching history —
    the data was already being pulled from yfinance and discarded before
    Phase 1; this table just stops discarding it.
    """

    __tablename__ = "results_quarterly"
    __table_args__ = (UniqueConstraint("symbol", "period_end", name="uq_resq_sym_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    period_end: Mapped[dt.date] = mapped_column(Date, index=True)
    revenue_actual: Mapped[float | None] = mapped_column(Float)
    profit_actual: Mapped[float | None] = mapped_column(Float)
    margin_pct: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class EventExpectation(Base):
    """Expectation / Surprise / Materiality — Phase 1 Event Intelligence Foundation.

    One row per (event_source_type, symbol, period_end, metric). Phase 1 only
    ever writes event_source_type="results" (the one category with enough
    reliable historical data to support an internally-derived expectation —
    see core/processing/expectation.py). The shape intentionally generalizes
    to other event categories for a later phase, but nothing outside Results
    populates it yet.

    Deliberately NOT a replacement for `results_tracker` — the actual/growth
    figures stay there; this table only adds what was EXPECTED and how
    material the surprise was, so existing consumers of `results_tracker`
    (Results Watchlist, opportunity_hub) are completely unaffected.
    """

    __tablename__ = "event_expectations"
    __table_args__ = (
        UniqueConstraint("event_source_type", "symbol", "period_end", "metric",
                         name="uq_expect_source_sym_period_metric"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_source_type: Mapped[str] = mapped_column(String, index=True)  # "results"
    symbol: Mapped[str] = mapped_column(String, index=True)
    period_end: Mapped[dt.date] = mapped_column(Date, index=True)
    metric: Mapped[str] = mapped_column(String)  # "revenue_growth_pct" | "profit_growth_pct"
    actual_pct: Mapped[float | None] = mapped_column(Float)
    expectation_pct: Mapped[float | None] = mapped_column(Float)
    expectation_source: Mapped[str] = mapped_column(String)
    # "internal_trailing_avg" | "analyst_consensus" | "unknown" — analyst_consensus
    # is a reserved value; nothing in Phase 1 produces it (no paid feed integrated).
    expectation_confidence: Mapped[str | None] = mapped_column(String)  # LOW/MEDIUM/None
    expectation_samples: Mapped[int | None] = mapped_column(Integer)  # prior prints used
    surprise_pct: Mapped[float | None] = mapped_column(Float)
    materiality_tier: Mapped[str] = mapped_column(String)  # LOW/MEDIUM/HIGH/TRANSFORMATIONAL/UNKNOWN
    materiality_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class CorporateActionMateriality(Base):
    """Materiality for a single corporate_actions row — Phase 2.

    One row per corporate_actions.id (1:1, not a separate identity of its
    own) — purely additive, `corporate_actions` itself is never modified by
    this table. Only Dividend and Large Order Win are currently populated
    (see core/pipelines/corp_action_materiality_pipeline.py); every other
    event type intentionally has no row here yet — absence means "not
    attempted", not "materiality is zero".
    """

    __tablename__ = "corporate_action_materiality"
    __table_args__ = (UniqueConstraint("corporate_action_id",
                                       name="uq_ca_materiality_action_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corporate_action_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    magnitude_value: Mapped[float | None] = mapped_column(Float)
    magnitude_unit: Mapped[str | None] = mapped_column(String)  # PER_SHARE_INR/INR_CR/USD_MN
    denominator_value: Mapped[float | None] = mapped_column(Float)
    denominator_type: Mapped[str | None] = mapped_column(String)  # latest_close/trailing_4q_revenue
    denominator_asof: Mapped[dt.date | None] = mapped_column(Date)
    materiality_tier: Mapped[str] = mapped_column(String)  # LOW/MEDIUM/HIGH/TRANSFORMATIONAL/UNKNOWN
    materiality_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class EventMarketReaction(Base):
    """Event-relative price/volume reaction — Phase 3 (event_intelligence/).

    One row per corporate_actions.id (1:1, purely additive — corporate_actions
    itself is never modified). Written by `event_intelligence/pipeline.py`,
    which is the one place allowed to import both `core.db.repository` (V1)
    and `intelligence_v2.processors.shared_relative_strength` (V2's
    calendar-aligned RS primitives) — see that package's docstring for why
    this doesn't violate the V1/V2 isolation rule (core/ and intelligence_v2/
    still never import each other directly; this is a third, bridging
    package, exactly as the Architecture Freeze anticipated).

    Windows persisted: +1, +5, +10, +20 sessions from the event's resolved
    "day 0" (the first trading session on or after announcement_date — see
    event_intelligence/reaction_windows.py for why forward-resolution, not
    backward, is correct here). `max_window_available` records how far the
    calculation could actually reach for this event — absence of a
    longer-window value means "not yet enough price history," not "zero."
    """

    __tablename__ = "event_market_reaction"
    __table_args__ = (UniqueConstraint("corporate_action_id",
                                       name="uq_event_reaction_action_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corporate_action_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    impact_tag: Mapped[str] = mapped_column(String)  # event's own direction — never overwritten
    announcement_date: Mapped[dt.date] = mapped_column(Date, index=True)
    anchor_date: Mapped[dt.date | None] = mapped_column(Date)  # resolved session-0 trading date
    pre_event_close: Mapped[float | None] = mapped_column(Float)
    pre_event_close_date: Mapped[dt.date | None] = mapped_column(Date)
    gap_pct: Mapped[float | None] = mapped_column(Float)          # day0 open vs pre-event close
    volume_ratio_day0: Mapped[float | None] = mapped_column(Float)  # day0 volume / trailing 20d avg

    return_1d: Mapped[float | None] = mapped_column(Float)
    benchmark_return_1d: Mapped[float | None] = mapped_column(Float)
    relative_return_1d: Mapped[float | None] = mapped_column(Float)
    return_5d: Mapped[float | None] = mapped_column(Float)
    benchmark_return_5d: Mapped[float | None] = mapped_column(Float)
    relative_return_5d: Mapped[float | None] = mapped_column(Float)
    return_10d: Mapped[float | None] = mapped_column(Float)
    benchmark_return_10d: Mapped[float | None] = mapped_column(Float)
    relative_return_10d: Mapped[float | None] = mapped_column(Float)
    return_20d: Mapped[float | None] = mapped_column(Float)
    benchmark_return_20d: Mapped[float | None] = mapped_column(Float)
    relative_return_20d: Mapped[float | None] = mapped_column(Float)

    mfe_pct: Mapped[float | None] = mapped_column(Float)  # max favourable excursion (event-direction-relative)
    mae_pct: Mapped[float | None] = mapped_column(Float)  # max adverse excursion (event-direction-relative)

    max_window_available: Mapped[int | None] = mapped_column(Integer)  # 1/5/10/20, or None
    reaction_state: Mapped[str] = mapped_column(String, index=True)     # see reaction_classifier.py
    reaction_reason: Mapped[str | None] = mapped_column(Text)
    continuation_state: Mapped[str] = mapped_column(String)             # CONTINUATION/PARTIAL_REVERSAL/REVERSAL/INSUFFICIENT_DATA
    event_alignment: Mapped[str] = mapped_column(String)                # ALIGNED/CONTRADICTS/AMBIGUOUS/NOT_APPLICABLE

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class EventTradeSignal(Base):
    """LONG / SHORT / NO_TRADE decision-support signal — Phase 5.

    One row per corporate_actions.id (1:1, purely additive — same pattern as
    CorporateActionMateriality/EventMarketReaction). Written by
    `event_intelligence/signal_pipeline.py`, which reads V1 event data,
    materiality, reaction (all via `core.db.repository`) AND V2 technical
    confirmation (via `intelligence_v2.contracts`) — the same bridging
    package, same V1/V2-isolation reasoning, as Phase 3's Market Reaction.

    `signal_strength` is explicitly HEURISTIC (evidence-count based), NOT an
    empirically validated score — Phase 4 found no dimension here predicts
    forward returns on the current (76-event) sample. `evidence_for_json`/
    `evidence_against_json` store JSON lists of short strings (mirrors the
    existing `DailyWatchlist.reasons` JSON-text convention) rather than a
    fixed set of columns, since the evidence set is inherently variable.
    """

    __tablename__ = "event_trade_signal"
    __table_args__ = (UniqueConstraint("corporate_action_id", name="uq_trade_signal_action_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    corporate_action_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String)
    announcement_date: Mapped[dt.date] = mapped_column(Date, index=True)
    event_direction: Mapped[str] = mapped_column(String)  # Bullish/Bearish/Neutral/Ambiguous

    materiality_tier: Mapped[str] = mapped_column(String)
    expectation_available: Mapped[bool] = mapped_column(Boolean)
    surprise_pct: Mapped[float | None] = mapped_column(Float)
    market_reaction_state: Mapped[str] = mapped_column(String)
    continuation_state: Mapped[str] = mapped_column(String)
    event_alignment: Mapped[str] = mapped_column(String)
    volume_confirmation: Mapped[str] = mapped_column(String)  # CONFIRMED/NOT_CONFIRMED/UNKNOWN
    technical_confirmation: Mapped[str] = mapped_column(String)  # CONFIRMED/PARTIAL/NOT_CONFIRMED/UNKNOWN
    technical_category: Mapped[str | None] = mapped_column(String)

    direction: Mapped[str] = mapped_column(String, index=True)  # LONG/SHORT/NO_TRADE
    no_trade_reason: Mapped[str | None] = mapped_column(String)
    signal_strength: Mapped[str] = mapped_column(String, index=True)  # STRONG/MODERATE/WEAK/INSUFFICIENT
    signal_strength_basis: Mapped[str] = mapped_column(String)  # always "HEURISTIC" — see class docstring
    confirming_dimensions: Mapped[int] = mapped_column(Integer)
    evaluable_dimensions: Mapped[int] = mapped_column(Integer)
    data_quality: Mapped[str] = mapped_column(String)  # HIGH/MEDIUM/LOW

    time_horizon: Mapped[str] = mapped_column(String)  # SWING/POSITION_CANDIDATE
    evidence_for_json: Mapped[str] = mapped_column(Text)
    evidence_against_json: Mapped[str] = mapped_column(Text)
    risk: Mapped[str | None] = mapped_column(Text)
    invalidation: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    predictive_status: Mapped[str] = mapped_column(String)  # always "EXPLORATORY" — see Phase 4/5 reports

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class SectorThemeState(Base):
    """Sector/Theme Emergence — Phase 6 (event_intelligence/). Append-only
    daily snapshot (mirrors V1's sector_rotation / V2's
    sector_intelligence_daily pattern) — one row per (as_of_date,
    sector_or_theme). `taxonomy` distinguishes the GICS-derived sectors
    (symbol_master.sector) from the two curated THEME_BASKET entries
    (Defence, PSU) — see event_intelligence/sector_universe.py for why
    these are a different universe than V1's own 12-sector SECTORS dict,
    which is untouched by this table.
    """

    __tablename__ = "sector_theme_state"
    __table_args__ = (UniqueConstraint("as_of_date", "sector_or_theme",
                                       name="uq_sector_theme_date_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    as_of_date: Mapped[dt.date] = mapped_column(Date, index=True)
    sector_or_theme: Mapped[str] = mapped_column(String, index=True)
    taxonomy: Mapped[str] = mapped_column(String)  # GICS_SECTOR / THEME_BASKET

    constituent_count: Mapped[int] = mapped_column(Integer)
    measurable_count: Mapped[int] = mapped_column(Integer)
    pct_above_20sma: Mapped[float | None] = mapped_column(Float)
    pct_positive_rs_1w: Mapped[float | None] = mapped_column(Float)
    pct_positive_rs_1m: Mapped[float | None] = mapped_column(Float)
    avg_rs_1w: Mapped[float | None] = mapped_column(Float)
    avg_rs_1m: Mapped[float | None] = mapped_column(Float)
    avg_rs_3m: Mapped[float | None] = mapped_column(Float)
    breadth_change: Mapped[float | None] = mapped_column(Float)   # vs. trend_lookback_sessions ago
    rs_change: Mapped[float | None] = mapped_column(Float)
    pct_volume_expansion: Mapped[float | None] = mapped_column(Float)

    positive_event_count: Mapped[int] = mapped_column(Integer)
    negative_event_count: Mapped[int] = mapped_column(Integer)

    raw_state: Mapped[str] = mapped_column(String)
    confirmed_state: Mapped[str] = mapped_column(String, index=True)
    days_in_state: Mapped[int] = mapped_column(Integer)
    direction_context: Mapped[str] = mapped_column(String)  # BULLISH/BEARISH/NEUTRAL

    leaders_json: Mapped[str] = mapped_column(Text)
    early_participants_json: Mapped[str] = mapped_column(Text)
    laggards_json: Mapped[str] = mapped_column(Text)
    non_participants_json: Mapped[str] = mapped_column(Text)
    evidence_for_json: Mapped[str] = mapped_column(Text)
    evidence_against_json: Mapped[str] = mapped_column(Text)

    data_quality: Mapped[str] = mapped_column(String)  # HIGH/MEDIUM/LOW
    state_basis: Mapped[str] = mapped_column(String)   # always "HEURISTIC"
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class SectorStockCrossReference(Base):
    """Sector/Theme <-> Stock evidence bridge — Phase 7 (event_intelligence/).

    One row per (as_of_date, sector_or_theme, symbol) — every symbol
    participating (in any role) in a sector/theme's LATEST confirmed state,
    combined with that symbol's own most recent company-event evidence
    (Phase 5's `event_trade_signal`), if any. Purely a cross-reference —
    does not recompute anything Phase 5/6 already computed (no duplicated
    RS, materiality, or reaction logic), and produces no numeric score or
    final ranking (`trade_context` is a categorical label, not a score).
    """

    __tablename__ = "sector_stock_cross_reference"
    __table_args__ = (UniqueConstraint("as_of_date", "sector_or_theme", "symbol",
                                       name="uq_crossref_date_sector_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    as_of_date: Mapped[dt.date] = mapped_column(Date, index=True)
    sector_or_theme: Mapped[str] = mapped_column(String, index=True)
    sector_stage: Mapped[str] = mapped_column(String)
    sector_direction: Mapped[str] = mapped_column(String)  # BULLISH/BEARISH/NEUTRAL
    symbol: Mapped[str] = mapped_column(String, index=True)
    participation_role: Mapped[str] = mapped_column(String)  # leader/early_participant/laggard/non_participant

    company_event_id: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str | None] = mapped_column(String)
    event_direction: Mapped[str | None] = mapped_column(String)
    materiality_tier: Mapped[str] = mapped_column(String)
    expectation_available: Mapped[bool] = mapped_column(Boolean)
    surprise_pct: Mapped[float | None] = mapped_column(Float)
    market_reaction_state: Mapped[str] = mapped_column(String)
    continuation_state: Mapped[str] = mapped_column(String)
    technical_confirmation: Mapped[str] = mapped_column(String)
    signal_direction: Mapped[str | None] = mapped_column(String)  # LONG/SHORT/NO_TRADE from Phase 5

    trade_context: Mapped[str] = mapped_column(String, index=True)
    sector_evidence_json: Mapped[str] = mapped_column(Text)
    stock_evidence_json: Mapped[str] = mapped_column(Text)
    evidence_for_json: Mapped[str] = mapped_column(Text)
    evidence_against_json: Mapped[str] = mapped_column(Text)
    conflicts_json: Mapped[str] = mapped_column(Text)
    data_quality: Mapped[str] = mapped_column(String)
    time_horizon: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class Opportunity(Base):
    """Opportunity Intelligence — Phase 8 (event_intelligence/). Final
    synthesis of Phase 5's per-event trade signal and, where available,
    Phase 7's sector/stock cross-reference for the same symbol. One row per
    (as_of_date, corporate_action_id) — the same event-level grain as
    `event_trade_signal`, since an opportunity is still anchored to one
    catalyst; sector confluence is additional evidence attached to it, not
    a new identity.

    NOT a 0-100 score — `tier` is categorical and `tier_basis` is always
    "HEURISTIC" (see event_intelligence/opportunity.py's module docstring
    for why a numeric score was explicitly rejected this phase).
    """

    __tablename__ = "opportunity"
    __table_args__ = (UniqueConstraint("as_of_date", "corporate_action_id",
                                       name="uq_opportunity_date_action"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    as_of_date: Mapped[dt.date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    corporate_action_id: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String, index=True)  # LONG/SHORT

    opportunity_type: Mapped[str] = mapped_column(String, index=True)  # EVENT_DRIVEN/CONFLUENCE/EMERGING_THEME
    tier: Mapped[str] = mapped_column(String, index=True)
    tier_basis: Mapped[str] = mapped_column(String)  # always "HEURISTIC"
    maturity: Mapped[str] = mapped_column(String)  # EARLY/MID_STAGE/MATURE/UNKNOWN
    time_horizon: Mapped[str] = mapped_column(String)  # SWING/POSITION_CANDIDATE/WATCH

    materiality_tier: Mapped[str] = mapped_column(String)
    market_reaction_state: Mapped[str] = mapped_column(String)
    continuation_state: Mapped[str] = mapped_column(String)
    technical_confirmation: Mapped[str] = mapped_column(String)

    sector_or_theme: Mapped[str | None] = mapped_column(String)
    sector_stage: Mapped[str | None] = mapped_column(String)
    participation_role: Mapped[str | None] = mapped_column(String)
    has_sector_data: Mapped[bool] = mapped_column(Boolean)

    evidence_for_json: Mapped[str] = mapped_column(Text)
    evidence_against_json: Mapped[str] = mapped_column(Text)
    conflicts_json: Mapped[str] = mapped_column(Text)
    risk: Mapped[str | None] = mapped_column(Text)
    invalidation: Mapped[str | None] = mapped_column(Text)
    data_quality: Mapped[str] = mapped_column(String)
    predictive_status: Mapped[str] = mapped_column(String)  # always "EXPLORATORY"
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
