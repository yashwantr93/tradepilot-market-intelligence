"""
Explainable LONG / SHORT / NO_TRADE Signal Engine — Phase 5.

Pure decision logic — no DB access (see signal_pipeline.py for that). Takes
already-computed evidence (materiality from Phase 2, reaction from Phase 3,
technical confirmation from V2 via technical_confirmation.py) and produces
one signal, always with a full, traceable explanation.

CORE PRINCIPLE (Product Vision, non-negotiable): fundamental quality is
never consulted here as a gate — this module has no fundamental-quality
input at all, by design. Direction comes from the event; confirmation comes
from reaction/volume/technical evidence; nothing here asks "is this a good
company."

SIGNAL STRENGTH IS HEURISTIC, NOT VALIDATED. Phase 4 found no evidence
dimension here predicts forward returns on the current (76-event) sample —
`STRONG`/`MODERATE`/`WEAK`/`INSUFFICIENT` is an evidence-COUNT rule (how
many independent dimensions agree), not a weighted or backtested score.
Every signal this module produces carries `predictive_status="EXPLORATORY"`
for exactly this reason, and every caller should treat it that way.

EVIDENCE DIMENSIONS (independently evaluated, never collapsed into one
number):
  1. Materiality       — LOW/MEDIUM/HIGH/TRANSFORMATIONAL/UNKNOWN (Phase 2)
  2. Expectation/Surprise — from a nearby Results-based surprise, if any
                           (Phase 1/2.5) — UNKNOWN for most events today
  3. Market Reaction    — reaction_state (Phase 3)
  4. Continuation       — continuation_state (Phase 3)
  5. Volume             — volume_ratio_day0 vs. the existing
                          TECHNICALS.vol_expansion_mult threshold (reused,
                          not reinvented)
  6. Technical Confirmation — V2 Early Momentum / Bearish Opportunity
                              category (via technical_confirmation.py)

GATE, not scored: `event_alignment` (Phase 3) is the primary conflict
check. CONTRADICTS (a directional event whose own reaction disagrees) hard-
gates to NO_TRADE — it is never "outvoted" by other confirming dimensions,
per the Product Vision's explicit instruction not to auto-resolve a
positive-event/negative-reaction (or the mirror) case into a trade.
"""

from __future__ import annotations

from core.config import MARKET_REACTION as REACTION_T
from core.config import TECHNICALS as TECH_T

_DIRECTIONAL_EVENTS = {"Bullish", "Bearish"}
_POSITIVE_REACTIONS = {"STRONG POSITIVE", "POSITIVE"}
_NEGATIVE_REACTIONS = {"STRONG NEGATIVE", "NEGATIVE"}
_CONFIRMING_MATERIALITY = {"MEDIUM", "HIGH", "TRANSFORMATIONAL"}

SIGNAL_STRENGTHS = ("STRONG", "MODERATE", "WEAK", "INSUFFICIENT")
DIRECTIONS = ("LONG", "SHORT", "NO_TRADE")
PREDICTIVE_STATUS = "EXPLORATORY"  # see module docstring — never change this without new evidence


def _volume_confirmation(volume_ratio_day0: float | None) -> str:
    if volume_ratio_day0 is None:
        return "UNKNOWN"
    return "CONFIRMED" if volume_ratio_day0 >= TECH_T["vol_expansion_mult"] else "NOT_CONFIRMED"


