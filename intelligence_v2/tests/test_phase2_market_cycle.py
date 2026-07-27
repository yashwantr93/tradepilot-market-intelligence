"""
Phase 2 (Market Cycle Engine) verification suite.

Covers every checkmark required at the end of Phase 2:
  - State calculation
  - Transition history
  - Hysteresis
  - Deterministic outputs
  - V1 unchanged
  - Regression tests pass

Run with:  python -m pytest intelligence_v2/tests/ -v
"""

from __future__ import annotations

import pytest

from intelligence_v2.config.market_cycle import (
    CYCLE_STAGES,
    MIN_CYCLE_CONFIRMATIONS,
    MIN_CYCLE_DWELL_DAYS,
)
from intelligence_v2.database import cycle_repository as crepo
from intelligence_v2.database.engine import init_db
from intelligence_v2.database.v1_reference import read_v1
from intelligence_v2.processors.cycle_classifier import (
    apply_cycle_hysteresis,
    build_confidence_notes,
    classify_cycle_stage,
)
from intelligence_v2.services.market_cycle import (
    get_current_market_cycle,
    get_sector_intelligence_dates,
    get_transition_history,
    run_cycle_backfill,
)

V1_BASELINE_TABLES = [
    "daily_watchlist", "institutional_watchlist", "combined_watchlist",
    "signals", "symbol_master", "sector_rotation", "price_history",
]

# Reusable metric fixtures for classifier tests.
STRONG = {"rs_1w": 5, "rs_1m": 5, "rs_3m": 5, "rs_6m": 5, "rs_1y": 5, "momentum_1m": 2,
         "above_20_sma": "Y", "above_50_sma": "Y", "above_200_sma": "Y", "perf_3m": 10}


@pytest.fixture(scope="module", autouse=True)
def cycled():
    init_db()
    dates = get_sector_intelligence_dates()
    assert dates, "Phase 1 output missing — run Sector Intelligence first"
    result = run_cycle_backfill(dates)
    return {"dates": dates, "result": result}


# ---------------------------------------------------------------------------
# State calculation
# ---------------------------------------------------------------------------
def test_cycle_rows_written(cycled):
    assert cycled["result"]["rows_written"] > 0
    current = get_current_market_cycle()
    assert not current.empty


def test_every_sector_gets_exactly_one_valid_stage(cycled):
    current = get_current_market_cycle()
    assert current["sector"].is_unique, "A sector appeared more than once for the same date"
    assert set(current["stage"]) <= set(CYCLE_STAGES), \
        f"Unexpected stage value(s): {set(current['stage']) - set(CYCLE_STAGES)}"
    assert current["stage"].notna().all()


def test_backfill_is_idempotent(cycled):
    before = len(crepo.get_cycle_history("Banking"))
    run_cycle_backfill(cycled["dates"])
    after = len(crepo.get_cycle_history("Banking"))
    assert before == after, "Re-running the cycle backfill duplicated rows"


@pytest.mark.parametrize("metrics,expected", [
    # Strong Trend — above 20/50, RS positive 1M/3M/6M, momentum not falling
    (STRONG, "Strong Trend"),
    # Distribution — still above 50-SMA but short-term RS rolled over + momentum down
    ({"rs_1w": -2, "rs_1m": -2, "rs_3m": 5, "rs_6m": 5, "rs_1y": 5, "momentum_1m": -3,
      "above_20_sma": "N", "above_50_sma": "Y", "above_200_sma": "Y"}, "Distribution"),
    # Mature Trend — above 50, 3M RS positive, momentum decelerating
    ({"rs_1w": 1, "rs_1m": 1, "rs_3m": 5, "rs_6m": 5, "rs_1y": 5, "momentum_1m": -1,
      "above_20_sma": "Y", "above_50_sma": "Y", "above_200_sma": "Y"}, "Mature Trend"),
    # Early Momentum — strong short-term, long-horizon not established, momentum up
    ({"rs_1w": 6, "rs_1m": 6, "rs_3m": 1, "rs_6m": 1, "rs_1y": 1, "momentum_1m": 4,
      "above_20_sma": "Y", "above_50_sma": "Y", "above_200_sma": "N"}, "Early Momentum"),
    # Recovery — long-term laggard turning up, reclaimed 20-SMA
    ({"rs_1w": 1, "rs_1m": 2, "rs_3m": -1, "rs_6m": -8, "rs_1y": -10, "momentum_1m": 1,
      "above_20_sma": "Y", "above_50_sma": "N", "above_200_sma": "N"}, "Recovery"),
    # Accumulation — below 50-SMA, RS still negative, but deterioration stopped
    ({"rs_1w": -1, "rs_1m": -4, "rs_3m": -6, "rs_6m": -8, "rs_1y": -9, "momentum_1m": 1,
      "above_20_sma": "N", "above_50_sma": "N", "above_200_sma": "N"}, "Accumulation"),
    # Weak Trend — below 50-SMA, RS negative, still deteriorating
    ({"rs_1w": -5, "rs_1m": -6, "rs_3m": -7, "rs_6m": -8, "rs_1y": -9, "momentum_1m": -4,
      "above_20_sma": "N", "above_50_sma": "N", "above_200_sma": "N"}, "Weak Trend"),
])
def test_classifier_covers_all_seven_stages(metrics, expected):
    assert classify_cycle_stage(metrics)["stage"] == expected


