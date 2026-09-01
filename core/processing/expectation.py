"""
Expectation baseline — Phase 1 Event Intelligence Foundation.

Answers: "what was reasonably expected for this quarter, given this
company's OWN recent history?" — an internally-derived proxy, explicitly
NOT analyst consensus (no paid/external estimate feed is used or assumed).

Method: trailing average of the company's own prior same-quarter-YoY growth
prints (as already computed and stored by the existing results pipeline).
This is deliberately the simplest defensible method, per the Phase 1 brief:

  - Requires NO new data source — it reads `results_tracker` rows that the
    existing pipeline already accumulates over successive daily runs.
  - Reliability is capped at MEDIUM even with several samples (never HIGH —
    see `_confidence()`): a 2-3 point trailing average is informative but is
    not a statistically validated estimate, and claiming HIGH confidence
    would overstate what this method can support.
  - Deliberately refuses to guess: with zero prior YoY prints, or when the
    prior prints are wildly inconsistent (see `_is_unstable`), the result is
    EXPECTATION = UNKNOWN rather than a fabricated number.

Known biases (documented, not hidden):
  - Seasonality bias: a trailing average of same-quarter-YoY prints is
    already seasonally aligned (each print compares the same quarter a year
    apart), which is why YoY — not QoQ — history is used as the input here.
  - Low-base bias: if the trailing prints themselves were measured off an
    unusually low or loss-making base, the "expectation" inherits that
    distortion. Not correctable with the data available in Phase 1.
  - Structural-shift blindness: a genuine, permanent change in the
    business (new product line, M&A) will make the trailing average
    obsolete but this method has no way to detect that — it will keep
    expecting the old trend until enough new prints accumulate to shift it.

Should NOT be used:
  - As a stand-in for real analyst consensus in any user-facing claim — the
    `expectation_source` field must always be shown alongside the number.
  - For a company with fewer than `min_samples_for_expectation` prior YoY
    prints stored (returns UNKNOWN in that case).
"""

from __future__ import annotations

from core.config import EXPECTATION as E


def _is_unstable(samples: list[float]) -> bool:
    """A crude, transparent instability check — not a statistical test.

    Prior prints swinging from strongly positive to strongly negative (or
    vice versa) mean "the recent trend" is not a coherent concept for this
    company; better to say UNKNOWN than average noise into a fake baseline.
    """
    if len(samples) < 2:
        return False
    return max(samples) - min(samples) > 60.0  # a >60pp spread among prints


def _confidence(n_samples: int) -> str:
    """LOW with 1 sample, MEDIUM with 2+. Deliberately never HIGH in Phase 1
    — see module docstring; this method cannot support that claim yet."""
    if n_samples >= E["min_samples_for_medium_confidence"]:
        return "MEDIUM"
    return "LOW"


def compute_expectation(prior_yoy_values: list[float]) -> dict:
    """Derive an internal trailing-average expectation from prior YoY prints.

    `prior_yoy_values` — the company's own prior same-quarter-YoY growth
    percentages for this metric (revenue or profit), NEWEST FIRST, excluding
    the quarter currently being evaluated. Caller is responsible for sourcing
    these (in production: prior `results_tracker` rows with basis="YoY").

    Returns a dict with expectation_pct (float|None), expectation_source
    (str), expectation_confidence (str|None), expectation_samples (int).
    """
    lookback = E["trailing_lookback"]
    samples = [v for v in prior_yoy_values[:lookback] if v is not None]

    if len(samples) < E["min_samples_for_expectation"]:
        return {
            "expectation_pct": None,
            "expectation_source": "unknown",
            "expectation_confidence": None,
            "expectation_samples": len(samples),
        }

    if _is_unstable(samples):
        return {
            "expectation_pct": None,
            "expectation_source": "unknown",
            "expectation_confidence": None,
            "expectation_samples": len(samples),
        }

    expectation = round(sum(samples) / len(samples), 2)
    return {
        "expectation_pct": expectation,
        "expectation_source": "internal_trailing_avg",
        "expectation_confidence": _confidence(len(samples)),
        "expectation_samples": len(samples),
    }


def compute_surprise(actual_pct: float | None, expectation_pct: float | None) -> float | None:
    """SURPRISE = ACTUAL - EXPECTED. None whenever either side is unavailable
    — never fabricated. Kept as its own function so EVENT DIRECTION, ACTUAL,
    EXPECTATION and SURPRISE stay four separate values, never collapsed into
    one bullish/bearish field (Phase 1 requirement)."""
    if actual_pct is None or expectation_pct is None:
        return None
    return round(actual_pct - expectation_pct, 2)
