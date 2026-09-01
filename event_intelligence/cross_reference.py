"""
Sector/Theme → Stock cross-reference — Phase 7. Pure logic, no DB access.

Combines Phase 6's sector/theme state (breadth/RS context + participation
role) with Phase 5's per-stock trade signal (company event + evidence) into
one explainable record. Does NOT compute a score or a final ranking — see
module docstring in signal_engine.py for why 0-100 scores are avoided
throughout this project; the same reasoning applies here.

EVIDENCE INDEPENDENCE (explicit, per the phase brief's "avoid double
counting" requirement): `sector_evidence` describes the SECTOR's own
breadth/RS/event-density (Phase 6, computed across the whole sector basket);
`stock_evidence` describes THIS STOCK's own event/materiality/reaction/
technical evidence (Phase 5, computed for this one corporate action). They
are never merged into one number — a company's own order-win event
contributes to `stock_evidence` only; it is never re-counted as sector-level
breadth or volume evidence (Phase 6's breadth/volume were already computed
independently, across ALL sector constituents' prices, before this module
ever runs — there is no shared input to double-count).
"""

from __future__ import annotations

_BULLISH_SECTOR_STATES = {"EMERGING", "DEVELOPING", "EARLY_MOMENTUM", "CONFIRMED_STRONG"}
_EXTENDED_SECTOR_STATES = {"CONFIRMED_STRONG", "MATURE"}


def build_cross_reference(sector_or_theme: str, sector_stage: str, sector_direction: str,
                          symbol: str, participation_role: str,
                          company_event: dict | None) -> dict:
    """`company_event` — the symbol's most recent event_trade_signal row
    (as a dict) within the recency window, or None if the symbol has no
    corporate-action history at all (genuinely different from "has an
    event but it produced NO_TRADE" — see NO_CATALYST below)."""
    sector_evidence = [f"{sector_or_theme}: {sector_stage} ({sector_direction} context)."]
    conflicts: list[str] = []

    if company_event is None:
        return {
            "sector_or_theme": sector_or_theme, "sector_stage": sector_stage,
            "sector_direction": sector_direction, "symbol": symbol,
            "participation_role": participation_role,
            "company_event_id": None, "event_type": None, "event_direction": None,
            "materiality_tier": "UNKNOWN", "expectation_available": False, "surprise_pct": None,
            "market_reaction_state": "UNKNOWN", "continuation_state": "INSUFFICIENT_DATA",
            "technical_confirmation": "UNKNOWN", "signal_direction": None,
            "sector_evidence_json": sector_evidence,
            "stock_evidence_json": [f"{symbol} has no corporate-action history on record — "
                                    "no company-specific catalyst to evaluate."],
            "evidence_for_json": [], "evidence_against_json": [
                "No company event available — sector participation alone is not evidence of a "
                "stock-specific catalyst."
            ],
            "conflicts_json": [], "trade_context": "NO_CATALYST", "data_quality": "LOW",
            "time_horizon": None,
        }

    stock_evidence = [f"{symbol}: {company_event['event_type']} ({company_event['event_direction']}), "
                      f"materiality={company_event['materiality_tier']}, "
                      f"reaction={company_event['market_reaction_state']}, "
                      f"technical={company_event['technical_confirmation']}."]

    # --- Contradiction detection (never hidden, always checked first) ---
    sector_bullish = sector_direction == "BULLISH"
    sector_bearish = sector_direction == "BEARISH"
    stock_bullish_event = company_event["event_direction"] == "Bullish"
    stock_bearish_event = company_event["event_direction"] == "Bearish"
    is_leader_or_early = participation_role in ("leader", "early_participant")
    is_lagging_or_non = participation_role in ("laggard", "non_participant")

    if sector_bullish and is_lagging_or_non and stock_bearish_event:
        conflicts.append(f"Sector is {sector_direction.lower()} ({sector_stage}) but {symbol} is "
                         f"{participation_role} with a negative company event — sector strength does "
                         "not extend to this stock.")
    if sector_bearish and is_leader_or_early:
        conflicts.append(f"{symbol} is a {participation_role} despite the sector being WEAKENING — "
                         "outperforming its own weak sector context.")
    if sector_bullish and stock_bearish_event:
        conflicts.append(f"Sector context is BULLISH but {symbol}'s own event "
                         f"({company_event['event_type']}) is Bearish — company-specific evidence "
                         "contradicts the broader sector read.")
    if sector_bearish and stock_bullish_event:
        conflicts.append(f"Sector context is BEARISH (WEAKENING) but {symbol}'s own event "
                         f"({company_event['event_type']}) is Bullish — company-specific catalyst "
                         "may override broader sector weakness.")

    signal_direction = company_event.get("signal_direction")

    # --- trade_context (categorical, first-match-wins; conflicts dominate) ---
    if conflicts:
        trade_context = "CONTRADICTED"
    elif (sector_bullish and is_leader_or_early and signal_direction == "LONG"
          and sector_stage in _EXTENDED_SECTOR_STATES
          and company_event["technical_confirmation"] == "CONFIRMED"):
        trade_context = "MATURE_CAUTION"
    elif (sector_bullish and is_leader_or_early
          and company_event["materiality_tier"] in ("HIGH", "TRANSFORMATIONAL")
          and company_event["market_reaction_state"] in ("NEUTRAL", "UNKNOWN")):
        trade_context = "WATCH_CANDIDATE"
    elif sector_bullish and is_leader_or_early and signal_direction == "LONG":
        trade_context = "LONG_CONTEXT"
    elif sector_bearish and participation_role == "laggard" and signal_direction == "SHORT":
        trade_context = "SHORT_CONTEXT"
    else:
        trade_context = "INSUFFICIENT_EVIDENCE"

    evidence_for = list(company_event.get("evidence_for", []))
    evidence_against = list(company_event.get("evidence_against", []))
    if trade_context == "MATURE_CAUTION":
        evidence_against.append(f"Sector already {sector_stage} and stock's own technical "
                                "confirmation is already CONFIRMED — thesis may already be extended.")
    if trade_context == "WATCH_CANDIDATE":
        evidence_for.append("Company catalyst is material but the market has not yet clearly "
                            "reacted — a developing, not yet confirmed, setup.")

    data_quality = ("HIGH" if company_event["materiality_tier"] != "UNKNOWN"
                    and company_event["market_reaction_state"] != "UNKNOWN"
                    and company_event["technical_confirmation"] != "UNKNOWN"
                    else "MEDIUM" if company_event["market_reaction_state"] != "UNKNOWN"
                    else "LOW")

    return {
        "sector_or_theme": sector_or_theme, "sector_stage": sector_stage,
        "sector_direction": sector_direction, "symbol": symbol,
        "participation_role": participation_role,
        "company_event_id": company_event["corporate_action_id"],
        "event_type": company_event["event_type"], "event_direction": company_event["event_direction"],
        "materiality_tier": company_event["materiality_tier"],
        "expectation_available": company_event["expectation_available"],
        "surprise_pct": company_event["surprise_pct"],
        "market_reaction_state": company_event["market_reaction_state"],
        "continuation_state": company_event["continuation_state"],
        "technical_confirmation": company_event["technical_confirmation"],
        "signal_direction": signal_direction,
        "sector_evidence_json": sector_evidence, "stock_evidence_json": stock_evidence,
        "evidence_for_json": evidence_for, "evidence_against_json": evidence_against,
        "conflicts_json": conflicts, "trade_context": trade_context, "data_quality": data_quality,
        "time_horizon": company_event.get("time_horizon"),
    }
