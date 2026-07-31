"""
Position Opportunity orchestration service.

Provides the six services required by Phase 5:
  - Calculation            -> run_position_backfill() / calculate_for_date()
  - Classification          -> delegates to processors.position_classifier (pure)
  - Ranking                  -> _rank_within_categories() (within-category only)
  - History retrieval        -> get_symbol_history() / get_category_history()
  - Reason generation        -> delegates to processors.position_classifier (pure)
  - Backfill                 -> run_position_backfill()

Data sources (all pre-existing): V1 price_history / symbol_master /
daily_watchlist via the read-only bridge, plus Phase 1 + Phase 2 + Phase 3
output from market_v2.db. No new connector.

Deliberate reuse: stock-level metrics (relative strength, moving averages,
price momentum, volume) are NOT recomputed here — this service calls the same
`momentum_metrics.compute_stock_metrics()` / `load_universe_series()` Phase 3
and Phase 4 already use (itself built on the shared Relative Strength Engine).
Only classification (position_classifier) is new; the underlying measurement
machinery, and the sector/cycle/early-momentum context it joins against, are
all reused unmodified from prior phases.
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
from sqlalchemy import select

from intelligence_v2.config.early_momentum import MIN_HISTORY_DAYS
from intelligence_v2.config.position_opportunity import (
    CATEGORIES,
    CYCLE_RANK_ORDER,
    V1_READY_LOOKBACK_DAYS,
)
from intelligence_v2.config.sectors import SECTOR_BASKETS
from intelligence_v2.database import position_repository as repo
from intelligence_v2.database.engine import session_scope
from intelligence_v2.database.v1_reference import read_v1
from intelligence_v2.models import EarlyMomentumDaily, MarketCycleDaily, SectorIntelligenceDaily
from intelligence_v2.processors.momentum_metrics import compute_stock_metrics, load_universe_series
from intelligence_v2.processors.position_classifier import (
    assign_category,
    build_reasons,
    evaluate_signals,
    signal_count,
)
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("services.position_opportunity")


def _symbol_to_sector() -> dict[str, str]:
    """Map each basket member to its V2 sector.

    Three symbols (ONGC, NTPC, POWERGRID) belong to two baskets; the tie-break
    is alphabetical so the mapping is deterministic and reproducible. Same
    self-contained mapping logic Phase 3/4 each carry — not RS-computation
    infrastructure, so it stays outside the shared engine's scope.
    """
    mapping: dict[str, list[str]] = {}
    for sector, symbols in SECTOR_BASKETS.items():
        for sym in symbols:
            mapping.setdefault(sym, []).append(sector)
    return {sym: sorted(sectors)[0] for sym, sectors in mapping.items()}


def _load_sector_context(trade_date: dt.date) -> tuple[dict[str, str], dict[str, str], dict[str, float]]:
    """(sector -> Phase 1 state, sector -> Phase 2 cycle stage, sector -> Phase 1 rs_1m)
    for one date."""
    with session_scope() as s:
        rows = s.scalars(
            select(SectorIntelligenceDaily)
            .where(SectorIntelligenceDaily.trade_date == trade_date)).all()
        states = {r.sector: r.state for r in rows}
        sector_rs_1m = {r.sector: r.rs_1m for r in rows}
        stages = {
            r.sector: r.stage for r in s.scalars(
                select(MarketCycleDaily)
                .where(MarketCycleDaily.trade_date == trade_date)).all()
        }
    return states, stages, sector_rs_1m


def _load_early_momentum_categories(trade_date: dt.date) -> dict[str, str]:
    """symbol -> Phase 3 Early Momentum category for one date — the "Phase 3
    Early Momentum" data source the Phase 5 brief requires."""
    with session_scope() as s:
        rows = s.scalars(
            select(EarlyMomentumDaily)
            .where(EarlyMomentumDaily.trade_date == trade_date)).all()
    return {r.symbol: r.category for r in rows}


def _load_v1_ready_symbols(as_of: dt.date) -> set[str]:
    """Symbols flagged by V1's existing technical_status="Ready" rule
    (`core/processing/technicals.py`: uptrend & leadership — above 20-SMA, RS
    not Weak, near 52w high or confirming volume) within the lookback window —
    read-only reuse of an existing V1 signal, the "Existing V1 Opportunity
    Status" data source the Phase 5 brief requires."""
    since = as_of - dt.timedelta(days=V1_READY_LOOKBACK_DAYS)
    df = read_v1(
        "SELECT DISTINCT symbol FROM daily_watchlist "
        "WHERE trade_date <= :as_of AND trade_date >= :since AND technical_status = 'Ready'",
        {"as_of": as_of.isoformat(), "since": since.isoformat()})
    return set(df["symbol"]) if not df.empty else set()


