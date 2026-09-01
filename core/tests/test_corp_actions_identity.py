"""
Event identity / deduplication / backfill tests — Phase 1.5 Event Data
Integrity & Backfill Decision.

Covers: the new event_type-free dedupe identity, repeated-ingestion
idempotency, corrected-classification-updates-in-place (never a duplicate
row), provenance preservation, the newly-unclassified edge case, and
dry-run safety (no writes unless dry_run=False is explicit).

The backfill's DB-facing calls (`repo.get_corporate_actions_for_backfill` /
`repo.apply_corporate_action_corrections`) are monkeypatched with an
in-memory fake store rather than hitting the real database — this tests the
actual correction DECISION logic (what should change, what shouldn't, what
gets stamped) hermetically and fast, the same "test business behavior, not
the DB plumbing" principle used in Phase 1's tests.
"""

from __future__ import annotations

import datetime as dt

import pytest

from core.pipelines.corp_actions_backfill import REASON, run_corp_actions_backfill
from core.pipelines.corp_actions_pipeline import dedupe_hash


class TestDedupeIdentity:
    """Section 1/6: does event identity depend on event_type? It must not."""

    def test_hash_does_not_depend_on_event_type(self):
        """The whole point of the Phase 1.5 fix: the SAME real-world
        announcement must hash identically regardless of how it's
        classified — dedupe_hash() no longer even takes event_type."""
        h1 = dedupe_hash("INFY", dt.date(2026, 1, 1), "Some announcement text")
        h2 = dedupe_hash("INFY", dt.date(2026, 1, 1), "Some announcement text")
        assert h1 == h2

    def test_hash_changes_with_symbol(self):
        h1 = dedupe_hash("INFY", dt.date(2026, 1, 1), "Some text")
        h2 = dedupe_hash("TCS", dt.date(2026, 1, 1), "Some text")
        assert h1 != h2

    def test_hash_changes_with_date(self):
        h1 = dedupe_hash("INFY", dt.date(2026, 1, 1), "Some text")
        h2 = dedupe_hash("INFY", dt.date(2026, 1, 2), "Some text")
        assert h1 != h2

    def test_hash_changes_with_summary(self):
        h1 = dedupe_hash("INFY", dt.date(2026, 1, 1), "Text A")
        h2 = dedupe_hash("INFY", dt.date(2026, 1, 1), "Text B")
        assert h1 != h2

    def test_repeated_ingestion_of_same_announcement_is_stable_across_reclassification(self):
        """The core regression this phase fixes: re-classifying the SAME
        announcement text must not change its identity."""
        symbol, date, summary = "KPENERGY", dt.date(2026, 8, 1), "ESOP/ESOS/ESPS grant of options"
        hash_before_fix = dedupe_hash(symbol, date, summary)   # today's (post-fix) function
        # Simulate what the OLD (pre-1.5) formula would have produced for two
        # different classifications of the identical text:
        import hashlib
        old_hash_esop = hashlib.sha1(
            f"{symbol}|{date}|Employee Stock Options|{summary[:80]}".encode()
        ).hexdigest()
        old_hash_reg_approval = hashlib.sha1(
            f"{symbol}|{date}|Regulatory Approval|{summary[:80]}".encode()
        ).hexdigest()
        assert old_hash_esop != old_hash_reg_approval  # the OLD bug: two different hashes
        # The NEW function produces ONE stable hash regardless of classification,
        # and it differs from BOTH old (event_type-including) hashes:
        assert hash_before_fix not in (old_hash_esop, old_hash_reg_approval)
        assert dedupe_hash(symbol, date, summary) == hash_before_fix


def _fake_row(id_, symbol="KPENERGY", date=dt.date(2026, 1, 1), summary="",
              event_type="Regulatory Approval", impact_tag="Bullish", priority="High",
              old_hash="stale-hash"):
    return {"id": id_, "symbol": symbol, "announcement_date": date,
            "event_summary": summary, "event_type": event_type,
            "impact_tag": impact_tag, "priority": priority, "dedupe_hash": old_hash}