def test_fallback_assigns_a_valid_stage_and_is_flagged():
    """A directionless reading that matches no specific rule must still get
    exactly one valid stage, and must be flagged as fallback-matched."""
    directionless = {"rs_1w": 0, "rs_1m": 0, "rs_3m": 0, "rs_6m": 0, "rs_1y": 0,
                    "momentum_1m": 0, "above_20_sma": "Y", "above_50_sma": "Y",
                    "above_200_sma": "Y"}
    result = classify_cycle_stage(directionless)
    assert result["stage"] in CYCLE_STAGES
    assert result["matched_by_fallback"] == "Y"


def test_every_classification_carries_explainability():
    result = classify_cycle_stage(STRONG)
    assert result["reasons"], "A stage must always come with human-readable reasons"
    assert all(isinstance(r, str) and r for r in result["reasons"])
    assert result["possible_behaviour"], "A stage must always carry a behaviour note"


def test_confidence_notes_are_never_empty():
    notes = build_confidence_notes(STRONG, history_days=3, matched_by_fallback="N",
                                  data_method="basket_from_v1_price_history (5/5 members)")
    assert notes and all(isinstance(n, str) for n in notes)


# ---------------------------------------------------------------------------
# Deterministic outputs
# ---------------------------------------------------------------------------
def test_classification_is_deterministic_across_repeated_calls():
    results = [classify_cycle_stage(STRONG) for _ in range(5)]
    assert all(r == results[0] for r in results)


def test_full_backfill_is_deterministic(cycled):
    """Re-running the entire backfill must reproduce identical stages."""
    before = get_current_market_cycle()[["sector", "stage", "raw_stage", "days_in_stage"]]
    run_cycle_backfill(cycled["dates"])
    after = get_current_market_cycle()[["sector", "stage", "raw_stage", "days_in_stage"]]
    assert before.equals(after), "Cycle backfill is not deterministic across runs"


# ---------------------------------------------------------------------------
# Hysteresis
# ---------------------------------------------------------------------------
def test_hysteresis_blocks_a_single_day_flip():
    """One divergent reading must NOT change the confirmed stage."""
    stage, days, transitioned = apply_cycle_hysteresis(
        "Weak Trend", "Strong Trend", 8, ["Strong Trend", "Strong Trend"])
    assert stage == "Strong Trend"
    assert transitioned is False
    assert days == 9


def test_hysteresis_confirms_on_majority():
    """Candidate present in MIN_CYCLE_CONFIRMATIONS of the window -> commit."""
    recent = ["Weak Trend"] + ["Strong Trend"] * (MIN_CYCLE_DWELL_DAYS - 2)
    stage, days, transitioned = apply_cycle_hysteresis(
        "Weak Trend", "Strong Trend", 8, recent)
    assert stage == "Weak Trend"
    assert transitioned is True
    assert days == 1


def test_hysteresis_first_ever_reading_has_no_prior():
    stage, days, transitioned = apply_cycle_hysteresis("Accumulation", None, 0, [])
    assert (stage, days, transitioned) == ("Accumulation", 1, False)


def test_hysteresis_same_stage_increments_dwell():
    stage, days, transitioned = apply_cycle_hysteresis(
        "Strong Trend", "Strong Trend", 4, ["Strong Trend"])
    assert (stage, days, transitioned) == ("Strong Trend", 5, False)


