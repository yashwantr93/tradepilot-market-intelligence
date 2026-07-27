"""
Phase 1 (Sector Intelligence) verification suite.

Covers every checkmark required at the end of Phase 1:
  - Snapshot saved
  - History retrieved
  - Trend calculated
  - Classification deterministic
  - V1 unchanged
  - Regression tests pass (Phase 0 + full app.py, including the new V2 page)

Run with:  python -m pytest intelligence_v2/tests/ -v
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from intelligence_v2.config.sectors import MIN_DWELL_DAYS, SECTOR_BASKETS
from intelligence_v2.database import sector_repository as repo
from intelligence_v2.database.engine import init_db
from intelligence_v2.database.v1_reference import read_v1
from intelligence_v2.processors.sector_classifier import apply_hysteresis, classify_raw
from intelligence_v2.processors.sector_metrics import compute_metrics, perf_over
from intelligence_v2.processors.sector_prices import build_basket_series, get_benchmark_series
from intelligence_v2.services.sector_intelligence import get_v1_sector_rotation_dates, run_backfill

V1_BASELINE_TABLES = [
    "daily_watchlist", "institutional_watchlist", "combined_watchlist",
    "signals", "symbol_master", "sector_rotation", "price_history",
]


@pytest.fixture(scope="module", autouse=True)
def backfilled():
    """Run once for this module: ensure the DB exists and a real backfill has
    executed (idempotent — safe even if it already ran)."""
    init_db()
    dates = get_v1_sector_rotation_dates()
    assert dates, "V1 sector_rotation has no history — cannot test Phase 1 against it"
    result = run_backfill(dates)
    return {"dates": dates, "result": result}


# ---------------------------------------------------------------------------
# Snapshot saved
# ---------------------------------------------------------------------------
def test_snapshot_saved(backfilled):
    assert backfilled["result"]["snapshots_written"] > 0
    overview = repo.get_latest_all_sectors()
    assert not overview.empty
    assert set(overview["sector"]) <= set(SECTOR_BASKETS.keys())


def test_snapshot_upsert_is_idempotent(backfilled):
    """Re-running the exact same backfill must not create duplicate rows."""
    before = len(repo.get_history("Banking"))
    run_backfill(backfilled["dates"])
    after = len(repo.get_history("Banking"))
    assert before == after, "Re-running the backfill duplicated rows instead of upserting"


# ---------------------------------------------------------------------------
# History retrieved
# ---------------------------------------------------------------------------
def test_history_retrieved(backfilled):
    hist = repo.get_history("Banking")
    assert not hist.empty
    assert list(hist["trade_date"]) == sorted(hist["trade_date"]), \
        "History must be returned in chronological (ascending) order"
    assert len(hist) == len(backfilled["dates"])


# ---------------------------------------------------------------------------
# Trend calculated
# ---------------------------------------------------------------------------
def test_perf_over_synthetic_series_is_arithmetically_correct():
    """Pure-function check against a hand-computable synthetic series —
    independent of any real data, so this can never be fooled by a data
    artifact (the exact class of issue found and fixed during this phase)."""
    dates = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(30)]
    series = pd.Series([100.0 + i for i in range(30)], index=dates)  # linear ramp
    result = perf_over(series, dates[25], 5)
    expected = (125.0 / 120.0 - 1) * 100
    # perf_over intentionally rounds to 4 dp for storage; tolerance matches that.
    assert result == pytest.approx(expected, abs=5e-5)


def test_perf_over_returns_none_without_enough_history():
    dates = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(10)]
    series = pd.Series(range(10), index=dates)
    assert perf_over(series, dates[3], 21) is None  # not enough history for a 1M window


def test_basket_series_index_is_sorted():
    """Regression guard for a real bug caught during Phase 1: pd.concat(axis=1)
    does not guarantee a sorted index when input series have differing date
    sets, which silently corrupted every position-based horizon lookup until
    an explicit sort_index() was added. This must never regress."""
    for sector in SECTOR_BASKETS:
        series, used, total = build_basket_series(sector)
        if series.empty:
            continue
        assert series.index.is_monotonic_increasing, (
            f"{sector}: basket series is not chronologically sorted"
        )
    nifty = get_benchmark_series()
    assert nifty.index.is_monotonic_increasing


def test_trend_calculated_against_independent_manual_calculation():
    """Cross-checks compute_metrics()'s 1M perf/RS against a manual, from-
    scratch recomputation for a real sector — proves the wiring (not just the
    pure perf_over function) is correct end-to-end."""
    series, _, _ = build_basket_series("Banking")
    nifty = get_benchmark_series()
    as_of = series.index[-1]

    pos = list(series.index).index(as_of)
    manual_perf_1m = (series.iloc[pos] / series.iloc[pos - 21] - 1) * 100

    metrics = compute_metrics(series, nifty, as_of)
    # compute_metrics intentionally rounds to 4 dp for storage; tolerance matches that.
    assert metrics["perf_1m"] == pytest.approx(manual_perf_1m, abs=5e-5)


# ---------------------------------------------------------------------------
# Classification deterministic
# ---------------------------------------------------------------------------
def test_classification_is_deterministic():
    metrics = {"rs_1w": 5.0, "rs_1m": 5.0, "rs_3m": 5.0, "rs_6m": 5.0, "rs_1y": 5.0,
              "above_20_sma": "Y", "above_50_sma": "Y", "above_200_sma": "Y",
              "rs_3m_40d_ago": 4.0, "rs_6m_40d_ago": 4.0, "rs_1m_slope": 1.0}
    r1 = classify_raw(metrics, consistency_pct=70.0)
    r2 = classify_raw(metrics, consistency_pct=70.0)
    assert r1 == r2 == "Strong Leader"


@pytest.mark.parametrize("metrics,consistency,expected", [
    ({"rs_1w": 5, "rs_1m": 5, "rs_3m": 5, "rs_6m": 5, "rs_1y": 5,
      "above_20_sma": "Y", "above_50_sma": "Y", "above_200_sma": "Y"}, 70.0, "Strong Leader"),
    ({"rs_1w": -5, "rs_1m": -5, "rs_3m": -5, "rs_6m": -5, "rs_1y": -5,
      "above_20_sma": "N", "above_50_sma": "N", "above_200_sma": "N"}, 0.0, "Downtrend"),
    ({"rs_1w": -1, "rs_1m": -1, "rs_3m": 1, "rs_6m": 5, "rs_1y": 1,
      "above_20_sma": "N", "above_50_sma": "N", "above_200_sma": "N",
      "rs_3m_40d_ago": 4.0}, 0.0, "Weakening"),
    ({"rs_1w": 1, "rs_1m": 1, "rs_3m": -5, "rs_6m": -5, "rs_1y": -5,
      "above_20_sma": "Y", "above_50_sma": "Y", "above_200_sma": "N"}, 0.0, "Recovery"),
    ({"rs_1w": 5, "rs_1m": 5, "rs_3m": 1, "rs_6m": 1, "rs_1y": 1,
      "above_20_sma": "Y", "above_50_sma": "Y", "above_200_sma": "N",
      "rs_3m_40d_ago": 0.5, "rs_6m_40d_ago": 0.5}, 0.0, "Early Momentum"),
    ({"rs_1w": 0, "rs_1m": 0, "rs_3m": 0, "rs_6m": 0, "rs_1y": 0,
      "above_20_sma": "Y", "above_50_sma": "N", "above_200_sma": "N",
      "rs_1m_slope": 1.0}, 0.0, "Improving"),
    ({"rs_1w": 0, "rs_1m": 0, "rs_3m": 0, "rs_6m": 0, "rs_1y": 0,
      "above_20_sma": "N", "above_50_sma": "N", "above_200_sma": "N"}, 0.0, "Sideways"),
])
def test_classify_raw_covers_all_seven_states(metrics, consistency, expected):
    assert classify_raw(metrics, consistency) == expected


def test_hysteresis_holds_a_flip_until_dwell_confirmed():
    # Candidate differs from confirmed state, but hasn't held long enough yet.
    state, days = apply_hysteresis("Downtrend", "Improving", 5, ["Improving", "Improving"])
    assert state == "Improving"  # not confirmed — must stay on prior state
    assert days == 6


def test_hysteresis_confirms_a_flip_after_dwell_period():
    recent = ["Downtrend"] * (MIN_DWELL_DAYS - 1)
    state, days = apply_hysteresis("Downtrend", "Improving", 6, recent)
    assert state == "Downtrend"
    assert days == 1


def test_hysteresis_first_ever_classification_has_no_prior():
    state, days = apply_hysteresis("Sideways", None, 0, [])
    assert state == "Sideways"
    assert days == 1


# ---------------------------------------------------------------------------
# V1 unchanged
# ---------------------------------------------------------------------------
def test_v1_row_counts_unchanged_after_phase1_backfill(backfilled):
    before = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
             for t in V1_BASELINE_TABLES}
    run_backfill(backfilled["dates"])  # exercise the full read path again
    after = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
            for t in V1_BASELINE_TABLES}
    assert before == after, f"V1 row counts changed! before={before} after={after}"


# ---------------------------------------------------------------------------
# Regression: Phase 0 health check + full app.py (V1 pages + new V2 page)
# ---------------------------------------------------------------------------
def test_phase0_health_check_still_passes():
    from intelligence_v2.services.health import run_health_check
    results = run_health_check()
    failed = [k for k, v in results.items() if k != "_overall" and not v["ok"]]
    assert not failed, f"Phase 0 health check regressed: {failed}"


def test_full_app_renders_including_new_v2_page():
    """Iterates every page via the SIDEBAR-scoped radio specifically
    (at.sidebar.radio[0], not at.radio[0]) — once a page with its own
    internal radio (e.g. Validation Dashboard) has rendered, a positional,
    unscoped at.radio[0] can resolve to that page's widget instead of the
    navigation control. Scoping to the sidebar avoids that ambiguity."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=60).run()
    assert not at.exception, [e.message for e in at.exception]

    v2_label = "🔥 Sector Intelligence (V2)"
    assert v2_label in at.sidebar.radio[0].options, "New V2 page missing from app.py's PAGES nav"

    ok = True
    for label in at.sidebar.radio[0].options:
        at.sidebar.radio[0].set_value(label).run()
        if at.exception:
            ok = False
            print(f"Exception on page {label!r}: {[e.message for e in at.exception]}")
    assert ok, "One or more pages (V1 or the new V2 page) raised an exception"