class TestBackfillDecisionLogic:
    def test_dry_run_never_writes(self, monkeypatch):
        rows = [_fake_row(1, summary="ESOP/ESOS/ESPS grant of options")]
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".get_corporate_actions_for_backfill", lambda: rows)
        write_calls = []
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".apply_corporate_action_corrections",
                            lambda updates: write_calls.append(updates) or len(updates))

        report = run_corp_actions_backfill(dry_run=True)

        assert report["dry_run"] is True
        assert write_calls == []  # no write call made at all
        assert "rows_written" not in report
        assert report["classification_corrections"] == 1

    def test_real_run_writes_exactly_once(self, monkeypatch):
        rows = [_fake_row(1, summary="ESOP/ESOS/ESPS grant of options")]
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".get_corporate_actions_for_backfill", lambda: rows)
        write_calls = []
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".apply_corporate_action_corrections",
                            lambda updates: write_calls.append(updates) or len(updates))

        report = run_corp_actions_backfill(dry_run=False)

        assert len(write_calls) == 1
        assert report["rows_written"] == 1

    def test_correct_classification_updates_in_place_not_duplicated(self, monkeypatch):
        """The row's id must be reused — never a second row for the same event."""
        rows = [_fake_row(42, summary="ESOP/ESOS/ESPS grant of options")]
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".get_corporate_actions_for_backfill", lambda: rows)
        captured = {}
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".apply_corporate_action_corrections",
                            lambda updates: captured.setdefault("updates", updates) and len(updates))

        run_corp_actions_backfill(dry_run=False)

        assert len(captured["updates"]) == 1
        assert captured["updates"][0]["id"] == 42  # same row, updated — not a new row
        assert captured["updates"][0]["event_type"] == "Employee Stock Options"

    def test_provenance_is_preserved_on_correction(self, monkeypatch):
        rows = [_fake_row(1, summary="ESOP/ESOS/ESPS grant of options",
                          event_type="Regulatory Approval", impact_tag="Bullish")]
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".get_corporate_actions_for_backfill", lambda: rows)
        captured = {}
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".apply_corporate_action_corrections",
                            lambda updates: captured.setdefault("updates", updates) and len(updates))

        run_corp_actions_backfill(dry_run=False)

        update = captured["updates"][0]
        assert update["original_event_type"] == "Regulatory Approval"
        assert update["original_impact_tag"] == "Bullish"
        assert update["reclassification_reason"] == REASON
        assert isinstance(update["reclassified_at"], dt.datetime)

    def test_unchanged_classification_is_never_touched_for_classification_fields(self, monkeypatch):
        """A row whose classification is already correct under current
        rules must not get a reclassification stamp — only its hash (if the
        hash formula itself changed) may be updated."""
        rows = [_fake_row(1, summary="Received approval from USFDA for new drug",
                          event_type="Regulatory Approval", impact_tag="Bullish",
                          priority="High")]
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".get_corporate_actions_for_backfill", lambda: rows)
        captured = {}
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".apply_corporate_action_corrections",
                            lambda updates: captured.setdefault("updates", updates) and len(updates))

        report = run_corp_actions_backfill(dry_run=False)

        assert report["classification_corrections"] == 0
        # Only the dedupe_hash may have been touched (formula changed in
        # Phase 1.5), never original_event_type/reclassification_reason.
        for u in captured["updates"]:
            assert "original_event_type" not in u
            assert "reclassification_reason" not in u

    def test_newly_unclassified_is_flagged_not_silently_nulled(self, monkeypatch):
        """A row whose text no longer matches ANY rule must not have its
        event_type/impact_tag/priority overwritten with None — those columns
        are NOT NULL — it's flagged for manual review instead."""
        rows = [_fake_row(1, summary="completely untracked noise text with no keyword match",
                          event_type="Dividend", impact_tag="Neutral", priority="Low")]
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".get_corporate_actions_for_backfill", lambda: rows)
        captured = {}
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".apply_corporate_action_corrections",
                            lambda updates: captured.setdefault("updates", updates) and len(updates))

        report = run_corp_actions_backfill(dry_run=False)

        assert len(report["newly_unclassified_under_current_rules"]) == 1
        assert report["classification_corrections"] == 0
        for u in captured.get("updates", []):
            # event_type must be ABSENT from the update entirely (the row's
            # existing value is left untouched) — never explicitly set to None.
            assert "event_type" not in u

    def test_hash_only_update_when_classification_unchanged_but_formula_changed(self, monkeypatch):
        rows = [_fake_row(1, summary="Dividend - Rs 5 Per Share", event_type="Dividend",
                          impact_tag="Neutral", priority="Low", old_hash="old-formula-hash")]
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".get_corporate_actions_for_backfill", lambda: rows)
        captured = {}
        monkeypatch.setattr("core.pipelines.corp_actions_backfill.repo"
                            ".apply_corporate_action_corrections",
                            lambda updates: captured.setdefault("updates", updates) and len(updates))

        report = run_corp_actions_backfill(dry_run=False)

        assert report["hash_only_updates"] == 1
        assert captured["updates"][0]["dedupe_hash"] != "old-formula-hash"