def test_hysteresis_cannot_get_permanently_stuck_on_alternating_noise():
    """Regression guard for a real bug found in this phase: the original
    'N consecutive identical' rule froze a sector on its first-ever stage
    forever when raw readings alternated (Defence never got 3 in a row, so it
    displayed 'Strong Trend' for 11 sessions while every recent reading said
    otherwise). The majority rule must eventually commit."""
    prior = "Strong Trend"
    days = 1
    # Alternating noise: Recovery, Accumulation, Recovery, Accumulation...
    alternating = ["Recovery", "Accumulation"] * 6
    committed_to_something_new = False
    recent: list[str] = []
    for raw in alternating:
        prior, days, transitioned = apply_cycle_hysteresis(raw, prior, days, recent[::-1][:2])
        recent.append(raw)
        if transitioned:
            committed_to_something_new = True
    assert committed_to_something_new, \
        "Hysteresis never committed under alternating readings — it is stuck again"
    assert prior != "Strong Trend"


def test_stored_stage_matches_raw_or_is_explained(cycled):
    """If a stored row's confirmed stage differs from its raw stage, the
    reasons text must say so — never silently show a contradicting label."""
    current = get_current_market_cycle()
    diverged = current[current["stage"] != current["raw_stage"]]
    for _, row in diverged.iterrows():
        joined = " ".join(row["reasons"]).lower()
        assert "holding at" in joined, \
            f"{row['sector']}: stage != raw_stage but reasons do not explain the hold"


# ---------------------------------------------------------------------------
# Transition history
# ---------------------------------------------------------------------------
def test_transition_history_recorded(cycled):
    tr = get_transition_history()
    assert not tr.empty, "No transitions were logged across the full backfill"
    required = {"sector", "transition_date", "from_stage", "to_stage",
               "days_in_previous_stage", "reasons"}
    assert required <= set(tr.columns)


def test_every_transition_has_a_reason(cycled):
    tr = get_transition_history()
    for _, row in tr.iterrows():
        assert row["reasons"], f"Transition {row['sector']} {row['to_stage']} has no reason"


def test_transitions_only_contain_valid_stages(cycled):
    tr = get_transition_history()
    assert set(tr["to_stage"]) <= set(CYCLE_STAGES)
    froms = set(tr["from_stage"].dropna())
    assert froms <= set(CYCLE_STAGES)


def test_transition_filter_by_sector_works(cycled):
    tr = get_transition_history()
    sector = tr["sector"].iloc[0]
    filtered = get_transition_history(sector=sector)
    assert set(filtered["sector"]) == {sector}


# ---------------------------------------------------------------------------
# V1 unchanged
# ---------------------------------------------------------------------------
def test_v1_row_counts_unchanged_after_phase2(cycled):
    before = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
             for t in V1_BASELINE_TABLES}
    run_cycle_backfill(cycled["dates"])
    after = {t: read_v1(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
            for t in V1_BASELINE_TABLES}
    assert before == after, f"V1 changed! before={before} after={after}"


def test_cycle_engine_reads_no_v1_tables_directly():
    """Phase 2's brief restricts the data source to market_v2.db. Verify the
    service module does not import the V1 bridge at all."""
    import ast
    import inspect

    import intelligence_v2.services.market_cycle as mod

    tree = ast.parse(inspect.getsource(mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert not any("v1_reference" in m for m in imported), \
        "Market Cycle must read only market_v2.db, but it imports the V1 bridge"


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------
def test_phase0_health_check_still_passes():
    from intelligence_v2.services.health import run_health_check
    results = run_health_check()
    failed = [k for k, v in results.items() if k != "_overall" and not v["ok"]]
    assert not failed, f"Phase 0 health check regressed: {failed}"


def test_full_app_renders_including_both_v2_pages():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=90).run()
    assert not at.exception, [e.message for e in at.exception]

    options = at.sidebar.radio[0].options
    assert "🔄 Market Cycle (V2)" in options, "Market Cycle page not wired into app.py"
    assert "🔥 Sector Intelligence (V2)" in options, "Phase 1 page disappeared"

    ok = True
    for label in options:
        at.sidebar.radio[0].set_value(label).run()
        if at.exception:
            ok = False
            print(f"Exception on {label!r}: {[e.message for e in at.exception]}")
    assert ok, "One or more pages raised an exception"
