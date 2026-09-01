"""
Results data integrity cleanup tests — Phase 2.5.

Covers seed-signature detection, dry-run safety, surgical (not wholesale)
deletion from results_tracker, and full-clear behavior for
results_quarterly/event_expectations. Same hermetic monkeypatch pattern as
Phase 1.5's backfill tests — the DB-facing repo calls are faked so these
test the actual DECISION logic fast and deterministically.
"""

from __future__ import annotations

import datetime as dt

from core.pipelines.results_data_integrity import run_results_integrity_cleanup


def _row(id_, symbol, period_end, rev_g, prof_g, basis="YoY"):
    return {"id": id_, "symbol": symbol, "period_end": period_end,
            "revenue_growth_pct": rev_g, "profit_growth_pct": prof_g,
            "basis": basis, "source": "yfinance", "created_at": dt.datetime(2026, 6, 23)}


class TestSeedDetection:
    def test_exact_seed_signature_is_flagged(self, monkeypatch):
        rows = [_row(1, "ABB", dt.date(2026, 3, 31), 18.0, 33.33)]
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".get_results_tracker_all", lambda: rows)
        report = run_results_integrity_cleanup(dry_run=True)
        assert report["results_tracker_seed_rows_identified"] == 1
        assert report["results_tracker_seed_row_ids"] == [1]

    def test_real_row_is_never_flagged(self, monkeypatch):
        rows = [_row(1, "ABB", dt.date(2026, 6, 30), 17.75, -23.67)]
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".get_results_tracker_all", lambda: rows)
        report = run_results_integrity_cleanup(dry_run=True)
        assert report["results_tracker_seed_rows_identified"] == 0

    def test_qoq_row_is_never_flagged_even_if_values_coincide(self):
        """basis must also be YoY — a QoQ row is never eligible, regardless
        of its numbers, since the seed signature is specifically a YoY
        artifact."""
        rows = [_row(1, "X", dt.date(2026, 3, 31), 18.0, 33.33, basis="QoQ")]
        import core.pipelines.results_data_integrity as mod
        assert mod._is_seed_row(rows[0]) is False

    def test_close_but_not_exact_values_are_not_flagged(self):
        """18.01 (not 18.0) must not match — the detection is deliberately
        exact, not a fuzzy/rounded comparison, to avoid false positives on
        real data that merely resembles the signature."""
        import core.pipelines.results_data_integrity as mod
        row = _row(1, "X", dt.date(2026, 3, 31), 18.01, 33.33)
        assert mod._is_seed_row(row) is False


class TestDryRunSafety:
    def test_dry_run_never_deletes(self, monkeypatch):
        rows = [_row(1, "ABB", dt.date(2026, 3, 31), 18.0, 33.33)]
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".get_results_tracker_all", lambda: rows)
        delete_calls = []
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".delete_results_tracker_rows",
                            lambda ids: delete_calls.append(ids) or len(ids))
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".truncate_results_quarterly", lambda: (_ for _ in ()).throw(
                                AssertionError("must not be called in dry_run")))
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".truncate_event_expectations", lambda: (_ for _ in ()).throw(
                                AssertionError("must not be called in dry_run")))

        report = run_results_integrity_cleanup(dry_run=True)

        assert delete_calls == []
        assert "results_tracker_rows_deleted" not in report

    def test_real_run_deletes_exactly_the_identified_ids(self, monkeypatch):
        rows = [
            _row(1, "ABB", dt.date(2026, 3, 31), 18.0, 33.33),   # seed
            _row(2, "ABB", dt.date(2026, 6, 30), 17.75, -23.67),  # real — must survive
            _row(3, "TCS", dt.date(2026, 3, 31), 18.0, 33.33),   # seed
        ]
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".get_results_tracker_all", lambda: rows)
        captured = {}
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".delete_results_tracker_rows",
                            lambda ids: captured.setdefault("ids", ids) and len(ids))
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".truncate_results_quarterly", lambda: 285)
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".truncate_event_expectations", lambda: 114)

        report = run_results_integrity_cleanup(dry_run=False)

        assert sorted(captured["ids"]) == [1, 3]
        assert 2 not in captured["ids"]  # ABB's real row is never touched
        assert report["results_tracker_rows_deleted"] == 2
        assert report["results_quarterly_rows_cleared"] == 285
        assert report["event_expectations_rows_cleared"] == 114


class TestReportCompleteness:
    def test_seed_only_symbol_is_flagged_as_left_with_zero_rows(self, monkeypatch):
        """A symbol whose ONLY row is the seed row must be reported as
        ending up with zero results_tracker rows — surfaced, not hidden."""
        rows = [_row(1, "SEEDONLY", dt.date(2026, 3, 31), 18.0, 33.33)]
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".get_results_tracker_all", lambda: rows)
        report = run_results_integrity_cleanup(dry_run=True)
        assert "SEEDONLY" in report["symbols_left_with_zero_results_tracker_rows"]

    def test_symbol_with_a_real_row_is_not_flagged(self, monkeypatch):
        rows = [
            _row(1, "ABB", dt.date(2026, 3, 31), 18.0, 33.33),
            _row(2, "ABB", dt.date(2026, 6, 30), 17.75, -23.67),
        ]
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".get_results_tracker_all", lambda: rows)
        report = run_results_integrity_cleanup(dry_run=True)
        assert "ABB" not in report["symbols_left_with_zero_results_tracker_rows"]

    def test_no_seed_rows_at_all_is_a_clean_no_op_report(self, monkeypatch):
        rows = [_row(1, "ABB", dt.date(2026, 6, 30), 17.75, -23.67)]
        monkeypatch.setattr("core.pipelines.results_data_integrity.repo"
                            ".get_results_tracker_all", lambda: rows)
        report = run_results_integrity_cleanup(dry_run=True)
        assert report["results_tracker_seed_rows_identified"] == 0
        assert report["symbols_left_with_zero_results_tracker_rows"] == []
