"""
Corporate-action materiality — Phase 2 Event Materiality.

Ties magnitude extraction (core/processing/magnitude_extractor.py) to a
company-scale denominator and produces a transparent LOW/MEDIUM/HIGH/
TRANSFORMATIONAL/UNKNOWN tier via the general ratio function already built
in Phase 1 (core/processing/materiality.py::compute_ratio_materiality) — no
new tiering logic, no new scoring model, just new inputs feeding the
existing one.

Two categories only, chosen because both the magnitude AND a reliable
denominator exist in already-collected data (see the Phase 2 report's
MATERIALITY COVERAGE section for the exact, measured extraction/coverage
rates — this module does not repeat that audit, it implements what it
concluded):

  Dividend         magnitude = ₹/share (extract_dividend_per_share)
                   denominator = latest price_history close (dividend yield %)
  Large Order Win  magnitude = ₹ crore (extract_order_value_cr, INR only —
                   see below)
                   denominator = trailing 4-quarter revenue from
                   results_quarterly (order value as % of revenue)

Every other event type is deliberately NOT handled here — Phase 1's audit
found no other category with both a reliably extractable magnitude AND a
reliable denominator in current data; inventing one would violate the
"do not force a score" requirement.
"""

from __future__ import annotations

from core.config import CORP_ACTION_MATERIALITY as T
from core.processing.magnitude_extractor import extract_dividend_per_share, extract_order_value_cr
from core.processing.materiality import compute_ratio_materiality

_DIVIDEND_THRESHOLDS = {
    "low_pct": T["dividend_yield_low_pct"],
    "medium_pct": T["dividend_yield_medium_pct"],
    "high_pct": T["dividend_yield_high_pct"],
}
_ORDER_THRESHOLDS = {
    "low_pct": T["large_order_value_low_pct"],
    "medium_pct": T["large_order_value_medium_pct"],
    "high_pct": T["large_order_value_high_pct"],
}


def _unknown(reason: str) -> dict:
    return {
        "magnitude_value": None, "magnitude_unit": None,
        "denominator_value": None, "denominator_type": None,
        "materiality_tier": "UNKNOWN", "materiality_reason": reason,
    }


def compute_dividend_materiality(event_summary: str, latest_close: float | None) -> dict:
    """Dividend yield = (₹/share extracted from text) / (latest close price)."""
    per_share = extract_dividend_per_share(event_summary)
    if per_share is None:
        return _unknown("No per-share amount found in the announcement text — "
                        "materiality is UNKNOWN rather than guessed.")
    if latest_close is None or latest_close <= 0:
        return {
            "magnitude_value": per_share, "magnitude_unit": "PER_SHARE_INR",
            "denominator_value": None, "denominator_type": None,
            "materiality_tier": "UNKNOWN",
            "materiality_reason": (f"Per-share amount ₹{per_share:g} extracted, but no "
                                   "price_history close is available for this symbol to "
                                   "compute a yield."),
        }

    result = compute_ratio_materiality(per_share, latest_close, "share price", _DIVIDEND_THRESHOLDS)
    yield_pct = per_share / latest_close * 100
    reason = (f"Dividend yield {yield_pct:.2f}% (₹{per_share:g}/share vs. ₹{latest_close:g} "
             f"close) -> {result['materiality_tier']}")
    return {
        "magnitude_value": per_share, "magnitude_unit": "PER_SHARE_INR",
        "denominator_value": latest_close, "denominator_type": "latest_close",
        "materiality_tier": result["materiality_tier"],
        "materiality_reason": reason,
    }


def compute_large_order_materiality(event_summary: str,
                                    trailing_revenue_cr: float | None) -> dict:
    """Order value (₹ crore) / trailing 4-quarter revenue (₹ crore)."""
    value, currency = extract_order_value_cr(event_summary)
    if value is None:
        return _unknown("No order value found in the announcement text — "
                        "materiality is UNKNOWN rather than guessed.")
    if currency == "USD":
        return {
            "magnitude_value": value, "magnitude_unit": "USD_MN",
            "denominator_value": None, "denominator_type": None,
            "materiality_tier": "UNKNOWN",
            "materiality_reason": (f"Order value ${value:g}M extracted, but is USD-denominated "
                                   "with no INR equivalent stated in the text — currency "
                                   "conversion is not implemented this phase (no FX rate "
                                   "source has been introduced), so materiality is UNKNOWN "
                                   "rather than an invented conversion."),
        }
    if trailing_revenue_cr is None or trailing_revenue_cr <= 0:
        return {
            "magnitude_value": value, "magnitude_unit": "INR_CR",
            "denominator_value": None, "denominator_type": None,
            "materiality_tier": "UNKNOWN",
            "materiality_reason": (f"Order value ₹{value:g} Cr extracted, but no trailing "
                                   "revenue is available (results_quarterly has no rows for "
                                   "this symbol) to compute a ratio."),
        }

    result = compute_ratio_materiality(value, trailing_revenue_cr, "trailing revenue",
                                       _ORDER_THRESHOLDS)
    return {
        "magnitude_value": value, "magnitude_unit": "INR_CR",
        "denominator_value": trailing_revenue_cr, "denominator_type": "trailing_4q_revenue",
        "materiality_tier": result["materiality_tier"],
        "materiality_reason": result["materiality_reason"],
    }
