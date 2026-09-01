"""
Results ingestion.

Flow per symbol: EXTRACT (yfinance quarterly income statement) → COMPUTE
(YoY revenue/profit growth + margin change) → CLASSIFY (Strong/Neutral/Weak) →
STORE. No scoring, no ML.

Phase 1 — Event Intelligence Foundation additions (purely additive, the
original `results_tracker` write path below is UNCHANGED so existing
consumers — Results Watchlist, opportunity_hub — see zero behavior change):

  1. Every quarter yfinance returns (not just the latest) has its RAW
     revenue/profit/margin stored to `results_quarterly` — previously
     fetched and silently discarded.
  2. Once the (unchanged) latest-quarter growth is computed and stored to
     `results_tracker`, an internal trailing-average EXPECTATION is derived
     from that symbol's own prior stored YoY prints, a SURPRISE is computed
     against it, and a MATERIALITY tier is derived from the surprise — all
     three stored to `event_expectations`, never blended into a single
     bullish/bearish field.
"""

from __future__ import annotations

from core.config import OFFLINE_MODE, results_universe
from core.connectors.results_connector import ResultsConnector
from core.db import repository as repo
from core.processing.expectation import compute_expectation, compute_surprise
from core.processing.materiality import compute_results_materiality
from core.processing.results_classifier import classify, compute_all_metrics, compute_metrics
from core.utils.logging import get_logger

log = get_logger(__name__)

_METRICS = ("revenue_growth_pct", "profit_growth_pct")

# Phase 2.5 — Data Integrity fix. Every row previously stored "yfinance"
# regardless of whether OFFLINE_MODE was on, so an offline/seed run and a
# real live run were byte-for-byte indistinguishable in storage — exactly
# how 57 synthetic rows went undetected in results_tracker for months (see
# the Phase 2.5 report's ROOT CAUSE section). Going forward every row is
# tagged with which one actually produced it.
_SOURCE_TAG = "yfinance_offline_seed" if OFFLINE_MODE else "yfinance_live"


def _expectation_rows(symbol: str, period_end, latest_row: dict) -> list[dict]:
    """Build the event_expectations rows for one symbol's latest quarter."""
    rows = []
    for metric in _METRICS:
        actual = latest_row.get(metric)
        history = repo.get_results_history(symbol, before=period_end, basis="YoY")
        prior_values = [h[metric] for h in history if h.get(metric) is not None]
        exp = compute_expectation(prior_values)
        surprise = compute_surprise(actual, exp["expectation_pct"])
        materiality = compute_results_materiality(surprise)
        rows.append({
            "event_source_type": "results", "symbol": symbol, "period_end": period_end,
            "metric": metric, "actual_pct": actual,
            "expectation_pct": exp["expectation_pct"],
            "expectation_source": exp["expectation_source"],
            "expectation_confidence": exp["expectation_confidence"],
            "expectation_samples": exp["expectation_samples"],
            "surprise_pct": surprise,
            "materiality_tier": materiality["materiality_tier"],
            "materiality_reason": materiality["materiality_reason"],
        })
    return rows


def run_results_ingestion() -> tuple[int, dict]:
    """Ingest + classify quarterly results across the universe.

    Returns (stored, counts) where counts has processed/with_data/stored.
    """
    job_id = repo.start_job("results_ingestion", source="yfinance")
    try:
        conn = ResultsConnector()
        universe = results_universe()
        rows, with_data = [], 0
        quarterly_rows: list[dict] = []
        expectation_rows: list[dict] = []

        for i, sym in enumerate(universe, 1):
            stmt = conn.fetch("quarterly_income", symbol=sym)

            # --- unchanged existing behavior: latest-quarter growth only ---
            metrics = compute_metrics(stmt)
            if metrics is None:
                continue
            with_data += 1
            cls = classify(metrics["revenue_growth_pct"], metrics["profit_growth_pct"])
            latest_row = {
                "symbol": sym, "company_name": sym, "quarter": metrics["quarter"],
                "period_end": metrics["period_end"],
                "revenue_growth_pct": metrics["revenue_growth_pct"],
                "profit_growth_pct": metrics["profit_growth_pct"],
                "margin_change_pct": metrics["margin_change_pct"],
                "result_classification": cls, "basis": metrics["basis"],
                "source": _SOURCE_TAG,
            }
            rows.append(latest_row)

            # --- Phase 1 additions (additive only) ---
            for q in compute_all_metrics(stmt):
                quarterly_rows.append({
                    "symbol": sym, "period_end": q["period_end"],
                    "revenue_actual": q["revenue_actual"], "profit_actual": q["profit_actual"],
                    "margin_pct": q["margin_pct"], "source": _SOURCE_TAG,
                })
            if metrics["basis"] == "YoY":
                # Expectation/Surprise is only meaningful against a genuine
                # YoY actual — a QoQ fallback figure isn't comparable to a
                # trailing YoY-print average (see expectation.py).
                expectation_rows.extend(
                    _expectation_rows(sym, metrics["period_end"], latest_row)
                )

            if i % 15 == 0:
                log.info("Results: processed %d/%d", i, len(universe))

        stored = repo.upsert_results(rows)
        repo.upsert_results_quarterly(quarterly_rows)
        repo.upsert_event_expectations(expectation_rows)
        repo.finish_job(job_id, "ok", rows_in=len(universe), rows_out=stored)
        log.info("Results: %d in universe, %d with data, %d stored "
                 "(%d raw quarters, %d expectation rows)",
                 len(universe), with_data, stored, len(quarterly_rows), len(expectation_rows))
        return stored, {"processed": len(universe), "with_data": with_data, "stored": stored}
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("Results ingestion failed")
        raise
