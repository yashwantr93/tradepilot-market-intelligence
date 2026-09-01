"""
Magnitude extraction — Phase 2 Event Materiality.

Rule-based regex extraction of a numeric magnitude from free-text corporate
announcements. No ML, no NLP model — plain, transparent, testable patterns,
each one designed and measured against the REAL stored `corporate_actions`
text (not invented examples) during this phase's audit.

Two extractors are provided, one per category currently wired into
materiality (see core/processing/corp_action_materiality.py):

  extract_dividend_per_share() — measured 332/337 (98.5%) real Dividend rows
  extract_order_value_cr()     — measured 6/17 (35%) real Large Order Win
                                  rows with an INR figure, +1/17 (6%) with a
                                  USD-only figure (not converted — see below)

Both return None (or (None, None)) rather than guessing when no pattern
matches — the remaining rows are genuinely textual/procedural announcements
with no number in the source text at all (verified by manual reading during
this phase's audit, not assumed).
"""

from __future__ import annotations

import re

_INR_MARK = r"(?:rs\.?|re\.?|inr|₹|&#8377;)"

# --- Dividend / distribution per-share (or per-unit, for REIT/InvIT
# distributions) amount. Handles the 300-char event_summary truncation
# occasionally cutting "Per Share" down to "Per Sh".
_DIVIDEND_PATTERN = re.compile(
    _INR_MARK + r"\s*([0-9]+(?:\.[0-9]+)?)\s*per\s*(?:sh|unit)", re.IGNORECASE
)

# --- Order value, INR-denominated, in decreasing preference order:
#   1. an explicit "equivalent to INR X crore" phrase (present alongside a
#      USD headline figure — prefer the INR figure when both exist)
#   2. a direct "Rs/INR/₹/&#8377; X crore(s)" phrase
#   3. a raw rupee figure with comma grouping and a "/-" suffix (e.g.
#      "Rs. 71,38,64,233/-"), converted from rupees to crore (÷ 1e7)
#   4. a "Rs/INR/₹ X lakh(s)" phrase, converted to crore (÷ 100)
_INR_EQUIVALENT = re.compile(
    r"equivalent to\s*(?:inr|rs\.?|₹|&#8377;)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:crores?|cr\b)",
    re.IGNORECASE,
)
_INR_CRORE_DIRECT = re.compile(
    _INR_MARK + r"\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:crores?|cr\b)", re.IGNORECASE
)
_INR_RAW_RUPEE = re.compile(
    _INR_MARK + r"\s*([0-9]{2,3}(?:,[0-9]{2,3})+)\s*/-", re.IGNORECASE
)
_INR_LAKH = re.compile(
    _INR_MARK + r"\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*lakhs?", re.IGNORECASE
)
_USD_MILLION = re.compile(
    r"(?:usd|\$)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:million|mn)", re.IGNORECASE
)


def extract_dividend_per_share(text: str) -> float | None:
    """₹-per-share (or per-unit) amount, or None if the text carries no
    extractable figure (e.g. a record-date notice with no amount stated)."""
    if not text:
        return None
    m = _DIVIDEND_PATTERN.search(text)
    return float(m.group(1)) if m else None


def extract_order_value_cr(text: str) -> tuple[float | None, str | None]:
    """(value, currency) where currency is "INR" (value already in ₹ crore)
    or "USD" (value in $ million, NOT converted — see module docstring and
    core/processing/corp_action_materiality.py for why). (None, None) when
    no pattern matches at all."""
    if not text:
        return None, None
    m = _INR_EQUIVALENT.search(text)
    if m:
        return float(m.group(1).replace(",", "")), "INR"
    m = _INR_CRORE_DIRECT.search(text)
    if m:
        return float(m.group(1).replace(",", "")), "INR"
    m = _INR_RAW_RUPEE.search(text)
    if m:
        return float(m.group(1).replace(",", "")) / 1e7, "INR"
    m = _INR_LAKH.search(text)
    if m:
        return float(m.group(1).replace(",", "")) / 100.0, "INR"
    m = _USD_MILLION.search(text)
    if m:
        return float(m.group(1).replace(",", "")), "USD"
    return None, None
