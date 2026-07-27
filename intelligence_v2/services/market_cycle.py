"""
Market Cycle orchestration service.

Provides the four services required by Phase 2:
  - Cycle calculation        -> run_cycle_backfill() / calculate_cycle_for_date()
  - State transition          -> handled inside _cycle_one_sector() (hysteresis + logging)
  - Transition history         -> get_transition_history()
  - Current market cycle       -> get_current_market_cycle()

Reads ONLY market_v2.db's `sector_intelligence_daily` (Phase 1 output).
Writes ONLY market_v2.db's cycle tables. V1 is never touched by this module.
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
from sqlalchemy import select

from intelligence_v2.config.market_cycle import (
    CYCLE_STAGES,
    MIN_CYCLE_CONFIRMATIONS,
    MIN_CYCLE_DWELL_DAYS,
)
from intelligence_v2.database import cycle_repository as crepo
from intelligence_v2.database.engine import session_scope
from intelligence_v2.models import SectorIntelligenceDaily
from intelligence_v2.processors.cycle_classifier import (
    apply_cycle_hysteresis,
    build_confidence_notes,
    classify_cycle_stage,
)
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("services.market_cycle")


def get_sector_intelligence_dates() -> list[dt.date]:
    """Dates available in Phase 1's output — the cycle engine's only input."""
    with session_scope() as s:
        return list(s.scalars(
            select(SectorIntelligenceDaily.trade_date).distinct()
            .order_by(SectorIntelligenceDaily.trade_date)
        ).all())


def _load_sector_intelligence(trade_date: dt.date) -> list[dict]:
    with session_scope() as s:
        rows = s.scalars(
            select(SectorIntelligenceDaily)
            .where(SectorIntelligenceDaily.trade_date == trade_date)
            .order_by(SectorIntelligenceDaily.sector)
        ).all()
        return [
            {"sector": r.sector, "trade_date": r.trade_date,
             "rs_1w": r.rs_1w, "rs_1m": r.rs_1m, "rs_3m": r.rs_3m,
             "rs_6m": r.rs_6m, "rs_1y": r.rs_1y,
             "perf_1w": r.perf_1w, "perf_1m": r.perf_1m, "perf_3m": r.perf_3m,
             "perf_6m": r.perf_6m, "perf_1y": r.perf_1y,
             "momentum_1m": r.momentum_1m,
             "above_20_sma": r.above_20_sma, "above_50_sma": r.above_50_sma,
             "above_200_sma": r.above_200_sma,
             "consistency_pct": r.consistency_pct, "data_method": r.data_method}
            for r in rows
        ]


def _cycle_one_sector(metrics: dict, as_of: dt.date, history_days: int) -> dict:
    sector = metrics["sector"]

    classification = classify_cycle_stage(metrics)
    raw_stage = classification["stage"]

    prior = crepo.get_prior_cycle_row(sector, before_date=as_of)
    prior_stage = prior["stage"] if prior else None
    prior_days = prior["days_in_stage"] if prior else 0
    prior_start = prior["stage_start_date"] if prior else None
    recent_raw = crepo.get_recent_raw_stages(sector, MIN_CYCLE_DWELL_DAYS - 1, before_date=as_of)

    stage, days_in_stage, transitioned = apply_cycle_hysteresis(
        raw_stage, prior_stage, prior_days, recent_raw)

    if prior_stage is None or transitioned:
        stage_start_date = as_of
    else:
        stage_start_date = prior_start or as_of

    confidence_notes = build_confidence_notes(
        metrics, history_days, classification["matched_by_fallback"], metrics.get("data_method"))

    # If hysteresis held the stage back, the stored reasons must describe the
    # CONFIRMED stage, not the unconfirmed candidate — otherwise the dashboard
    # would show a reason that contradicts the displayed stage.
    if stage == raw_stage:
        reasons = classification["reasons"]
        behaviour = classification["possible_behaviour"]
        rule_order = classification["rule_order"]
        fallback_flag = classification["matched_by_fallback"]
    else:
        reasons = [
            f"Holding at '{stage}' — today's readings suggest '{raw_stage}', but a "
            f"stage change requires that stage in {MIN_CYCLE_CONFIRMATIONS} of the "
            f"last {MIN_CYCLE_DWELL_DAYS} readings (hysteresis).",
        ] + [f"(Candidate evidence) {r}" for r in classification["reasons"]]
        behaviour = f"Stage under review — possible move toward '{raw_stage}' if the reading persists."
        rule_order = None
        fallback_flag = "N"
        confidence_notes.append(
            f"Pending stage change: raw reading is '{raw_stage}' but not yet confirmed.")

    row = {
        "trade_date": as_of, "sector": sector,
        "raw_stage": raw_stage, "stage": stage,
        "prior_stage": prior_stage, "days_in_stage": days_in_stage,
        "stage_start_date": stage_start_date,
        "reasons": json.dumps(reasons),
        "possible_behaviour": behaviour,
        "confidence_notes": json.dumps(confidence_notes),
        "rule_order": rule_order, "matched_by_fallback": fallback_flag,
    }

    if transitioned:
        crepo.record_transition({
            "sector": sector, "transition_date": as_of,
            "from_stage": prior_stage, "to_stage": stage,
            "days_in_previous_stage": prior_days,
            "reasons": json.dumps(classification["reasons"]),
        })
        log.info("%s: %s -> %s on %s (after %d days)", sector, prior_stage, stage,
                 as_of, prior_days)

    return row


def run_cycle_backfill(dates: list[dt.date] | None = None) -> dict:
    """Compute + store cycle stages for each date in chronological order, so
    hysteresis and transition history accumulate correctly with no look-ahead."""
    if dates is None:
        dates = get_sector_intelligence_dates()
    dates = sorted(dates)
    if not dates:
        log.warning("No sector-intelligence dates available — run Phase 1 first.")
        return {"dates": 0, "rows_written": 0, "transitions": 0}

    rows_written = 0
    for idx, as_of in enumerate(dates):
        history_days = idx  # stored sessions available BEFORE this date
        for metrics in _load_sector_intelligence(as_of):
            row = _cycle_one_sector(metrics, as_of, history_days)
            crepo.upsert_cycle(row)
            rows_written += 1

    transitions = len(crepo.get_transitions())
    log.info("Cycle backfill complete: %d dates, %d rows, %d transitions logged",
             len(dates), rows_written, transitions)
    return {"dates": len(dates), "rows_written": rows_written, "transitions": transitions}


def calculate_cycle_for_date(as_of: dt.date) -> int:
    return run_cycle_backfill([as_of])["rows_written"]


# ---------------------------------------------------------------------------
# Retrieval services
# ---------------------------------------------------------------------------
def get_current_market_cycle() -> pd.DataFrame:
    return crepo.get_latest_all_sectors()


def get_sector_cycle_history(sector: str) -> pd.DataFrame:
    return crepo.get_cycle_history(sector)


def get_transition_history(sector: str | None = None, limit: int | None = None) -> pd.DataFrame:
    return crepo.get_transitions(sector=sector, limit=limit)


def get_stage_distribution() -> pd.DataFrame:
    df = get_current_market_cycle()
    if df.empty:
        return pd.DataFrame(columns=["stage", "count"])
    counts = df["stage"].value_counts().reindex(CYCLE_STAGES).fillna(0).astype(int)
    return counts.rename_axis("stage").reset_index(name="count")
