"""
Counterparty feasibility utility — Phase 1 Event Intelligence Foundation,
Section 8 (Buyer/Seller Feasibility).

FINDING (investigated against real `bulk_deals`/`block_deals.client_name`
values in the local database, not assumed): the stored client_name text is
often self-identifying enough to reliably classify the counterparty into a
coarse INSTITUTION vs INDIVIDUAL category — e.g. "AXIS MUTUAL FUND",
"FRANKLIN TEMPLETON MUTUAL FUND", "CITIGROUP GLOBAL MARKETS SINGAPORE PTE
LIMITED", "THE MTBJ LTD. AS TRST FOR GOVRNMNT PENSION INVSTMNT FUND" all
carry an unambiguous institutional-entity marker; "GIRIRAJ RATAN DAMANI" or
"RAJ KUMAR PATNI" read as individual names with no such marker.

WHAT THIS CANNOT DO: identify a PROMOTER specifically (vs. an unrelated
institution or HNI with a similar-sounding name), or infer TRANSACTION
PURPOSE (accumulation vs. distribution vs. arbitrage/hedging). Neither
`bulk_deals`/`block_deals` nor any other existing table carries a
promoter/insider relationship flag or a purpose field — that would require a
NEW SOURCE (e.g. NSE/BSE shareholding-pattern or SAST disclosures), which
Phase 1 does NOT introduce (no speculative connector, per the brief).

This module is therefore a bounded, honest utility — NOT wired into
core/watchlist/rules.py or any pipeline in Phase 1. `MARQUEE_BUYERS`
(core/config.py) remains the only existing, already-wired identity
mechanism, and it stays dormant (empty by default) exactly as before; this
module does not populate or replace it. See the Phase 1 report's DISCOVERED
section for the full investigation.
"""

from __future__ import annotations

# Substrings that reliably mark an institutional/entity counterparty in the
# real client_name text observed in bulk_deals/block_deals. Deliberately
# conservative — false negatives (an institution read as "Unknown") are
# preferred over false positives.
_INSTITUTION_MARKERS = [
    "mutual fund", "insurance", "pension", "trust", "trst", "llp",
    "private limited", "pvt ltd", "pvt. ltd", "limited", "ltd.", "ltd",
    "capital", "fund", "asset management", "arbitrage", "securities",
    "advisory", "investments", "investment", "bank", "ag", "plc",
    "corporation", "corp", "global markets", "warehousing", "enterprises",
]


def classify_counterparty(client_name: str) -> str:
    """Coarse INSTITUTION / INDIVIDUAL / UNKNOWN classification.

    NOT a promoter or purpose classifier — see module docstring for the
    documented limits of what this can and cannot determine.
    """
    if not client_name or not client_name.strip():
        return "UNKNOWN"
    name = client_name.strip().lower()

    if any(marker in name for marker in _INSTITUTION_MARKERS):
        return "INSTITUTION"

    # A plain multi-word name with no institutional marker and no digits
    # reads as an individual (HNI) counterparty.
    words = name.split()
    if 2 <= len(words) <= 5 and not any(ch.isdigit() for ch in name):
        return "INDIVIDUAL"

    return "UNKNOWN"