def build_signal(event: dict, technical: dict, expectation: dict | None) -> dict:
    """`event` — one row from repo.get_events_for_signal_engine() (symbol,
    event_type, impact_tag, materiality_tier, reaction_state,
    continuation_state, event_alignment, relative_return_5d, volume_ratio_day0).
    `technical` — technical_confirmation.get_technical_confirmation() result
    for the correct side (long if impact_tag=="Bullish", short if "Bearish";
    caller decides which side to fetch, since fetching both for a Neutral/
    Ambiguous event would be wasted work).
    `expectation` — repo.get_nearby_expectation_surprise() result, or None.

    Returns the full signal dict — every field in EventTradeSignal except
    the id/corporate_action_id/symbol/event_type/announcement_date, which
    the pipeline attaches from `event` directly.
    """
    impact_tag = event["impact_tag"]
    materiality_tier = event["materiality_tier"]
    reaction_state = event["reaction_state"]
    continuation_state = event["continuation_state"]
    event_alignment = event["event_alignment"]
    volume_ratio = event["volume_ratio_day0"]

    evidence_for: list[str] = []
    evidence_against: list[str] = []

    # --- Gate 1: no directional thesis at all ---
    if impact_tag not in _DIRECTIONAL_EVENTS:
        return _no_trade(event, technical, expectation, "NEUTRAL_OR_AMBIGUOUS_EVENT",
                         f"Event direction is {impact_tag!r} — no directional thesis to evaluate.",
                         evidence_for=[], evidence_against=[f"Event direction: {impact_tag}"])

    is_long = impact_tag == "Bullish"

    # --- Gate 2: reaction actively contradicts the event's own direction ---
    if event_alignment == "CONTRADICTS":
        evidence_against.append(
            f"Market reaction ({reaction_state}) CONTRADICTS the event's {impact_tag} direction."
        )
        return _no_trade(event, technical, expectation, "CONTRADICTED_EVIDENCE",
                         f"{impact_tag} event, but the market's reaction disagrees "
                         f"({reaction_state}) — conflicting evidence is not converted into a "
                         "trade in either direction.",
                         evidence_for=[], evidence_against=evidence_against)

    # --- Evaluate each dimension: CONFIRMED / AGAINST / UNKNOWN ---
    evaluable = 0
    confirming = 0

    # Materiality
    if materiality_tier == "UNKNOWN":
        evidence_against.append("Materiality could not be determined (insufficient magnitude/"
                                "denominator data) — UNKNOWN, not treated as confirming.")
    else:
        evaluable += 1
        if materiality_tier in _CONFIRMING_MATERIALITY:
            confirming += 1
            evidence_for.append(f"Materiality: {materiality_tier}.")
        else:
            evidence_against.append(f"Materiality: {materiality_tier} — likely too small to "
                                    "drive a meaningful repricing on its own.")

    # Expectation / Surprise
    if expectation is None:
        evidence_against.append("No expectation/surprise data available for this symbol "
                                "(UNKNOWN — not treated as confirming or contradicting).")
    else:
        evaluable += 1
        surprise = expectation["surprise_pct"]
        surprise_supports = (surprise is not None and
                            ((is_long and surprise > 0) or (not is_long and surprise < 0)))
        if surprise_supports:
            confirming += 1
            evidence_for.append(f"Results surprise {surprise:+.1f}pp supports the "
                                f"{'positive' if is_long else 'negative'} thesis "
                                f"(source: {expectation['expectation_source']}).")
        else:
            evidence_against.append(f"Results surprise {surprise:+.1f}pp does not support "
                                    "the event's direction." if surprise is not None else
                                    "Surprise unavailable.")

    # Market Reaction (already gated for CONTRADICTS above — here we grade AMBIGUOUS/
    # NOT_APPLICABLE/UNKNOWN/weak cases)
    if reaction_state == "UNKNOWN":
        evidence_against.append("Market reaction UNKNOWN (insufficient price history).")
    else:
        evaluable += 1
        reaction_supports = ((is_long and reaction_state in _POSITIVE_REACTIONS) or
                            (not is_long and reaction_state in _NEGATIVE_REACTIONS))
        if reaction_supports:
            confirming += 1
            rel = event.get("relative_return_5d")
            evidence_for.append(f"Market reaction: {reaction_state}"
                                f"{f' ({rel:+.2f}% relative over 5 sessions)' if rel is not None else ''}.")
        else:
            evidence_against.append(f"Market reaction: {reaction_state} — not a clear "
                                    f"{'positive' if is_long else 'negative'} confirmation.")

    # Continuation
    if continuation_state == "INSUFFICIENT_DATA":
        evidence_against.append("Continuation UNKNOWN (insufficient data to judge persistence).")
    else:
        evaluable += 1
        if continuation_state == "CONTINUATION":
            confirming += 1
            evidence_for.append("Reaction is persisting (CONTINUATION), not fading.")
        elif continuation_state == "PARTIAL_REVERSAL":
            evidence_against.append("Reaction is fading (PARTIAL_REVERSAL).")
        else:  # REVERSAL
            evidence_against.append("Reaction has reversed (REVERSAL) since the initial move.")

    # Volume
    vol_status = _volume_confirmation(volume_ratio)
    if vol_status == "UNKNOWN":
        evidence_against.append("Volume confirmation UNKNOWN (insufficient prior volume history).")
    else:
        evaluable += 1
        if vol_status == "CONFIRMED":
            confirming += 1
            evidence_for.append(f"Volume expansion confirmed ({volume_ratio:.2f}x trailing average).")
        else:
            evidence_against.append(f"No volume expansion ({volume_ratio:.2f}x trailing average) "
                                    "— limited participation.")

    # Technical Confirmation (V2)
    if technical["status"] == "UNKNOWN":
        evidence_against.append(technical["reason"])
    else:
        evaluable += 1
        if technical["status"] == "CONFIRMED":
            confirming += 1  # flat count — no dimension is weighted above another (see docstring)
            evidence_for.append(technical["reason"])
        elif technical["status"] == "PARTIAL":
            confirming += 1
            evidence_for.append(technical["reason"] + " (partial confirmation.)")
        else:
            evidence_against.append(technical["reason"] + " (no technical confirmation.)")

    # --- Strength (HEURISTIC evidence count — see module docstring) ---
    strength, data_quality = _classify_strength(confirming, evaluable)

    if strength == "INSUFFICIENT":
        return _no_trade(event, technical, expectation, "INSUFFICIENT_EVIDENCE",
                         f"{impact_tag} event, but too little confirming evidence "
                         f"({confirming}/{evaluable} evaluable dimensions) to support a trade.",
                         evidence_for, evidence_against, materiality_tier=materiality_tier,
                         reaction_state=reaction_state, continuation_state=continuation_state,
                         confirming=confirming, evaluable=evaluable,
                         data_quality=data_quality)

    direction = "LONG" if is_long else "SHORT"
    horizon = _classify_horizon(is_long, continuation_state, technical)
    reason = _build_reason(direction, event, evidence_for, strength)
    risk, invalidation = _risk_and_invalidation(is_long, event, technical)

    return {
        "event_direction": impact_tag, "materiality_tier": materiality_tier,
        "expectation_available": expectation is not None,
        "surprise_pct": expectation["surprise_pct"] if expectation else None,
        "market_reaction_state": reaction_state, "continuation_state": continuation_state,
        "event_alignment": event_alignment, "volume_confirmation": vol_status,
        "technical_confirmation": technical["status"], "technical_category": technical["category"],
        "direction": direction, "no_trade_reason": None,
        "signal_strength": strength, "signal_strength_basis": "HEURISTIC",
        "confirming_dimensions": confirming, "evaluable_dimensions": evaluable,
        "data_quality": data_quality, "time_horizon": horizon,
        "evidence_for_json": evidence_for, "evidence_against_json": evidence_against,
        "risk": risk, "invalidation": invalidation, "reason": reason,
        "predictive_status": PREDICTIVE_STATUS,
    }


