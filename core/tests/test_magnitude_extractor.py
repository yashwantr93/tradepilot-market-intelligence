"""
Magnitude extraction tests — Phase 2 Event Materiality.

Every case here is a REAL stored `corporate_actions.event_summary` value
(verbatim), captured during this phase's audit of the local database — not
invented text. See magnitude_extractor.py's docstring for the measured
extraction rates (332/337 Dividend, 6/17 + 1/17 Large Order Win).
"""

from __future__ import annotations

from core.processing.magnitude_extractor import extract_dividend_per_share, extract_order_value_cr


class TestDividendExtraction:
    def test_simple_rupee_amount(self):
        assert extract_dividend_per_share("Dividend - Rs 5 Per Share") == 5.0

    def test_decimal_amount(self):
        assert extract_dividend_per_share("Dividend - Rs 9.14 Per Share") == 9.14

    def test_re_singular(self):
        assert extract_dividend_per_share("Dividend - Re 0.05 Per Share") == 0.05

    def test_truncated_per_share_still_matches(self):
        """The 300-char event_summary truncation sometimes cuts 'Per Share'
        down to 'Per Sh' — must still extract."""
        assert extract_dividend_per_share("Dividend - Rs 33 Per Sh") == 33.0

    def test_combined_special_dividend_takes_first_figure(self):
        text = "Dividend - Rs 14 Per Share/Special Dividend - Rs 6 Per Share"
        assert extract_dividend_per_share(text) == 14.0

    def test_invit_per_unit_distribution(self):
        text = ("Distribution - Rs 6.31 Per Unit Consisting Of Re 0.37 Per Unit As "
               "Interest/ Re 0.80 Per Unit As Dividend/ Rs 5.14 Per Unit As Repayment")
        assert extract_dividend_per_share(text) == 6.31

    def test_no_amount_returns_none(self):
        text = ("Updates The India Cements Limited has informed the Exchange regarding "
               "'Letter To Shareholder - Transfer Of Dividend And Corresponding Shares'")
        assert extract_dividend_per_share(text) is None

    def test_record_date_notice_without_amount_returns_none(self):
        text = ("Record Date International Conveyors Limited has informed the Exchange "
               "that Record date for the purpose of Dividend is 17-Sep-2026.")
        assert extract_dividend_per_share(text) is None

    def test_empty_and_none(self):
        assert extract_dividend_per_share("") is None
        assert extract_dividend_per_share(None) is None


class TestOrderValueExtraction:
    def test_direct_crore_figure(self):
        value, currency = extract_order_value_cr("Bagging/Receiving of orders - bags order worth Rs 15000 Cr")
        assert value == 15000.0
        assert currency == "INR"

    def test_html_entity_rupee_symbol(self):
        text = ('Interarch Building Solutions Strengthens Order Book with '
               '&#8377;375 Crores of New Orders in June 2026')
        value, currency = extract_order_value_cr(text)
        assert value == 375.0
        assert currency == "INR"

    def test_prefers_inr_equivalent_over_usd_headline(self):
        """HFCL: USD figure appears first in the text, but the INR
        equivalent is explicitly stated — must prefer the INR figure."""
        text = ("HFCL Limited has informed the Exchange about bagging an export order "
               "of USD 46.13 million approx. (equivalent to INR 441.53 crore approx.) "
               "for supply of Optical Fiber Cables")
        value, currency = extract_order_value_cr(text)
        assert currency == "INR"
        assert value == 441.53

    def test_raw_rupee_figure_with_commas_converts_to_crore(self):
        text = ("Viviana Power Tech Limited has informed the Exchange about receiving "
               "new turnkey contract amounting to Rs. 71,38,64,233/- (Rupees Seventy-One "
               "Crore Thirty-Eight Lakhs)")
        value, currency = extract_order_value_cr(text)
        assert currency == "INR"
        assert abs(value - 71.3864233) < 0.001

    def test_usd_only_returns_usd_currency_not_converted(self):
        text = ("L&T Technology Services has secured a landmark engagement valued at "
               "over $75 Million from a leading global technology enterprise.")
        value, currency = extract_order_value_cr(text)
        assert value == 75.0
        assert currency == "USD"

    def test_generic_boilerplate_with_no_number_returns_none(self):
        text = ("Bagging/Receiving of orders/contracts Larsen & Toubro Limited has "
               "informed the Exchange about Bagging/Receiving of orders/contracts")
        value, currency = extract_order_value_cr(text)
        assert value is None
        assert currency is None

    def test_empty_and_none(self):
        assert extract_order_value_cr("") == (None, None)
        assert extract_order_value_cr(None) == (None, None)
