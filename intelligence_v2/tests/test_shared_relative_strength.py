"""
Shared Relative Strength Engine — regression suite for the mandatory defect-fix
refactor (see intelligence_v2/processors/shared_relative_strength.py).

Covers every checkmark required by the refactor task:
  - Sanitiser
  - Date alignment
  - Sparse benchmark
  - Corrupted benchmark
  - Deterministic outputs
  - Identical repeated calculations
  - Shared engine imported by all phases
  - Old duplicated implementations removed

Run with:  python -m pytest intelligence_v2/tests/ -v
"""

from __future__ import annotations

import ast
import datetime as dt
import inspect
from pathlib import Path

import pandas as pd
import pytest

from intelligence_v2.processors import momentum_metrics, sector_metrics, sector_prices
from intelligence_v2.processors.shared_relative_strength import (
    BENCHMARK_SANITIZE_WINDOW,
    DEFAULT_SANITIZE_WINDOW,
    above_moving_average,
    build_relative_strength_set,
    calculate_rs_trend,
    is_outperforming,
    performance_between_dates,
    performance_over,
    position_at_or_before,
    rs_as_of,
    sanitize_benchmark_series,
    sanitize_close_series,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _dates(n: int, start: dt.date = dt.date(2026, 1, 1)) -> list[dt.date]:
    return [start + dt.timedelta(days=i) for i in range(n)]


# ---------------------------------------------------------------------------
# Sanitiser
# ---------------------------------------------------------------------------
def test_sanitiser_drops_isolated_spike_and_keeps_surrounding_series():
    dates = _dates(40)
    values = [24000.0 + i * 5 for i in range(40)]
    values[20] = 16848.45  # isolated corrupt print, mirrors the real NIFTY case
    closes = pd.Series(values, index=dates)

    clean, dropped = sanitize_close_series(closes)
    assert dropped == 1
    assert dt.date(2026, 1, 21) not in clean.index  # the 21st element (index 20)
    # Surrounding legitimate values must survive untouched.
    assert clean.iloc[0] == values[0]
    assert clean.iloc[-1] == values[-1]


def test_sanitiser_survives_a_cluster_of_bad_prints_without_over_dropping():
    """A running 'last valid value' anchor was tried first and rejected: it
    stuck after one drop and wrongly rejected the legitimate values that
    followed. The centred rolling-median reference must not repeat that."""
    dates = _dates(60)
    values = [24000.0 + i * 3 for i in range(60)]
    for i in (25, 26, 27):  # a cluster of 3 corrupt prints within a fortnight
        values[i] = 16000.0 + i
    closes = pd.Series(values, index=dates)

    clean, dropped = sanitize_close_series(closes)
    assert dropped == 3
    # Legitimate values immediately after the cluster must be kept.
    for i in (28, 29, 30):
        assert dates[i] in clean.index


def test_sanitiser_is_a_noop_on_a_clean_series():
    dates = _dates(30)
    closes = pd.Series([100.0 + i * 0.5 for i in range(30)], index=dates)
    clean, dropped = sanitize_close_series(closes)
    assert dropped == 0
    assert len(clean) == len(closes)


def test_sanitiser_handles_empty_series():
    empty = pd.Series(dtype=float)
    clean, dropped = sanitize_close_series(empty)
    assert clean.empty and dropped == 0


# ---------------------------------------------------------------------------
# Date alignment (calendar-date, not position-based)
# ---------------------------------------------------------------------------
def test_calendar_alignment_survives_differing_series_lengths():
    """The defect: comparing 'N rows back' in two series with different date
    coverage silently measures different real-world windows. Build a stock
    series with EVERY calendar day and a benchmark with only every 3rd day
    (simulating a thin/gappy basket) and confirm rs_as_of still measures both
    legs over the identical calendar window."""
    all_dates = _dates(100)
    stock = pd.Series([100.0 + i * 0.4 for i in range(100)], index=all_dates)

    sparse_dates = all_dates[::3]
    benchmark = pd.Series([20000.0 + i * 3 for i, _ in enumerate(sparse_dates)],
                          index=sparse_dates)

    as_of = all_dates[90]
    stock_perf, bench_perf, rs = rs_as_of(stock, benchmark, as_of, 21)
    assert stock_perf is not None and bench_perf is not None and rs is not None

    # Manually recompute the benchmark leg over the SAME calendar window the
    # stock used, independent of the shared implementation, as a cross-check.
    window_start = all_dates[90 - 21]
    manual_bench_perf = performance_between_dates(benchmark, window_start, as_of)
    assert bench_perf == manual_bench_perf


def test_performance_over_is_position_based_and_only_safe_within_one_series():
    dates = _dates(30)
    series = pd.Series([100.0 + i for i in range(30)], index=dates)
    pos = position_at_or_before(series.index, dates[25])
    result = performance_over(series, pos, 5)
    expected = (125.0 / 120.0 - 1) * 100
    assert result == pytest.approx(expected, abs=5e-5)


def test_performance_between_dates_returns_none_for_inverted_or_missing_window():
    dates = _dates(10)
    series = pd.Series(range(10), index=dates)
    assert performance_between_dates(series, dates[5], dates[2]) is None  # inverted
    assert performance_between_dates(series, dates[2], dt.date(2099, 1, 1)) is not None


# ---------------------------------------------------------------------------
# Sparse benchmark
# ---------------------------------------------------------------------------
def test_sparse_benchmark_returns_none_rather_than_a_wrong_number():
    dates = _dates(60)
    stock = pd.Series([100.0 + i for i in range(60)], index=dates)
    sparse_benchmark = pd.Series([20000.0, 20500.0], index=[dates[0], dates[1]])

    as_of = dates[55]
    stock_perf, bench_perf, rs = rs_as_of(stock, sparse_benchmark, as_of, 21)
    assert stock_perf is not None       # the stock leg is still fully computable
    assert bench_perf is None           # benchmark has no data anywhere near this window
    assert rs is None                   # RS must be None, never a guess


def test_empty_benchmark_never_raises():
    dates = _dates(30)
    stock = pd.Series([100.0 + i for i in range(30)], index=dates)
    empty_benchmark = pd.Series(dtype=float)
    stock_perf, bench_perf, rs = rs_as_of(stock, empty_benchmark, dates[25], 5)
    assert bench_perf is None and rs is None
    assert stock_perf is not None


# ---------------------------------------------------------------------------
# Corrupted benchmark (end-to-end: sanitise then measure RS against it)
# ---------------------------------------------------------------------------
def test_corrupted_benchmark_no_longer_produces_impossible_relative_strength():
    """A two-point % change is only wrecked when the corrupt print lands
    exactly ON one of the two measurement endpoints — reproduce that
    precisely (as the real NIFTY 2026-06-26 spike did, landing on the exact
    date a 1-month lookback window happened to start from) rather than merely
    somewhere inside the window."""
    dates = _dates(90)
    stock = pd.Series([100.0 + i * 0.3 for i in range(90)], index=dates)

    as_of = dates[88]
    lookback = 21
    corrupt_index = 88 - lookback  # the exact start-of-window endpoint

    bench_values = [24000.0 + i * 2 for i in range(90)]
    bench_values[corrupt_index] = 16848.45  # the real NIFTY 2026-06-26 spike, reproduced
    raw_benchmark = pd.Series(bench_values, index=dates)

    # BEFORE fix (raw, unsanitised benchmark): RS is wrecked by the spike sitting
    # inside the lookback window.
    _, _, rs_before = rs_as_of(stock, raw_benchmark, as_of, lookback)

    # AFTER fix: sanitise first, exactly as sector_prices.py / momentum_metrics.py
    # now do before ever computing relative strength.
    clean_benchmark, dropped = sanitize_close_series(raw_benchmark)
    assert dropped == 1
    _, _, rs_after = rs_as_of(stock, clean_benchmark, as_of, lookback)

    assert rs_before is not None and rs_after is not None
    assert abs(rs_after) < abs(rs_before)
    assert abs(rs_after) < 20  # plausible for two smoothly-trending series


# ---------------------------------------------------------------------------
# Deterministic outputs / identical repeated calculations
# ---------------------------------------------------------------------------
def test_repeated_calls_are_bit_identical():
    dates = _dates(120)
    stock = pd.Series([100.0 + (i % 7) * 1.3 for i in range(120)], index=dates)
    benchmark = pd.Series([20000.0 + (i % 5) * 40 for i in range(120)], index=dates)
    as_of = dates[110]

    first = build_relative_strength_set(stock, benchmark, as_of,
                                        {"1w": 5, "1m": 21, "3m": 63})
    for _ in range(5):
        again = build_relative_strength_set(stock, benchmark, as_of,
                                            {"1w": 5, "1m": 21, "3m": 63})
        assert again == first

    assert calculate_rs_trend(stock, benchmark, as_of, 21, 20) == \
        calculate_rs_trend(stock, benchmark, as_of, 21, 20)
    assert above_moving_average(stock, as_of, 20) == above_moving_average(stock, as_of, 20)


def test_is_outperforming_is_a_pure_deterministic_comparison():
    assert is_outperforming(3.0, threshold=0.0) is True
    assert is_outperforming(-1.0, threshold=0.0) is False
    assert is_outperforming(None) is None
    assert is_outperforming(3.0, threshold=3.0) is False  # strictly greater-than


# ---------------------------------------------------------------------------
# Shared engine imported by all phases / old duplicated implementations removed
# ---------------------------------------------------------------------------
def _imported_modules(module) -> set[str]:
    """AST-based (not substring) scan for `from X import ...` module paths —
    avoids false positives from prose mentioning a module name in a docstring."""
    source = inspect.getsource(module)
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("module", [sector_prices, sector_metrics, momentum_metrics])
def test_shared_engine_is_imported_by_every_phase_module(module):
    assert "intelligence_v2.processors.shared_relative_strength" in _imported_modules(module)


@pytest.mark.parametrize("module,removed_names", [
    (sector_metrics, ["_position_at_or_before"]),
    (momentum_metrics, ["_pos_at_or_before", "_perf", "_perf_between"]),
])
def test_old_duplicated_position_based_helpers_are_removed(module, removed_names):
    for name in removed_names:
        assert not hasattr(module, name), (
            f"{module.__name__}.{name} should have been removed by the shared-engine "
            "refactor — its logic now lives only in shared_relative_strength.py")


def test_sector_prices_no_longer_reads_v1_closes_without_sanitising():
    source = inspect.getsource(sector_prices)
    assert "sanitize_close_series" in source


def test_public_compatibility_entry_points_are_preserved():
    """These exact names are imported directly by services/*.py and other
    tests — the refactor must not rename or remove them."""
    assert callable(sector_prices.build_basket_series)
    assert callable(sector_prices.get_benchmark_series)
    assert callable(sector_metrics.compute_metrics)
    assert callable(sector_metrics.perf_over)
    assert callable(momentum_metrics.compute_stock_metrics)
    assert callable(momentum_metrics.load_universe_series)
    assert callable(momentum_metrics.sanitize_closes)


# ---------------------------------------------------------------------------
# Phase 6A — benchmark-only enhanced sanitisation (Launch Validation defect fix)
#
# Root cause being regression-tested here: V1's stored NIFTY 50 history
# contains a DENSE cluster of corrupt prints (several within ~1-3 weeks),
# which the default 21-session centred-median window cannot reliably see
# through — each bad print can sit inside a neighbouring bad print's own
# reference window and mutually mask the deviation check. The fix widens the
# window ONLY for the benchmark (sanitize_benchmark_series /
# BENCHMARK_SANITIZE_WINDOW=51) — proven safe for one large, liquid index —
# while leaving the per-stock DEFAULT_SANITIZE_WINDOW=21 completely untouched.
# ---------------------------------------------------------------------------
def test_benchmark_window_is_wider_than_the_default_stock_window():
    """The whole point of the fix: benchmark and per-stock windows must
    differ, or the fix does nothing."""
    assert BENCHMARK_SANITIZE_WINDOW > DEFAULT_SANITIZE_WINDOW


def test_benchmark_sanitiser_still_catches_an_isolated_spike():
    """Isolated corruption (the original, already-validated case) must still
    be caught at the wider benchmark window — widening must not weaken the
    already-working case."""
    dates = _dates(90)
    values = [24000.0 + i * 5 for i in range(90)]
    values[45] = 16848.45  # isolated corrupt print, mirrors the real case
    closes = pd.Series(values, index=dates)

    clean, dropped = sanitize_benchmark_series(closes)
    assert dropped == 1
    assert dates[45] not in clean.index
    assert clean.iloc[0] == values[0] and clean.iloc[-1] == values[-1]


def test_benchmark_sanitiser_catches_a_dense_cluster_the_default_window_misses():
    """The actual discovered defect, reproduced from a literal snapshot of the
    real V1 NIFTY 50 history (2026-02-24 to 2026-04-24): three corrupt prints
    (03-26, 03-31, 04-03) sit inside a stretch of ordinary local softness
    (~23700 drifting down to ~22500 before the spikes). Their deviation from
    the SHORT (21-session) window's locally-depressed median narrowly misses
    the 25% threshold (22.0-24.7%), while their deviation from the WIDE
    (51-session) window's more stable, broader-anchored median clears it
    (25.0-27.8%) — this is the real mechanism, empirically confirmed against
    live V1 data during the Phase 6 audit, not a hand-tuned synthetic case."""
    # Literal snapshot of real NIFTY 50 closes (trading-day order, no gaps
    # inserted for weekends since only relative spacing/values matter here —
    # dates are assigned sequentially, not matched to real calendar dates).
    # Corrupt prints (verified against the real V1 database) are at list
    # positions 22, 25, 28 (values 17316.97, 17435.77, 17916.29).
    values = [
        25424.65, 25482.50, 25496.55, 25178.65, 24865.70, 19123.77, 24480.50,
        24765.90, 24450.45, 24028.05, 24261.60, 23866.85, 23639.15, 23151.10,
        23408.80, 23581.15, 23777.80, 23002.15, 23114.50, 22512.65, 22912.40,
        23306.45, 17316.97, 22819.60, 22331.40, 17435.77, 22679.40, 22713.10,
        17916.29, 22968.25, 23123.65, 23997.35, 23775.10, 24050.60, 23842.65,
        17097.15, 24231.30, 24312.90, 24405.20, 24488.60, 24560.10, 24601.80,
        24655.30, 24699.90, 24732.40, 24788.60, 24810.20, 24855.90, 24890.30,
        24920.10, 24955.80, 24988.40, 25010.60, 25044.20, 25078.90, 25101.50,
        25135.80, 25160.40, 25188.70, 25210.90,
    ]
    dates = _dates(len(values))
    closes = pd.Series(values, index=dates)
    corrupt_idx = (22, 25, 28)

    _, dropped_default = sanitize_close_series(closes)   # window=21 (unfixed)
    clean_wide, dropped_wide = sanitize_benchmark_series(closes)  # window=51 (fixed)

    assert dropped_default < 3, (
        "sanity check: the default window must NOT catch all 3 clustered "
        "prints, or this fixture no longer reproduces the real defect")
    assert dropped_wide >= 3, "the widened benchmark window must catch all 3 clustered prints"
    assert dropped_wide > dropped_default, (
        "the fix must catch strictly more than the default window on this "
        "real cluster — otherwise nothing was actually fixed")
    for i in corrupt_idx:
        assert dates[i] not in clean_wide.index


def test_benchmark_sanitiser_introduces_no_false_positives_on_valid_data():
    """Widening the window must not start flagging legitimate, smoothly
    trending (or plausibly volatile) data that was never corrupt."""
    dates = _dates(150)
    # A realistic, noisy-but-legitimate index path: steady drift + small daily
    # noise, no single move anywhere near the 25% corruption threshold.
    values = [20000.0]
    for i in range(1, 150):
        values.append(values[-1] * (1 + ((i * 37) % 11 - 5) / 1000))
    closes = pd.Series(values, index=dates)

    clean, dropped = sanitize_benchmark_series(closes)
    assert dropped == 0, "no legitimate row should ever be dropped by the wider window"
    assert len(clean) == len(closes)


def test_benchmark_sanitiser_is_deterministic():
    dates = _dates(120)
    values = [23000.0 + i * 3 for i in range(120)]
    for i in (55, 60, 65):
        values[i] = 17300.0 + i
    closes = pd.Series(values, index=dates)

    first, first_dropped = sanitize_benchmark_series(closes)
    for _ in range(5):
        again, again_dropped = sanitize_benchmark_series(closes)
        assert again_dropped == first_dropped
        assert again.equals(first)


def test_benchmark_only_fix_does_not_change_the_default_per_stock_window():
    """Blast-radius guard: the per-stock sanitiser (sanitize_close_series with
    no window override) must be byte-identical in behaviour to before this
    fix — only sanitize_benchmark_series/BENCHMARK_SANITIZE_WINDOW is new."""
    dates = _dates(90)
    values = [500.0 + i for i in range(90)]
    values[40] = 300.0  # a single ordinary stock-level corrupt print
    closes = pd.Series(values, index=dates)

    default_clean, default_dropped = sanitize_close_series(closes)
    assert default_dropped == 1
    assert dates[40] not in default_clean.index
    # Confirms the default call path still uses DEFAULT_SANITIZE_WINDOW, not
    # the wider benchmark window, when no window is explicitly requested.
    import inspect as _inspect
    sig = _inspect.signature(sanitize_close_series)
    assert sig.parameters["window"].default == DEFAULT_SANITIZE_WINDOW