def _classify_strength(confirming: int, evaluable: int) -> tuple[str, str]:
    """HEURISTIC — see module docstring. Not a validated score.
    data_quality reflects how much WAS measurable (independent of direction),
    so a signal can be e.g. MODERATE strength but LOW data_quality if most
    dimensions happened to be UNKNOWN rather than genuinely unconfirming."""
    if evaluable == 0:
        return "INSUFFICIENT", "LOW"
    data_quality = "HIGH" if evaluable >= 5 else "MEDIUM" if evaluable >= 3 else "LOW"
    if confirming == 0:
        return "INSUFFICIENT", data_quality
    if confirming >= 5:
        return "STRONG", data_quality
    if confirming >= 3:
        return "MODERATE", data_quality
    return "WEAK", data_quality


def _classify_horizon(is_long: bool, continuation_state: str, technical: dict) -> str:
    """SWING by default. Upgrades to POSITION_CANDIDATE only when momentum
    is PERSISTING (CONTINUATION) AND V2's technical engine independently
    confirms at its STRONGEST tier — persistence + confirmation, per the
    Product Vision's explicit "not simply because the initial signal is
    strong" instruction. No numeric threshold — this is a categorical rule,
    not a score."""
    if continuation_state == "CONTINUATION" and technical["status"] == "CONFIRMED":
        return "POSITION_CANDIDATE"
    return "SWING"


