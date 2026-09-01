"""
Event classifier tests — Phase 1 Event Intelligence Foundation.

Covers positive/negative/neutral-ambiguous/unknown events, the ESOP
regression (root-caused this phase against real stored announcement text —
see core/config.py's EVENT_TYPE_RULES comment), the Warning-Letter/keyword-
overlap regression, and direction validity. These validate BUSINESS
behavior (what type + direction a real announcement text should produce),
not the keyword-matching implementation itself.
"""

from __future__ import annotations

from core.config import EVENT_DIRECTIONS, EVENT_IMPACT
from core.processing.event_classifier import classify_event


class TestPositiveEvents:
    def test_buyback_is_bullish(self):
        et, impact, pri = classify_event("Board approves buyback of equity shares")
        assert et == "Buyback"
        assert impact == "Bullish"

    def test_large_order_win_is_bullish(self):
        et, impact, pri = classify_event(
            "Company has received order win from a major client for Rs 500 crore"
        )
        assert et == "Large Order Win"
        assert impact == "Bullish"

    def test_genuine_regulatory_approval_stays_bullish(self):
        et, impact, pri = classify_event("Received approval from USFDA for new drug")
        assert et == "Regulatory Approval"
        assert impact == "Bullish"

    def test_credit_rating_upgrade_is_bullish(self):
        et, impact, pri = classify_event("CRISIL has upgraded the rating to AA+")
        assert et == "Credit Rating Upgrade"
        assert impact == "Bullish"


class TestNegativeEvents:
    def test_order_cancellation_is_bearish(self):
        et, impact, pri = classify_event("Company received cancellation of order from client")
        assert et == "Order Cancellation"
        assert impact == "Bearish"

    def test_sebi_action_is_bearish(self):
        et, impact, pri = classify_event("SEBI order passed against the company for violation")
        assert et == "Regulatory / Legal Action"
        assert impact == "Bearish"

    def test_auditor_resignation_is_bearish(self):
        et, impact, pri = classify_event(
            "Company informs resignation of statutory auditor with immediate effect"
        )
        assert et == "Auditor Resignation"
        assert impact == "Bearish"

    def test_credit_rating_downgrade_is_bearish(self):
        et, impact, pri = classify_event("ICRA has downgraded the rating to BBB-")
        assert et == "Credit Rating Downgrade"
        assert impact == "Bearish"

    def test_debt_default_is_bearish(self):
        et, impact, pri = classify_event("Company reports default in payment of interest")
        assert et == "Debt Default"
        assert impact == "Bearish"

    def test_plant_fire_is_bearish(self):
        et, impact, pri = classify_event("Fire at the company's manufacturing plant")
        assert et == "Operations Disruption"
        assert impact == "Bearish"

    def test_product_recall_is_bearish(self):
        et, impact, pri = classify_event("Company announces voluntary recall of product batch")
        assert et == "Product Recall"
        assert impact == "Bearish"


class TestNeutralAmbiguousEvents:
    def test_dividend_is_neutral(self):
        et, impact, pri = classify_event("Board recommends final dividend of Rs 5 per share")
        assert et == "Dividend"
        assert impact == "Neutral"

    def test_esop_grant_is_neutral_not_regulatory_approval(self):
        """The ESOP-misclassification regression, root-cause fixed this phase."""
        et, impact, pri = classify_event(
            "ESOP/ESOS/ESPS K.P. Energy Limited has informed the Exchange "
            "regarding Grant of 76000 Options."
        )
        assert et == "Employee Stock Options"
        assert impact == "Neutral"

    def test_stock_option_grant_variant_is_neutral(self):
        et, impact, pri = classify_event(
            "Options to purchase securities Indus Towers Limited has informed "
            "the Exchange regarding grant of stock options"
        )
        assert et == "Employee Stock Options"

    def test_mna_is_ambiguous_not_bullish(self):
        """Acquirer vs. target collapse into one keyword rule — direction is
        genuinely unknown from text alone, must not default to Bullish."""
        et, impact, pri = classify_event("Company announces merger with XYZ Ltd")
        assert et == "Mergers & Acquisitions"
        assert impact == "Ambiguous"

    def test_generic_management_change_is_ambiguous(self):
        et, impact, pri = classify_event("Appointment of new Independent Director")
        assert et == "Management Change"
        assert impact == "Ambiguous"


class TestKeywordOverlapRegression:
    def test_fda_warning_letter_is_bearish_not_approval(self):
        """The second real classification bug found this phase: adverse FDA
        text was matching Regulatory Approval's 'usfda'/'us fda' keyword."""
        et, impact, pri = classify_event(
            "Aurobindo Pharma Limited has informed the Exchange that Unit I "
            "of Eugia Pharma Specialities Ltd., received a Warning Letter "
            "from US FDA"
        )
        assert et == "Regulatory / Legal Action"
        assert impact == "Bearish"

    def test_cfo_resignation_stays_management_change_not_auditor(self):
        """A CFO resignation must not be conflated with an auditor
        resignation — they are different governance signals."""
        et, impact, pri = classify_event("Resignation of Chief Financial Officer")
        assert et == "Management Change"
        assert et != "Auditor Resignation"


class TestUnknownEvents:
    def test_untracked_text_returns_none(self):
        et, impact, pri = classify_event("Newspaper publication of financial results extract")
        assert et is None
        assert impact is None
        assert pri is None

    def test_empty_text_returns_none(self):
        et, impact, pri = classify_event("")
        assert et is None

    def test_none_text_returns_none(self):
        et, impact, pri = classify_event(None)
        assert et is None


class TestDirectionValidity:
    def test_every_event_impact_value_is_a_valid_direction(self):
        for event_type, impact in EVENT_IMPACT.items():
            assert impact in EVENT_DIRECTIONS, (
                f"{event_type!r} has impact {impact!r}, not in {EVENT_DIRECTIONS}"
            )

    def test_negative_vocabulary_is_no_longer_near_absent(self):
        """Phase 1 requirement: negative direction must be genuinely
        represented, not just Rights Issue as the sole Bearish type."""
        bearish_types = [t for t, i in EVENT_IMPACT.items() if i == "Bearish"]
        assert len(bearish_types) >= 8, (
            f"expected meaningful negative-vocabulary coverage, got {bearish_types}"
        )
