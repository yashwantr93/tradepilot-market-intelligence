"""
Materiality — Phase 1 Event Intelligence Foundation.

Rule-based, transparent, ratio-first. No 0-100 score anywhere. Every result
carries a human-readable `reason` string so a user can see exactly why an
event received its tier — never a black box.

Two entry points:

  compute_results_materiality(surprise_pct)
      The only materiality computation actually WIRED into a pipeline in
      Phase 1 — Results is the one category with a real Surprise value
      (see expectation.py) to grade against.

  compute_ratio_materiality(value, denominator, denominator_label, thresholds)
      A general-purpose ratio-tier function for future categories (order
      value / revenue, corporate-action value / market cap, etc.) — NOT
      wired into any pipeline yet in Phase 1 (Corporate Actions doesn't yet
      have a reliable magnitude+denominator pair extracted for most event
      types), but implemented and tested now so a later phase can wire it in
      without redesigning the tier logic.

Both refuse to guess: whenever the required input is missing, the tier is
UNKNOWN — never a forced LOW/MEDIUM/HIGH guess.
"""

from __future__ import annotations

from core.config import MATERIALITY as M

TIERS = ("LOW", "MEDIUM", "HIGH", "TRANSFORMATIONAL", "UNKNOWN")


def compute_results_materiality(surprise_pct: float | None) -> dict:
    """Tier a Results surprise using the documented starting-point thresholds
    in core.config.MATERIALITY. See that dict's comment: these are an
    explicit starting point, not evidence-derived precise cutoffs."""
    if surprise_pct is None:
        return {
            "materiality_tier": "UNKNOWN",
            "materiality_reason": "No surprise value available (expectation could "
                                   "not be derived) — materiality is UNKNOWN rather "
                                   "than guessed.",
        }

    mag = abs(surprise_pct)
    if mag < M["results_surprise_low_pct"]:
        tier = "LOW"
    elif mag < M["results_surprise_medium_pct"]:
        tier = "MEDIUM"
    elif mag < M["results_surprise_high_pct"]:
        tier = "HIGH"
    else:
        tier = "TRANSFORMATIONAL"

    sign = "positive" if surprise_pct >= 0 else "negative"
    reason = (f"Surprise of {surprise_pct:+.1f}pp vs. internal trailing expectation "
              f"({sign}) -> {tier} (|surprise| {mag:.1f}pp)")
    return {"materiality_tier": tier, "materiality_reason": reason}


def compute_ratio_materiality(value: float | None, denominator: float | None,
                              denominator_label: str,
                              thresholds: dict[str, float]) -> dict:
    """Generic magnitude/denominator ratio tiering.

    `thresholds` must provide "low_pct", "medium_pct", "high_pct" (ratio, as
    a percentage of denominator, below which the tier applies; at/above
    "high_pct" -> TRANSFORMATIONAL). UNKNOWN whenever value or denominator is
    missing, or denominator is zero/negative (a ratio against zero is not
    meaningful, not "infinitely material").
    """
    if value is None or denominator is None or denominator <= 0:
        return {
            "materiality_tier": "UNKNOWN",
            "materiality_reason": f"Missing or non-positive {denominator_label} — "
                                   "cannot compute a ratio, materiality is UNKNOWN "
                                   "rather than guessed.",
        }

    ratio_pct = abs(value) / denominator * 100
    if ratio_pct < thresholds["low_pct"]:
        tier = "LOW"
    elif ratio_pct < thresholds["medium_pct"]:
        tier = "MEDIUM"
    elif ratio_pct < thresholds["high_pct"]:
        tier = "HIGH"
    else:
        tier = "TRANSFORMATIONAL"

    reason = f"{ratio_pct:.1f}% of {denominator_label} -> {tier}"
    return {"materiality_tier": tier, "materiality_reason": reason}