def _risk_and_invalidation(is_long: bool, event: dict, technical: dict) -> tuple[str, str]:
    opposite = "breaks down" if is_long else "breaks out"
    risk = (f"Thesis rests on a single classified event ({event['event_type']}) and its "
           f"early market reaction — both can be wrong or reverse without further notice. "
           f"No fundamental-quality check is applied by this engine (by design — see the "
           f"Product Vision); a fundamentally troubled company can still generate a LONG "
           f"signal here on a strong catalyst, and vice versa for SHORT.")
    invalidation = (f"Thesis is invalidated if the reaction reverses (continuation_state "
                    f"turns REVERSAL) or if V2's technical confirmation for {event['symbol']} "
                    f"{opposite} ({technical.get('category')!r} today).")
    return risk, invalidation


def _build_reason(direction: str, event: dict, evidence_for: list[str], strength: str) -> str:
    lead = evidence_for[0] if evidence_for else "Limited independent confirmation."
    return (f"{direction} — {event['event_type']} ({event['impact_tag']}) for {event['symbol']}. "
           f"{lead} Signal strength: {strength} (HEURISTIC — see predictive_status).")


def _no_trade(event: dict, technical: dict, expectation: dict | None, reason_code: str,
             reason: str, evidence_for: list[str], evidence_against: list[str],
             materiality_tier: str | None = None, reaction_state: str | None = None,
             continuation_state: str | None = None, confirming: int = 0, evaluable: int = 0,
             data_quality: str = "LOW") -> dict:
    return {
        "event_direction": event["impact_tag"],
        "materiality_tier": materiality_tier or event.get("materiality_tier", "UNKNOWN"),
        "expectation_available": expectation is not None,
        "surprise_pct": expectation["surprise_pct"] if expectation else None,
        "market_reaction_state": reaction_state or event.get("reaction_state", "UNKNOWN"),
        "continuation_state": continuation_state or event.get("continuation_state", "INSUFFICIENT_DATA"),
        "event_alignment": event.get("event_alignment", "UNKNOWN"),
        "volume_confirmation": _volume_confirmation(event.get("volume_ratio_day0")),
        "technical_confirmation": technical["status"], "technical_category": technical["category"],
        "direction": "NO_TRADE", "no_trade_reason": reason_code,
        "signal_strength": "INSUFFICIENT", "signal_strength_basis": "HEURISTIC",
        "confirming_dimensions": confirming, "evaluable_dimensions": evaluable,
        "data_quality": data_quality, "time_horizon": "SWING",
        "evidence_for_json": evidence_for, "evidence_against_json": evidence_against,
        "risk": None, "invalidation": None, "reason": reason,
        "predictive_status": PREDICTIVE_STATUS,
    }
