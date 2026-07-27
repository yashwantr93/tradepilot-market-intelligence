"""
Sector Intelligence orchestration service.

Provides the four services required by Phase 1:
  - Snapshot creation   -> create_snapshot_for_date() / run_backfill()
  - Historical lookup   -> get_history()
  - Trend calculation   -> (delegates to processors.sector_metrics, pure)
  - Classification      -> (delegates to processors.sector_classifier, pure)

This is the only module that reads V1 (via processors.sector_prices, which
uses the read-only bridge) and writes V2 (via database.sector_repository).
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from intelligence_v2.config.sectors import CONSISTENCY_LOOKBACK_DAYS, MIN_DWELL_DAYS, SECTOR_BASKETS
from intelligence_v2.database import sector_repository as repo
from intelligence_v2.database.v1_reference import read_v1
from intelligence_v2.processors.sector_classifier import apply_hysteresis, classify_raw
from intelligence_v2.processors.sector_metrics import compute_metrics
from intelligence_v2.processors.sector_prices import build_basket_series, get_benchmark_series
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("services.sector_intelligence")


def get_v1_sector_rotation_dates() -> list[dt.date]:
    """The trade_dates V1's own sector_rotation table already has — this IS
    "use existing V1 sector data as the primary source" for deciding which
    historical dates to backfill."""
    df = read_v1("SELECT DISTINCT trade_date FROM sector_rotation ORDER BY trade_date")
    if df.empty:
        return []
    return sorted(pd.to_datetime(df["trade_date"]).dt.date.tolist())


def _snapshot_one_sector(sector: str, sector_series: pd.Series, nifty_series: pd.Series,
                         as_of: dt.date, members_used: int, members_total: int) -> dict | None:
    if sector_series.empty:
        log.warning("Sector %s: no usable price series — skipping %s", sector, as_of)
        return None

    metrics = compute_metrics(sector_series, nifty_series, as_of)
    if metrics["close"] is None:
        # as_of predates this sector's available history entirely.
        return None

    matches, total = repo.count_recent_state(
        sector, "Strong Leader", CONSISTENCY_LOOKBACK_DAYS, before_date=as_of)
    consistency_pct = round(matches / total * 100, 2) if total > 0 else None

    raw_state = classify_raw(metrics, consistency_pct)

    recent = repo.get_last_n_rows(sector, MIN_DWELL_DAYS, before_date=as_of)
    prior = recent[0] if recent else None
    prior_state = prior["state"] if prior else None
    prior_days = prior["days_in_state"] if prior else 0
    recent_raw_states = [r["raw_state"] for r in recent[1:MIN_DWELL_DAYS]]

    state, days_in_state = apply_hysteresis(raw_state, prior_state, prior_days, recent_raw_states)

    method = f"basket_from_v1_price_history ({members_used}/{members_total} members)"

    row = {"trade_date": as_of, "sector": sector, "consistency_pct": consistency_pct,
          "raw_state": raw_state, "state": state, "days_in_state": days_in_state,
          "data_method": method}
    row.update({k: v for k, v in metrics.items()
               if k in ("close", "perf_1w", "perf_1m", "perf_3m", "perf_6m", "perf_1y",
                        "nifty_perf_1w", "nifty_perf_1m", "nifty_perf_3m", "nifty_perf_6m",
                        "nifty_perf_1y", "rs_1w", "rs_1m", "rs_3m", "rs_6m", "rs_1y",
                        "momentum_1m", "above_20_sma", "above_50_sma", "above_200_sma")})
    return row


def run_backfill(dates: list[dt.date] | None = None) -> dict:
    """Build every sector's full series ONCE, then evaluate + store a snapshot
    for each date in chronological order (oldest first) so hysteresis and
    consistency_pct accumulate correctly with no look-ahead.
    """
    if dates is None:
        dates = get_v1_sector_rotation_dates()
    dates = sorted(dates)
    if not dates:
        log.warning("No dates to backfill (V1 sector_rotation has no history yet)")
        return {"dates": 0, "snapshots_written": 0, "sectors_skipped": []}

    nifty_series = get_benchmark_series()
    if nifty_series.empty:
        raise RuntimeError("Benchmark (NIFTY 50) series is empty in V1's price_history — "
                          "cannot compute relative strength.")

    sector_series_cache: dict[str, tuple[pd.Series, int, int]] = {}
    for sector in SECTOR_BASKETS:
        sector_series_cache[sector] = build_basket_series(sector)

    written = 0
    skipped_sectors = set()
    for as_of in dates:
        for sector, (series, used, total) in sector_series_cache.items():
            row = _snapshot_one_sector(sector, series, nifty_series, as_of, used, total)
            if row is None:
                skipped_sectors.add(sector)
                continue
            repo.upsert_snapshot(row)
            written += 1

    log.info("Backfill complete: %d dates, %d snapshots written, sectors with any "
             "skip: %s", len(dates), written, sorted(skipped_sectors))
    return {"dates": len(dates), "snapshots_written": written,
           "sectors_skipped": sorted(skipped_sectors)}


def create_snapshot_for_date(as_of: dt.date) -> int:
    """Convenience wrapper for a single date (e.g. a future daily run)."""
    result = run_backfill([as_of])
    return result["snapshots_written"]


def get_overview() -> pd.DataFrame:
    return repo.get_latest_all_sectors()


def get_history(sector: str) -> pd.DataFrame:
    return repo.get_history(sector)