def _rank_within_categories(rows: list[dict]) -> list[dict]:
    """Deterministic ranking applied SEPARATELY inside each category.

    Sort keys (per the Phase 5 brief's suggested priority): rs_3m descending,
    sector_rs_1m descending, cycle_rank ascending (via the documented,
    display-only CYCLE_RANK_ORDER — never used by the classifier itself),
    perf_3m descending, symbol ascending. There is deliberately no
    market-wide ranking — ranks are only comparable within one category.
    """
    ranked: list[dict] = []
    for category in CATEGORIES:
        cohort = [r for r in rows if r["category"] == category]
        cohort.sort(key=lambda r: (
            -(r["rs_3m"] if r["rs_3m"] is not None else -9e9),
            -(r["sector_rs_1m"] if r["sector_rs_1m"] is not None else -9e9),
            CYCLE_RANK_ORDER.get(r["cycle_stage"], len(CYCLE_RANK_ORDER)),
            -(r["perf_3m"] if r["perf_3m"] is not None else -9e9),
            r["symbol"]))
        for i, row in enumerate(cohort, start=1):
            row["rank_in_category"] = i
            ranked.append(row)
    return ranked


def calculate_for_date(as_of: dt.date, series: dict, nifty_closes: pd.Series,
                       sym_sector: dict[str, str]) -> list[dict]:
    """Classify every universe symbol for one date. Returns ranked rows."""
    sector_states, cycle_stages, sector_rs_1m = _load_sector_context(as_of)
    early_momentum_categories = _load_early_momentum_categories(as_of)
    v1_ready = _load_v1_ready_symbols(as_of)

    rows: list[dict] = []
    for symbol, frame in series.items():
        if len(frame) < MIN_HISTORY_DAYS:
            continue
        metrics = compute_stock_metrics(frame["close"], frame["volume"], nifty_closes, as_of)
        if metrics is None:
            continue

        sector = sym_sector.get(symbol)
        sector_state = sector_states.get(sector) if sector else None
        cycle_stage = cycle_stages.get(sector) if sector else None
        sector_rs = sector_rs_1m.get(sector) if sector else None
        em_category = early_momentum_categories.get(symbol)

        signals = evaluate_signals(metrics, sector_state, cycle_stage,
                                   em_category, symbol in v1_ready)
        category, category_reason = assign_category(signals)
        satisfied, missing = build_reasons(signals)

        rows.append({
            "trade_date": as_of, "symbol": symbol,
            "category": category, "rank_in_category": 0,
            "signal_count": signal_count(signals),
            "sector": sector, "sector_state": sector_state, "cycle_stage": cycle_stage,
            "early_momentum_category": em_category,
            "close": metrics["close"],
            "perf_1w": metrics["perf_1w"], "perf_1m": metrics["perf_1m"],
            "perf_3m": metrics["perf_3m"],
            "rs_1w": metrics["rs_1w"], "rs_1m": metrics["rs_1m"], "rs_3m": metrics["rs_3m"],
            "rs_slope": metrics["rs_slope"],
            "above_20_sma": metrics["above_20_sma"], "above_50_sma": metrics["above_50_sma"],
            "above_200_sma": metrics["above_200_sma"],
            "volume_ratio": metrics["volume_ratio"],
            "dist_52w_high_pct": metrics["dist_52w_high_pct"],
            "sector_rs_1m": sector_rs,
            "signals": json.dumps(signals),
            "reasons": json.dumps(satisfied),
            "missing": json.dumps(missing),
            "category_reason": category_reason,
        })

    return _rank_within_categories(rows)


def get_available_dates() -> list[dt.date]:
    """Dates where Phase 1, Phase 2 AND Phase 3 context all exist — Phase 3's
    dates are the binding constraint since it itself requires Phase 1 + 2."""
    with session_scope() as s:
        return list(s.scalars(
            select(EarlyMomentumDaily.trade_date).distinct()
            .order_by(EarlyMomentumDaily.trade_date)).all())


def run_position_backfill(dates: list[dt.date] | None = None) -> dict:
    """Classify the universe for each date. Loads price series ONCE and reuses
    it across all dates (the expensive part is the V1 read, not the maths)."""
    if dates is None:
        dates = get_available_dates()
    dates = sorted(dates)
    if not dates:
        log.warning("No Phase 1/2/3 context dates available — run those phases first.")
        return {"dates": 0, "rows_written": 0, "universe": 0}

    series, nifty_closes = load_universe_series()
    if not series or nifty_closes.empty:
        raise RuntimeError("V1 price_history is missing symbols or the NIFTY 50 benchmark.")

    sym_sector = _symbol_to_sector()
    total = 0
    for as_of in dates:
        rows = calculate_for_date(as_of, series, nifty_closes, sym_sector)
        total += repo.replace_for_date(as_of, rows)

    log.info("Position Opportunity backfill: %d dates, %d rows, universe %d symbols",
             len(dates), total, len(series))
    return {"dates": len(dates), "rows_written": total, "universe": len(series)}


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
def get_latest(category: str | None = None) -> pd.DataFrame:
    return repo.get_latest(category=category)


def get_symbol_history(symbol: str) -> pd.DataFrame:
    return repo.get_symbol_history(symbol)


def get_category_history() -> pd.DataFrame:
    return repo.get_category_counts_by_date()


def get_category_counts() -> dict[str, int]:
    df = repo.get_latest()
    if df.empty:
        return {c: 0 for c in CATEGORIES}
    counts = df["category"].value_counts().to_dict()
    return {c: int(counts.get(c, 0)) for c in CATEGORIES}
