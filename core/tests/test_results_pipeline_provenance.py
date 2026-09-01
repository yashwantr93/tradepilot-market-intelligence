"""
Results pipeline provenance test — Phase 2.5.

Confirms the root-cause fix: results rows are no longer tagged with a
single indistinguishable "yfinance" source regardless of origin — the tag
now reflects core.config.OFFLINE_MODE at the time of the run.
"""

from __future__ import annotations

from core.config import OFFLINE_MODE
from core.pipelines.results_pipeline import _SOURCE_TAG


def test_source_tag_reflects_offline_mode():
    if OFFLINE_MODE:
        assert _SOURCE_TAG == "yfinance_offline_seed"
    else:
        assert _SOURCE_TAG == "yfinance_live"


def test_source_tag_is_never_the_old_ambiguous_value():
    """The old bug: every row said just 'yfinance', live or not — that
    exact ambiguous value must never be produced again."""
    assert _SOURCE_TAG != "yfinance"
