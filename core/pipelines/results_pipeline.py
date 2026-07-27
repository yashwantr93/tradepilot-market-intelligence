"""
Results ingestion.

Flow per symbol: EXTRACT (yfinance quarterly income statement) → COMPUTE
(YoY revenue/profit growth + margin change) → CLASSIFY (Strong/Neutral/Weak) →
STORE. No scoring, no ML.
"""

from __future__ import annotations

from core.config import results_universe
from core.connectors.results_connector import ResultsConnector
from core.db import repository as repo
from core.processing.results_classifier import classify, compute_metrics
from core.utils.logging import get_logger

log = get_logger(__name__)


def run_results_ingestion() -> tuple[int, dict]:
    """Ingest + classify quarterly results across the universe.

    Returns (stored, counts) where counts has processed/with_data/stored.
    """
    job_id = repo.start_job("results_ingestion", source="yfinance")
    try:
        conn = ResultsConnector()
        universe = results_universe()
        rows, with_data = [], 0
        for i, sym in enumerate(universe, 1):
            stmt = conn.fetch("quarterly_income", symbol=sym)
            metrics = compute_metrics(stmt)
            if metrics is None:
                continue
            with_data += 1
            cls = classify(metrics["revenue_growth_pct"], metrics["profit_growth_pct"])
            rows.append({
                "symbol": sym, "company_name": sym, "quarter": metrics["quarter"],
                "period_end": metrics["period_end"],
                "revenue_growth_pct": metrics["revenue_growth_pct"],
                "profit_growth_pct": metrics["profit_growth_pct"],
                "margin_change_pct": metrics["margin_change_pct"],
                "result_classification": cls, "basis": metrics["basis"],
                "source": "yfinance",
            })
            if i % 15 == 0:
                log.info("Results: processed %d/%d", i, len(universe))

        stored = repo.upsert_results(rows)
        repo.finish_job(job_id, "ok", rows_in=len(universe), rows_out=stored)
        log.info("Results: %d in universe, %d with data, %d stored",
                 len(universe), with_data, stored)
        return stored, {"processed": len(universe), "with_data": with_data, "stored": stored}
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("Results ingestion failed")
        raise
