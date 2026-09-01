"""
Results data integrity cleanup — Phase 2.5.

A ONE-TIME historical remediation, not a permanent runtime filter. Going
forward, `results_pipeline.py` tags every row with real provenance
(`yfinance_live` vs `yfinance_offline_seed`) so this detective work never
needs to happen again — see that module's `_SOURCE_TAG`. This module exists
only to clean up the 57 rows written BEFORE that fix existed, when every row
was indistinguishably tagged "yfinance" regardless of origin.

Detection heuristic (documented, not hidden): a results_tracker row is
treated as offline-seed contamination if it matches the offline
`ResultsConnector._seed()` fixture's EXACT, mathematically deterministic
growth signature — revenue_growth_pct == 18.0 AND profit_growth_pct == 33.33
AND basis == "YoY". This signature is independent of company size and comes
from the seed's fixed growth RATIOS (revenue x1.18, net income x0.20 latest
vs x0.15 four quarters back — see results_connector.py), not from any
per-symbol random value — so it does not occur by chance in real data, and
it was cross-validated during this phase's audit against `created_at`
clustering (54 of 57 matches share one calendar day, 2026-06-23; the
remaining 3 were traced to this session's own earlier offline test runs).

results_quarterly and event_expectations are NOT surgically filtered — see
repository.py's `truncate_results_quarterly()`/`truncate_event_expectations()`
docstrings for why a full clear is safe for those two specifically (100%
offline-origin content, confirmed by process history, not by a signature
heuristic).
"""

from __future__ import annotations

from core.db import repository as repo

_SEED_REVENUE_GROWTH = 18.0
_SEED_PROFIT_GROWTH = 33.33


def _is_seed_row(row: dict) -> bool:
    return (row["basis"] == "YoY"
            and row["revenue_growth_pct"] == _SEED_REVENUE_GROWTH
            and row["profit_growth_pct"] == _SEED_PROFIT_GROWTH)


def run_results_integrity_cleanup(dry_run: bool = True) -> dict:
    """Audit (and, if dry_run=False, apply) the results_tracker cleanup plus
    a full clear of results_quarterly/event_expectations. Always returns a
    complete report; only mutates the DB when dry_run is explicitly False."""
    all_rows = repo.get_results_tracker_all()
    seed_rows = [r for r in all_rows if _is_seed_row(r)]
    seed_ids = [r["id"] for r in seed_rows]

    by_symbol_after: dict[str, int] = {}
    for r in all_rows:
        if r["id"] in seed_ids:
            continue
        by_symbol_after[r["symbol"]] = by_symbol_after.get(r["symbol"], 0) + 1
    symbols_left_with_zero_rows = sorted(
        {r["symbol"] for r in all_rows} - set(by_symbol_after)
    )

    report = {
        "dry_run": dry_run,
        "results_tracker_total_rows": len(all_rows),
        "results_tracker_seed_rows_identified": len(seed_rows),
        "results_tracker_seed_row_ids": seed_ids,
        "affected_symbols": sorted({r["symbol"] for r in seed_rows}),
        "symbols_left_with_zero_results_tracker_rows": symbols_left_with_zero_rows,
    }

    if not dry_run:
        deleted = repo.delete_results_tracker_rows(seed_ids)
        cleared_quarterly = repo.truncate_results_quarterly()
        cleared_expectations = repo.truncate_event_expectations()
        report.update({
            "results_tracker_rows_deleted": deleted,
            "results_quarterly_rows_cleared": cleared_quarterly,
            "event_expectations_rows_cleared": cleared_expectations,
        })

    return report
