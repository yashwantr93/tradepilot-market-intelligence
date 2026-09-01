"""
Technical Confirmation bridge — Phase 5.

Reads V2's existing Early Momentum / Bearish Opportunity classification for
a symbol via `intelligence_v2.contracts` — NO new technical calculation.
Deliberately lives in `event_intelligence/`, not `core/db/repository.py`:
importing `intelligence_v2` from inside `core/` would violate CLAUDE.md's
V1/V2 isolation rule (see `event_intelligence/__init__.py`).

This module does not decide LONG/SHORT — it only reports what the existing,
unchanged V2 engines already concluded, translated into the CONFIRMED/
PARTIAL/NOT_CONFIRMED/UNKNOWN vocabulary the signal engine uses for every
evidence dimension.
"""

from __future__ import annotations

from intelligence_v2.contracts import bearish_opportunity, early_momentum

# Early Momentum's own category order (config/early_momentum.py), strongest first.
_LONG_CONFIRMED = {"Emerging Leader"}
_LONG_PARTIAL = {"Building Momentum", "Watch Closely"}
# Bearish Opportunity's own category order (config/bearish_opportunity.py), strongest first.
_SHORT_CONFIRMED = {"High Conviction Bearish"}
_SHORT_PARTIAL = {"Building Weakness", "Watch for Breakdown"}


def _latest_category(history) -> str | None:
    if history is None or history.empty:
        return None
    latest = history.sort_values("trade_date").iloc[-1]
    return latest.get("category")


def get_technical_confirmation(symbol: str, side: str) -> dict:
    """side: "long" or "short". Returns
    {"status": CONFIRMED/PARTIAL/NOT_CONFIRMED/UNKNOWN, "category": str|None,
     "reason": str}. UNKNOWN when V2 has no history for this symbol at all
    (e.g. outside V2's tracked universe) — never guessed."""
    if side == "long":
        history = early_momentum.get_symbol_history(symbol)
        confirmed, partial, engine = _LONG_CONFIRMED, _LONG_PARTIAL, "Early Momentum"
    elif side == "short":
        history = bearish_opportunity.get_symbol_history(symbol)
        confirmed, partial, engine = _SHORT_CONFIRMED, _SHORT_PARTIAL, "Bearish Opportunity"
    else:
        raise ValueError(f"side must be 'long' or 'short', got {side!r}")

    category = _latest_category(history)
    if category is None:
        return {"status": "UNKNOWN", "category": None,
               "reason": f"No {engine} history for {symbol} (outside V2's tracked universe)."}

    if category in confirmed:
        status = "CONFIRMED"
    elif category in partial:
        status = "PARTIAL"
    else:
        status = "NOT_CONFIRMED"  # "Not Qualified" — V2 examined it and found no technical case

    return {"status": status, "category": category,
           "reason": f"{engine} classifies {symbol} as \"{category}\"."}
