"""
Market Reaction classification — Phase 3.

Three SEPARATE, independently-explainable dimensions rather than one
combined label (e.g. "FAILED POSITIVE REACTION"). Deliberate design choice,
made after inspecting the task brief's own suggested state list: collapsing
"how did price move," "is the event's own thesis confirmed," and "is the
move persisting" into one enum forces information loss and hides exactly
the kind of divergence (positive event, negative reaction) the Product
Vision requires to stay visible. Keeping them separate mirrors the same
principle already used for Direction/Expectation/Surprise/Materiality
throughout this project — see the Phase 3 report's PRODUCT ALIGNMENT
section for the full reasoning.

  reaction_state      — pure price/volume behavior, direction-agnostic
                        vocabulary (STRONG POSITIVE ... STRONG NEGATIVE).
                        Says nothing about whether this "confirms" the event.
  continuation_state  — is the move persisting (1-session vs. 5-session) or
                        reversing?
  event_alignment     — does the reaction agree with the EVENT's OWN
                        classified direction? Computed separately, never by
                        overwriting either side (Product Vision §6).

Thresholds are calibrated from the empirical distribution of the 76 real,
currently-computable 5-session relative returns in local data (measured
during this phase's audit): p10=-5.5%, p25=-2.0%, median=+0.3%, p75=+2.5%,
p90=+6.7%. NEUTRAL band and POSITIVE/NEGATIVE boundaries are set at
approximately p25/p75 (±2.5%); STRONG boundaries at approximately p10/p90
(±7%, rounded). Same "evidence-derived starting point, not a fabricated
number" status as the Materiality thresholds from Phase 1/2.
"""

from __future__ import annotations

from core.config import MARKET_REACTION as T

REACTION_STATES = (
    "STRONG POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE", "STRONG NEGATIVE", "UNKNOWN",
)
CONTINUATION_STATES = ("CONTINUATION", "PARTIAL_REVERSAL", "REVERSAL", "INSUFFICIENT_DATA")
ALIGNMENT_STATES = ("ALIGNED", "CONTRADICTS", "AMBIGUOUS", "NOT_APPLICABLE", "UNKNOWN")

_DIRECTIONAL_IMPACTS = {"Bullish", "Bearish"}  # Neutral/Ambiguous have no thesis to compare against


def classify_reaction_state(relative_return_5d: float | None) -> tuple[str, str]:
    """Returns (state, reason). Prefers the 5-session window as the primary
    read — long enough to filter pure noise, short enough that coverage
    isn't crippled (see the Phase 3 report's COVERAGE section: 17.2% at +5d
    vs. 9.7% at +20d)."""
    if relative_return_5d is None:
        return "UNKNOWN", "Insufficient price history to compute a 5-session reaction."

    r = relative_return_5d
    if r >= T["strong_pct"]:
        tier = "STRONG POSITIVE"
    elif r >= T["moderate_pct"]:
        tier = "POSITIVE"
    elif r > -T["moderate_pct"]:
        tier = "NEUTRAL"
    elif r > -T["strong_pct"]:
        tier = "NEGATIVE"
    else:
        tier = "STRONG NEGATIVE"

    reason = f"{r:+.2f}% relative return over 5 sessions -> {tier}"
    return tier, reason


def classify_continuation(relative_return_1d: float | None,
                          relative_return_5d: float | None) -> str:
    """Is the 1-session initial reaction persisting, fading, or reversing by
    session 5? Deliberately uses 1d-vs-5d (not 5d-vs-10d/20d) as the primary
    pair — coverage for the longer pair is materially thinner (see
    COVERAGE).

    Three outcomes, not two — found necessary during this phase's real-data
    validation (BAJAJ-AUTO: 1d -2.79% -> 5d -2.59%, same sign, merely
    shrinking — labeling that "REVERSAL" alongside a genuine sign flip like
    VISAKAIND's 1d -2.13% -> 5d +0.98% would conflate two different
    behaviors under one word):
      CONTINUATION     — same sign, magnitude held or grew
      PARTIAL_REVERSAL — same sign, magnitude shrank (the move is fading,
                        but never crossed back through zero)
      REVERSAL         — sign flipped entirely
    """
    if relative_return_1d is None or relative_return_5d is None:
        return "INSUFFICIENT_DATA"
    if abs(relative_return_1d) < T["moderate_pct"] / 2:
        # The initial move itself was too small to call a direction on —
        # "continuation of noise" isn't a meaningful judgement.
        return "INSUFFICIENT_DATA"
    same_direction = (relative_return_1d > 0) == (relative_return_5d > 0)
    if not same_direction:
        return "REVERSAL"
    if abs(relative_return_5d) >= abs(relative_return_1d):
        return "CONTINUATION"
    return "PARTIAL_REVERSAL"


def classify_event_alignment(impact_tag: str, reaction_state: str) -> str:
    """Does the market's reaction agree with the event's OWN classified
    direction? Never overwrites either side — both remain independently
    stored (Product Vision §6)."""
    if reaction_state == "UNKNOWN":
        return "UNKNOWN"
    if impact_tag not in _DIRECTIONAL_IMPACTS:
        return "NOT_APPLICABLE"  # event itself has no directional thesis (Neutral/Ambiguous)

    is_positive_reaction = reaction_state in ("STRONG POSITIVE", "POSITIVE")
    is_negative_reaction = reaction_state in ("STRONG NEGATIVE", "NEGATIVE")

    if impact_tag == "Bullish":
        if is_positive_reaction:
            return "ALIGNED"
        if is_negative_reaction:
            return "CONTRADICTS"
        return "AMBIGUOUS"  # NEUTRAL reaction — market hasn't clearly confirmed or rejected
    else:  # Bearish
        if is_negative_reaction:
            return "ALIGNED"
        if is_positive_reaction:
            return "CONTRADICTS"
        return "AMBIGUOUS"
