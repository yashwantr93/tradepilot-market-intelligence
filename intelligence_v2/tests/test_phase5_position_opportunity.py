"""
Phase 5 (Position Opportunity Engine) verification suite — the final phase of
the V2 Intelligence Stack.

Covers every checkmark required at the end of Phase 5:
  - Category assignment
  - Deterministic behaviour
  - Ranking reproducibility
  - Explainability generation
  - History retrieval
  - Shared RS Engine usage
  - V1 unchanged
  - Existing modules unaffected
  - Full regression suite

Run with:  python -m pytest intelligence_v2/tests/ -v
"""

from __future__ import annotations

import ast
import datetime as dt
import inspect

import pandas as pd
import pytest

from intelligence_v2.config.position_opportunity import CATEGORIES, SIGNAL_LABELS
from intelligence_v2.database import position_repository as repo
from intelligence_v2.database.engine import init_db
from intelligence_v2.database.v1_reference import read_v1
from intelligence_v2.processors import momentum_metrics, position_classifier
from intelligence_v2.processors.position_classifier import (
    assign_category,
    build_reasons,
    evaluate_signals,
    signal_count,
)
from intelligence_v2.processors.momentum_metrics import compute_stock_metrics, load_universe_series
from intelligence_v2.services.position_opportunity import (
    get_available_dates,
    get_category_counts,
    get_latest,
    get_symbol_history,
    run_position_backfill,
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
    assert dates, "Phase 1/2/3 context missing — run those phases first"
    result = run_position_backfill(dates)
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


def test_high_conviction_position_requires_full_evidence():
    category, _ = assign_category(ALL_ON)
    assert category == "High Conviction Position"


def test_high_conviction_position_denied_without_backdrop():
    """Sector strength OR bullish cycle OR Early Momentum confirmation is
    mandatory for High Conviction Position."""
    signals = dict(ALL_ON, sector_strength=False, cycle_bullish=False,
                   early_momentum_confirmed=False)
    category, _ = assign_category(signals)
    assert category != "High Conviction Position"
    assert category == "Position Candidate"


def test_position_candidate_rule():
    signals = dict(ALL_OFF, rs_improving=True, above_50_sma=True, rs_positive=True)
    assert assign_category(signals)[0] == "Position Candidate"


def test_accumulation_watch_on_single_early_sign():
    signals = dict(ALL_OFF, rs_improving=True)
    assert assign_category(signals)[0] == "Accumulation Watch"
    signals2 = dict(ALL_OFF, above_50_sma=True, price_momentum=True)
    assert assign_category(signals2)[0] == "Accumulation Watch"


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
# Deterministic behaviour
# ---------------------------------------------------------------------------
def test_signal_evaluation_is_deterministic():
    metrics = {"rs_3m": 5.0, "rs_slope": 2.0, "perf_3m": 3.0,
              "above_50_sma": "Y", "above_200_sma": "Y"}
    results = [evaluate_signals(metrics, "Strong Leader", "Strong Trend",
                                "Emerging Leader", True) for _ in range(5)]
    assert all(r == results[0] for r in results)


def test_signals_are_native_python_bools():
    """Regression guard: numpy.bool_ leaking from pandas comparisons broke JSON
    persistence of the signals payload during Phase 3 — the same fix applies here."""
    metrics = {"rs_3m": 5.0, "rs_slope": 2.0, "perf_3m": 3.0,
              "above_50_sma": "Y", "above_200_sma": "Y"}
    signals = evaluate_signals(metrics, "Strong Leader", "Strong Trend", "Emerging Leader", True)
    for key, value in signals.items():
        assert type(value) is bool, f"{key} is {type(value)}, not a native bool"


def test_missing_inputs_never_turn_a_signal_on():
    """Absent data must weaken, never strengthen, a case."""
    empty = {"rs_3m": None, "rs_slope": None, "perf_3m": None,
            "above_50_sma": None, "above_200_sma": None}
    signals = evaluate_signals(empty, None, None, None, False)
    assert not any(signals.values())
    assert assign_category(signals)[0] == "Not Qualified"


def test_full_backfill_is_deterministic(backfilled):
    before = get_latest()[["symbol", "category", "rank_in_category", "signal_count"]]
    run_position_backfill(backfilled["dates"])
    after = get_latest()[["symbol", "category", "rank_in_category", "signal_count"]]
    assert before.equals(after), "Position Opportunity backfill is not deterministic"


def test_metrics_are_arithmetically_correct():
    """Pure-function check against a hand-computable synthetic series — same
    shared metrics function Phase 3/4 use, reused unmodified here."""
    dates = [dt.date(2026, 1, 1) + dt.timedelta(days=i) for i in range(260)]
    closes = pd.Series([100.0 + i * 0.5 for i in range(260)], index=dates)  # steady rise
    volumes = pd.Series([1000] * 260, index=dates)
    nifty = pd.Series([200.0] * 260, index=dates)   # flat benchmark

    m = compute_stock_metrics(closes, volumes, nifty, dates[250])
    expected_perf_3m = (closes.iloc[250] / closes.iloc[250 - 63] - 1) * 100
    assert m["perf_3m"] == pytest.approx(expected_perf_3m, abs=5e-5)
    # Flat benchmark => relative strength equals the stock's own performance.
    assert m["rs_3m"] == pytest.approx(expected_perf_3m, abs=5e-5)
    assert m["above_200_sma"] == "Y"   # steadily rising series is always above its own SMA


# ---------------------------------------------------------------------------
# Shared RS engine usage — Phase 5 must NOT recompute stock metrics
# ---------------------------------------------------------------------------
def test_position_engine_reuses_phase3_metrics_infrastructure():
    """Phase 5 must not duplicate stock-level RS/SMA/momentum computation —
    it imports momentum_metrics.compute_stock_metrics directly (itself built
    on the shared Relative Strength Engine), per the 'reuse infrastructure,
    no new indicators' instruction."""
    import intelligence_v2.services.position_opportunity as position_svc

    source = inspect.getsource(position_svc)
    tree = ast.parse(source)
    imported = {
        (node.module, alias.name)
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert ("intelligence_v2.processors.momentum_metrics", "compute_stock_metrics") in imported
    assert ("intelligence_v2.processors.momentum_metrics", "load_universe_series") in imported


def test_position_classifier_has_no_independent_metric_computation():
    """position_classifier.py must contain only classification logic — no
    position/date-lookup or performance-calculation primitives of its own."""
    source = inspect.getsource(position_classifier)
    for forbidden in ("bisect", "position_at_or_before", "def perf", "def rs_"):
        assert forbidden not in source, (
            f"position_classifier.py appears to reimplement RS machinery "
            f"(found {forbidden!r}) instead of reusing the shared engine")


def test_shared_relative_strength_engine_underlies_position_metrics():
    """compute_stock_metrics (reused unmodified by Phase 5) is itself built on
    the shared engine — confirm the chain is intact via AST import scan."""
    source = inspect.getsource(momentum_metrics)
    tree = ast.parse(source)
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "intelligence_v2.processors.shared_relative_strength" in modules


def test_position_config_reuses_phase3_sector_and_cycle_definitions():
    """SECTOR_STRENGTH_STATES / CYCLE_CONFIRMING_STAGES must be imported from
    Phase 3's config, not redefined — proves no duplicated business rules."""
    import intelligence_v2.config.position_opportunity as position_config

    source = inspect.getsource(position_config)
    tree = ast.parse(source)
    imported = {
        (node.module, alias.name)
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert ("intelligence_v2.config.early_momentum", "SECTOR_STRENGTH_STATES") in imported
    assert ("intelligence_v2.config.early_momentum", "CYCLE_CONFIRMING_STAGES") in imported


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
    """rs_3m desc, sector_rs_1m desc, cycle_rank asc, perf_3m desc, symbol asc."""
    from intelligence_v2.config.position_opportunity import CYCLE_RANK_ORDER

    for category in ("High Conviction Position", "Position Candidate", "Accumulation Watch"):
        df = get_latest(category)
        if len(df) < 2:
            continue
        df = df.sort_values("rank_in_category")
        keys = [(
            -(r["rs_3m"] if pd.notna(r["rs_3m"]) else -9e9),
            -(r["sector_rs_1m"] if pd.notna(r["sector_rs_1m"]) else -9e9),
            CYCLE_RANK_ORDER.get(r["cycle_stage"], len(CYCLE_RANK_ORDER)),
            -(r["perf_3m"] if pd.notna(r["perf_3m"]) else -9e9),
            r["symbol"],
        ) for _, r in df.iterrows()]
        assert keys == sorted(keys), f"{category}: ranking violates documented sort keys"


def test_ranking_is_reproducible_across_runs(backfilled):
    first = get_latest()[["symbol", "rank_in_category"]].sort_values("symbol")
    run_position_backfill(backfilled["dates"])
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
    from intelligence_v2.services.position_opportunity import get_category_history
    hist = get_category_history()
    assert not hist.empty
    assert set(hist["trade_date"]) == set(backfilled["dates"])


def test_backfill_replaces_rather_than_duplicates(backfilled):
    before = len(repo.get_by_date(backfilled["dates"][-1]))
    run_position_backfill([backfilled["dates"][-1]])
    after = len(repo.get_by_date(backfilled["dates"][-1]))
    assert before == after, "Re-running duplicated rows instead of replacing"


# ---------------------------------------------------------------------------
# Explainability generation
# ---------------------------------------------------------------------------
def test_reasons_and_missing_partition_all_nine_signals():
    signals = dict(ALL_OFF, rs_improving=True, above_50_sma=True)
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
    signals = dict(ALL_OFF, rs_improving=True, above_50_sma=True, rs_positive=True)
    assert signal_count(signals) == 3


# ---------------------------------------------------------------------------
# V1 unchanged
# ---------------------------------------------------------------------------
def test_v1_row_counts_unchanged_after_phase5(backfilled):
    before = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
             for t in V1_BASELINE_TABLES}
    run_position_backfill(backfilled["dates"])
    after = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
            for t in V1_BASELINE_TABLES}
    assert before == after, f"V1 changed! before={before} after={after}"


def test_no_new_connector_was_introduced():
    """Phase 5 forbids new external data sources. The connectors package must
    remain empty of modules."""
    import pathlib

    import intelligence_v2.connectors as connectors_pkg

    pkg_dir = pathlib.Path(connectors_pkg.__file__).parent
    modules = [p.name for p in pkg_dir.glob("*.py") if p.name != "__init__.py"]
    assert not modules, f"Phase 5 must not add connectors, but found: {modules}"


# ---------------------------------------------------------------------------
# Existing modules unaffected
# ---------------------------------------------------------------------------
def test_phase3_and_phase4_data_unaffected_by_phase5_backfill(backfilled):
    """Phase 5 reads Phase 3's early_momentum_daily table but must never write
    to it, and must not disturb Phase 4's independent bearish_opportunity_daily
    table."""
    from intelligence_v2.database import bearish_repository, momentum_repository

    em_before = len(momentum_repository.get_latest())
    bear_before = len(bearish_repository.get_latest())
    run_position_backfill(backfilled["dates"])
    em_after = len(momentum_repository.get_latest())
    bear_after = len(bearish_repository.get_latest())
    assert em_before == em_after, "Phase 5 backfill altered Phase 3's stored data"
    assert bear_before == bear_after, "Phase 5 backfill altered Phase 4's stored data"


# ---------------------------------------------------------------------------
# Regression — full stack
# ---------------------------------------------------------------------------
def test_phase0_health_check_still_passes():
    from intelligence_v2.services.health import run_health_check
    results = run_health_check()
    failed = [k for k, v in results.items() if k != "_overall" and not v["ok"]]
    assert not failed, f"Phase 0 health check regressed: {failed}"


def test_full_app_renders_including_all_five_v2_pages():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=120).run()
    assert not at.exception, [e.message for e in at.exception]

    options = at.sidebar.radio[0].options
    for expected in ("🔥 Sector Intelligence (V2)", "🔄 Market Cycle (V2)",
                    "🚀 Early Momentum (V2)", "📉 Bearish Opportunities (V2)",
                    "🧭 Position Opportunities (V2)"):
        assert expected in options, f"{expected} missing from navigation"

    ok = True
    for label in options:
        at.sidebar.radio[0].set_value(label).run()
        if at.exception:
            ok = False
            print(f"Exception on {label!r}: {[e.message for e in at.exception]}")
    assert ok, "One or more pages raised an exception"
