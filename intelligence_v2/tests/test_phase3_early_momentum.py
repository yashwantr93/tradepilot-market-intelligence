"""
Phase 3 (Early Momentum Engine) verification suite.

Covers every checkmark required at the end of Phase 3:
  - Category assignment
  - Deterministic outputs
  - Ranking reproducibility
  - History retrieval
  - Explainability generation
  - V1 unchanged
  - Regression tests

Run with:  python -m pytest intelligence_v2/tests/ -v
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from intelligence_v2.config.early_momentum import CATEGORIES, SIGNAL_LABELS
from intelligence_v2.database import momentum_repository as repo
from intelligence_v2.database.engine import init_db
from intelligence_v2.database.v1_reference import read_v1
from intelligence_v2.processors.momentum_classifier import (
    assign_category,
    build_reasons,
    evaluate_signals,
    signal_count,
)
from intelligence_v2.processors.momentum_metrics import (
    compute_stock_metrics,
    load_universe_series,
    sanitize_closes,
)
from intelligence_v2.services.early_momentum import (
    get_available_dates,
    get_category_counts,
    get_latest,
    get_symbol_history,
    run_momentum_backfill,
)

V1_BASELINE_TABLES = [
    "daily_watchlist", "institutional_watchlist", "combined_watchlist",
    "signals", "symbol_master", "sector_rotation", "price_history",
]

ALL_ON = {k: True for k in SIGNAL_LABELS}
ALL_OFF = {k: False for k in SIGNAL_LABELS}


@pytest.fixture(scope="module", autouse=True)
def backfilled():
    init_db()
    dates = get_available_dates()
    assert dates, "Phase 1/2 context missing — run those phases first"
    result = run_momentum_backfill(dates)
    return {"dates": dates, "result": result}


# ---------------------------------------------------------------------------
# Category assignment
# ---------------------------------------------------------------------------
def test_backfill_wrote_rows(backfilled):
    assert backfilled["result"]["rows_written"] > 0
    assert backfilled["result"]["universe"] > 0
    assert not get_latest().empty


def test_every_stock_has_exactly_one_valid_category(backfilled):
    df = get_latest()
    assert df["symbol"].is_unique, "A symbol appeared more than once on the same date"
    assert set(df["category"]) <= set(CATEGORIES)
    assert df["category"].notna().all()


def test_category_counts_sum_to_universe(backfilled):
    df = get_latest()
    counts = get_category_counts()
    assert sum(counts.values()) == len(df), \
        "Category counts do not account for every scanned stock"


def test_emerging_leader_requires_full_evidence():
    category, _ = assign_category(ALL_ON)
    assert category == "Emerging Leader"


def test_emerging_leader_denied_without_backdrop():
    """Sector strength OR cycle confirmation is mandatory for Emerging Leader."""
    signals = dict(ALL_ON, sector_strength=False, cycle_confirmation=False)
    category, _ = assign_category(signals)
    assert category != "Emerging Leader"
    assert category == "Building Momentum"


def test_building_momentum_rule():
    signals = dict(ALL_OFF, rs_improving=True, above_20_sma=True, rs_positive=True)
    assert assign_category(signals)[0] == "Building Momentum"


def test_watch_closely_on_single_early_sign():
    signals = dict(ALL_OFF, rs_improving=True)
    assert assign_category(signals)[0] == "Watch Closely"
    signals2 = dict(ALL_OFF, above_20_sma=True, price_momentum=True)
    assert assign_category(signals2)[0] == "Watch Closely"


def test_not_qualified_is_the_catch_all():
    assert assign_category(ALL_OFF)[0] == "Not Qualified"


def test_categories_are_mutually_exclusive():
    """Exhaustively check every one of the 2^9 signal combinations yields
    exactly one valid category — proves no stock can ever land in two."""
    import itertools

    keys = list(SIGNAL_LABELS)
    for combo in itertools.product([False, True], repeat=len(keys)):
        signals = dict(zip(keys, combo))
        category, reason = assign_category(signals)
        assert category in CATEGORIES
        assert reason


# ---------------------------------------------------------------------------
# Deterministic outputs
# ---------------------------------------------------------------------------
def test_signal_evaluation_is_deterministic():
    metrics = {"rs_1m": 5.0, "rs_slope": 2.0, "perf_1m": 3.0, "volume_ratio": 1.5,
              "above_20_sma": "Y", "above_50_sma": "Y"}
    results = [evaluate_signals(metrics, "Strong Leader", "Strong Trend", True)
              for _ in range(5)]
    assert all(r == results[0] for r in results)


def test_signals_are_native_python_bools():
    """Regression guard: numpy.bool_ leaking from pandas comparisons broke JSON
    persistence of the signals payload during this phase."""
    metrics = {"rs_1m": 5.0, "rs_slope": 2.0, "perf_1m": 3.0, "volume_ratio": 1.5,
              "above_20_sma": "Y", "above_50_sma": "Y"}
    signals = evaluate_signals(metrics, "Strong Leader", "Strong Trend", True)
    for key, value in signals.items():
        assert type(value) is bool, f"{key} is {type(value)}, not a native bool"


def test_missing_inputs_never_turn_a_signal_on():
    """Absent data must weaken, never strengthen, a case."""
    empty = {"rs_1m": None, "rs_slope": None, "perf_1m": None, "volume_ratio": None,
            "above_20_sma": None, "above_50_sma": None}
    signals = evaluate_signals(empty, None, None, False)
    assert not any(signals.values())
    assert assign_category(signals)[0] == "Not Qualified"


def test_full_backfill_is_deterministic(backfilled):
    before = get_latest()[["symbol", "category", "rank_in_category", "signal_count"]]
    run_momentum_backfill(backfilled["dates"])
    after = get_latest()[["symbol", "category", "rank_in_category", "signal_count"]]
    assert before.equals(after), "Early Momentum backfill is not deterministic"


def test_metrics_are_arithmetically_correct():
    """Pure-function check against a hand-computable synthetic series."""
    dates = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(80)]
    closes = pd.Series([100.0 + i for i in range(80)], index=dates)
    volumes = pd.Series([1000] * 80, index=dates)
    nifty = pd.Series([200.0] * 80, index=dates)   # flat benchmark

    m = compute_stock_metrics(closes, volumes, nifty, dates[70])
    expected_perf_1m = (170.0 / 149.0 - 1) * 100   # 21 sessions back
    assert m["perf_1m"] == pytest.approx(expected_perf_1m, abs=5e-5)
    # Flat benchmark => relative strength equals the stock's own performance.
    assert m["rs_1m"] == pytest.approx(expected_perf_1m, abs=5e-5)
    assert m["above_20_sma"] == "Y"   # rising series is always above its own SMA


# ---------------------------------------------------------------------------
# Input data sanitisation (real defect found in V1's stored price history)
# ---------------------------------------------------------------------------
def test_sanitizer_drops_an_isolated_corrupt_close():
    """V1's price_history contains isolated bad prints (e.g. NIFTY 50 showing
    16,848 between two ~24,000 closes). They must be removed before any
    relative-strength maths runs."""
    dates = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(40)]
    closes = [24000.0] * 40
    closes[20] = 16848.0                      # the corrupt print
    frame = pd.DataFrame({"close": closes, "volume": [1000] * 40}, index=dates)

    clean, dropped = sanitize_closes(frame)
    assert dropped == 1
    assert 16848.0 not in set(clean["close"])
    assert len(clean) == 39


def test_sanitizer_keeps_legitimate_data_untouched():
    dates = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(40)]
    frame = pd.DataFrame({"close": [100.0 + i for i in range(40)],
                         "volume": [1000] * 40}, index=dates)
    clean, dropped = sanitize_closes(frame)
    assert dropped == 0
    assert len(clean) == len(frame)


def test_benchmark_is_clean_over_the_horizons_actually_used():
    """The 1W/1M/3M windows this engine reads must contain no implausible
    benchmark moves after sanitisation."""
    _, nifty = load_universe_series()
    recent = nifty.tail(70)          # comfortably covers the longest (3M) window
    moves = recent.pct_change().abs() * 100
    assert (moves.dropna() < 10).all(), \
        "Benchmark still contains implausible moves inside the horizons used"


def test_relative_strength_uses_the_same_calendar_window_for_both_series():
    """Regression guard for a real bug: comparing POSITION offsets across
    series of differing lengths measured the stock and the benchmark over
    different calendar spans, producing nonsense relative strength."""
    dates = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(80)]
    closes = pd.Series([100.0] * 80, index=dates)          # perfectly flat stock

    # Benchmark is also flat, but has FEWER rows (every 3rd session missing).
    sparse_dates = dates[::3]
    nifty = pd.Series([500.0] * len(sparse_dates), index=sparse_dates)

    m = compute_stock_metrics(closes, pd.Series([1000] * 80, index=dates), nifty, dates[70])
    # Both are flat, so relative strength must be exactly zero regardless of
    # the differing series lengths.
    assert m["rs_1m"] == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Ranking reproducibility
# ---------------------------------------------------------------------------
def test_ranks_are_contiguous_within_each_category(backfilled):
    df = get_latest()
    for category, cohort in df.groupby("category"):
        ranks = sorted(cohort["rank_in_category"])
        assert ranks == list(range(1, len(cohort) + 1)), \
            f"{category}: ranks are not 1..N contiguous"


def test_ranking_respects_documented_sort_keys(backfilled):
    """signal_count desc, then rs_1m desc, then symbol asc."""
    for category in ("Emerging Leader", "Building Momentum", "Watch Closely"):
        df = get_latest(category)
        if len(df) < 2:
            continue
        df = df.sort_values("rank_in_category")
        keys = [(-r["signal_count"],
                -(r["rs_1m"] if pd.notna(r["rs_1m"]) else -9e9),
                r["symbol"]) for _, r in df.iterrows()]
        assert keys == sorted(keys), f"{category}: ranking violates documented sort keys"


def test_ranking_is_reproducible_across_runs(backfilled):
    first = get_latest()[["symbol", "rank_in_category"]].sort_values("symbol")
    run_momentum_backfill(backfilled["dates"])
    second = get_latest()[["symbol", "rank_in_category"]].sort_values("symbol")
    assert first.reset_index(drop=True).equals(second.reset_index(drop=True))


def test_ranking_is_within_category_only(backfilled):
    """Rank 1 must exist separately in each populated category — proving there
    is no single market-wide ranking."""
    df = get_latest()
    populated = [c for c in CATEGORIES if not df[df["category"] == c].empty]
    for category in populated:
        assert 1 in set(df[df["category"] == category]["rank_in_category"])


# ---------------------------------------------------------------------------
# History retrieval
# ---------------------------------------------------------------------------
def test_history_retrieval_for_a_symbol(backfilled):
    df = get_latest()
    symbol = df["symbol"].iloc[0]
    hist = get_symbol_history(symbol)
    assert not hist.empty
    assert list(hist["trade_date"]) == sorted(hist["trade_date"])
    assert set(hist["symbol"]) == {symbol}


def test_category_history_covers_all_dates(backfilled):
    from intelligence_v2.services.early_momentum import get_category_history
    hist = get_category_history()
    assert not hist.empty
    assert set(hist["trade_date"]) == set(backfilled["dates"])


def test_backfill_replaces_rather_than_duplicates(backfilled):
    before = len(repo.get_by_date(backfilled["dates"][-1]))
    run_momentum_backfill([backfilled["dates"][-1]])
    after = len(repo.get_by_date(backfilled["dates"][-1]))
    assert before == after, "Re-running duplicated rows instead of replacing"


# ---------------------------------------------------------------------------
# Explainability generation
# ---------------------------------------------------------------------------
def test_reasons_and_missing_partition_all_nine_signals():
    signals = dict(ALL_OFF, rs_improving=True, above_20_sma=True)
    satisfied, missing = build_reasons(signals)
    assert len(satisfied) + len(missing) == len(SIGNAL_LABELS)
    assert set(satisfied).isdisjoint(missing)


def test_every_stored_row_carries_explainability(backfilled):
    df = get_latest()
    for _, row in df.iterrows():
        assert row["category_reason"], f"{row['symbol']}: missing category reason"
        assert isinstance(row["signals"], dict) and row["signals"]
        assert len(row["reasons"]) == row["signal_count"], \
            f"{row['symbol']}: reason count does not match signal_count"


def test_qualified_rows_always_list_at_least_one_reason(backfilled):
    df = get_latest()
    qualified = df[df["category"] != "Not Qualified"]
    for _, row in qualified.iterrows():
        assert row["reasons"], f"{row['symbol']} is {row['category']} but lists no reason"


def test_signal_count_matches_signals_dict():
    signals = dict(ALL_OFF, rs_improving=True, above_20_sma=True, rs_positive=True)
    assert signal_count(signals) == 3


# ---------------------------------------------------------------------------
# V1 unchanged
# ---------------------------------------------------------------------------
def test_v1_row_counts_unchanged_after_phase3(backfilled):
    before = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
             for t in V1_BASELINE_TABLES}
    run_momentum_backfill(backfilled["dates"])
    after = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
            for t in V1_BASELINE_TABLES}
    assert before == after, f"V1 changed! before={before} after={after}"


def test_no_new_connector_was_introduced():
    """Phase 3 forbids new external data sources. The connectors package must
    remain empty of modules."""
    import pathlib

    import intelligence_v2.connectors as connectors_pkg

    pkg_dir = pathlib.Path(connectors_pkg.__file__).parent
    modules = [p.name for p in pkg_dir.glob("*.py") if p.name != "__init__.py"]
    assert not modules, f"Phase 3 must not add connectors, but found: {modules}"


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------
def test_phase0_health_check_still_passes():
    from intelligence_v2.services.health import run_health_check
    results = run_health_check()
    failed = [k for k, v in results.items() if k != "_overall" and not v["ok"]]
    assert not failed, f"Phase 0 health check regressed: {failed}"


def test_full_app_renders_including_all_three_v2_pages():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=120).run()
    assert not at.exception, [e.message for e in at.exception]

    options = at.sidebar.radio[0].options
    for expected in ("🔥 Sector Intelligence (V2)", "🔄 Market Cycle (V2)",
                    "🚀 Early Momentum (V2)"):
        assert expected in options, f"{expected} missing from navigation"

    ok = True
    for label in options:
        at.sidebar.radio[0].set_value(label).run()
        if at.exception:
            ok = False
            print(f"Exception on {label!r}: {[e.message for e in at.exception]}")
    assert ok, "One or more pages raised an exception"
