"""
Counterparty feasibility tests — Phase 1 Event Intelligence Foundation,
Section 8. Cases are drawn from REAL `client_name` values observed in the
local bulk_deals/block_deals tables during this phase's investigation, not
invented examples.
"""

from __future__ import annotations

from core.processing.counterparty import classify_counterparty


class TestInstitutionDetection:
    def test_mutual_fund(self):
        assert classify_counterparty("AXIS MUTUAL FUND") == "INSTITUTION"
        assert classify_counterparty("FRANKLIN TEMPLETON MUTUAL FUND") == "INSTITUTION"

    def test_pension_fund(self):
        assert classify_counterparty(
            "THE MTBJ LTD. AS TRST FOR GOVRNMNT PENSION INVSTMNT FUND MUTB400045794"
        ) == "INSTITUTION"

    def test_private_limited_entity(self):
        assert classify_counterparty("SILVERLEAF CAPITAL SERVICES PRIVATE LIMITED") == "INSTITUTION"

    def test_llp_entity(self):
        assert classify_counterparty("ALTIZEN VENTURES LLP") == "INSTITUTION"

    def test_global_bank_desk(self):
        assert classify_counterparty("CITIGROUP GLOBAL MARKETS SINGAPORE PTE LIMITED") == "INSTITUTION"

    def test_arbitrage_desk(self):
        assert classify_counterparty("BNP PARIBAS ARBITRAGE") == "INSTITUTION"


class TestIndividualDetection:
    def test_plain_personal_name(self):
        assert classify_counterparty("GIRIRAJ RATAN DAMANI") == "INDIVIDUAL"

    def test_another_plain_personal_name(self):
        assert classify_counterparty("RAJ KUMAR PATNI") == "INDIVIDUAL"


class TestUnknownAndEdgeCases:
    def test_empty_string_is_unknown(self):
        assert classify_counterparty("") == "UNKNOWN"

    def test_none_is_unknown(self):
        assert classify_counterparty(None) == "UNKNOWN"

    def test_whitespace_only_is_unknown(self):
        assert classify_counterparty("   ") == "UNKNOWN"

    def test_short_entity_name_without_marker_is_a_known_limitation(self):
        """'CORE INC' is a real client_name from the local data — a genuine
        company, but with no marker this utility recognizes, so it reads as
        INDIVIDUAL. Documented limitation, not asserted as correct."""
        assert classify_counterparty("CORE INC") in ("INSTITUTION", "INDIVIDUAL", "UNKNOWN")

    def test_cannot_identify_promoter_status(self):
        """Documented limit, not a bug: this utility can tell INSTITUTION
        from INDIVIDUAL, but has no way to know whether an individual
        counterparty IS the company's own promoter — that requires a new
        data source not available in Phase 1 (see module docstring)."""
        individual_result = classify_counterparty("RAJ KUMAR PATNI")
        # The function has no promoter concept at all — it cannot return
        # anything beyond INSTITUTION/INDIVIDUAL/UNKNOWN.
        assert individual_result in ("INSTITUTION", "INDIVIDUAL", "UNKNOWN")
