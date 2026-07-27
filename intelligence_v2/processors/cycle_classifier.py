"""
Market Cycle stage classifier — pure, deterministic, fully explainable.

Implements EXACTLY the documented rule set in
`intelligence_v2/config/market_cycle.py::STAGE_RULES_DOC`, in the same order.
The first rule that matches wins, which is what guarantees exactly one stage
per sector; a final fallback guarantees no sector is ever left unclassified.

Every function here is PURE (no database access) so determinism is directly
unit-testable: the same input dict always yields the same stage, reasons, and
behaviour note — every time, on every machine.
"""

from __future__ import annotations

from intelligence_v2.config.market_cycle import (
    LOW_CONSISTENCY_PCT,
    MIN_CYCLE_CONFIRMATIONS,
    MIN_CYCLE_DWELL_DAYS,
    MOMENTUM_FLAT,
    RS_FLAT_BAND,
    RS_STRONG,
    SHORT_HISTORY_DAYS,
    STAGE_BEHAVIOUR,
)


def _fmt(value: float | None, suffix: str = "%") -> str:
    return "n/a" if value is None else f"{value:+.2f}{suffix}"


def classify_cycle_stage(m: dict) -> dict:
    """Assign one cycle stage from one sector-intelligence row.

    `m` is a dict with the Phase 1 fields (rs_1w..rs_1y, perf_*, momentum_1m,
    above_20_sma / above_50_sma / above_200_sma, consistency_pct).

    Returns: {stage, reasons: list[str], possible_behaviour, rule_order,
              matched_by_fallback}
    """
    rs_1w, rs_1m, rs_3m, rs_6m, rs_1y = (
        m.get("rs_1w"), m.get("rs_1m"), m.get("rs_3m"), m.get("rs_6m"), m.get("rs_1y"))
    mom = m.get("momentum_1m")
    a20, a50, a200 = m.get("above_20_sma"), m.get("above_50_sma"), m.get("above_200_sma")
    perf_3m = m.get("perf_3m")

    def gt(v, threshold=0.0):
        return v is not None and v > threshold

    def lt(v, threshold=0.0):
        return v is not None and v < threshold

    # --- Rule 1: Early Momentum ------------------------------------------
    # Deliberately evaluated BEFORE Strong Trend: a sector whose 3M/6M RS is
    # only marginally positive is a fresh mover, not an established leader.
    # The "not yet established" guard lets genuine long-standing leaders fall
    # through to Strong Trend below.
    if a50 == "Y" and gt(rs_1w, RS_STRONG) and gt(rs_1m, RS_STRONG) \
            and not (gt(rs_3m, RS_FLAT_BAND) and gt(rs_6m, RS_FLAT_BAND)) \
            and gt(mom, MOMENTUM_FLAT):
        return _result("Early Momentum", 1, [
            "Price has reclaimed its 50-SMA",
            f"Short-term Relative Strength strongly positive: 1W {_fmt(rs_1w)}, 1M {_fmt(rs_1m)}",
            f"Longer-horizon leadership not yet established (3M {_fmt(rs_3m)}, 6M {_fmt(rs_6m)})",
            f"Momentum improving ({_fmt(mom, '')})",
        ])

    # --- Rule 2: Strong Trend --------------------------------------------
    if a20 == "Y" and a50 == "Y" and gt(rs_1m) and gt(rs_3m) and gt(rs_6m) \
            and (mom is not None and mom >= MOMENTUM_FLAT):
        return _result("Strong Trend", 2, [
            "Price above both its 20-SMA and 50-SMA (trend intact)",
            f"Relative Strength positive across 1M ({_fmt(rs_1m)}), 3M ({_fmt(rs_3m)}) and 6M ({_fmt(rs_6m)})",
            f"Momentum not decelerating ({_fmt(mom, '')})",
            f"3-month performance {_fmt(perf_3m)}",
        ] + ([f"Above 200-SMA as well — long-term trend confirms"] if a200 == "Y" else
             ["Note: still below its 200-SMA — long-term trend not yet confirmed"]))

    # --- Rule 3: Distribution --------------------------------------------
    if a50 == "Y" and lt(rs_1w) and lt(rs_1m) and lt(mom, MOMENTUM_FLAT):
        return _result("Distribution", 3, [
            "Price still above its 50-SMA (still elevated)",
            f"Short-term Relative Strength has rolled over: 1W {_fmt(rs_1w)}, 1M {_fmt(rs_1m)}",
            f"Momentum decelerating ({_fmt(mom, '')})",
            "Strength is leaving the sector while price is still high",
        ])

    # --- Rule 4: Mature Trend --------------------------------------------
    if a50 == "Y" and gt(rs_3m) and (
            lt(mom, MOMENTUM_FLAT) or (rs_1m is not None and rs_3m is not None and rs_1m < rs_3m)):
        reasons = [
            "Price above its 50-SMA (trend still intact)",
            f"3-month Relative Strength still positive ({_fmt(rs_3m)})",
        ]
        if lt(mom, MOMENTUM_FLAT):
            reasons.append(f"Momentum slowing ({_fmt(mom, '')})")
        if rs_1m is not None and rs_3m is not None and rs_1m < rs_3m:
            reasons.append(
                f"Short-term strength now lagging medium-term (1M {_fmt(rs_1m)} < 3M {_fmt(rs_3m)})")
        return _result("Mature Trend", 4, reasons)

    # --- Rule 5: Recovery -------------------------------------------------
    if (lt(rs_6m) or lt(rs_1y)) and gt(rs_1m) and a20 == "Y":
        return _result("Recovery", 5, [
            f"Still a longer-term laggard (6M {_fmt(rs_6m)}, 1Y {_fmt(rs_1y)})",
            f"But 1-month Relative Strength has turned positive ({_fmt(rs_1m)})",
            "Price has reclaimed its 20-SMA",
        ])

    # --- Rule 6: Accumulation --------------------------------------------
    if a50 == "N" and lt(rs_1m) and (mom is not None and mom >= MOMENTUM_FLAT):
        return _result("Accumulation", 6, [
            "Price still below its 50-SMA (under trend)",
            f"1-month Relative Strength still negative ({_fmt(rs_1m)})",
            f"But the deterioration has stopped — momentum no longer falling ({_fmt(mom, '')})",
        ])

    # --- Rule 7: Weak Trend ----------------------------------------------
    if a50 == "N" and lt(rs_1m):
        return _result("Weak Trend", 7, [
            "Price below its 50-SMA",
            f"1-month Relative Strength negative ({_fmt(rs_1m)})",
            f"Momentum {_fmt(mom, '')}",
        ])

    # --- Fallback ---------------------------------------------------------
    if a50 == "Y":
        return _result("Mature Trend", 8, [
            "No specific cycle rule matched (directionless readings)",
            "Price is above its 50-SMA, so treated as the nearest neutral in-trend stage",
        ], fallback=True)
    return _result("Accumulation", 8, [
        "No specific cycle rule matched (directionless readings)",
        "Price is below its 50-SMA, so treated as the nearest neutral below-trend stage",
    ], fallback=True)


def _result(stage: str, rule_order: int, reasons: list[str], fallback: bool = False) -> dict:
    return {
        "stage": stage,
        "reasons": reasons,
        "possible_behaviour": STAGE_BEHAVIOUR.get(stage, ""),
        "rule_order": rule_order,
        "matched_by_fallback": "Y" if fallback else "N",
    }


def build_confidence_notes(m: dict, history_days: int, matched_by_fallback: str,
                           data_method: str | None) -> list[str]:
    """Transparency about how much to trust today's reading. These are honest
    caveats about DATA SUFFICIENCY — deliberately not a numeric confidence
    score, which would violate the no-scoring principle."""
    notes: list[str] = []

    if history_days < SHORT_HISTORY_DAYS:
        notes.append(
            f"Short cycle history: only {history_days} stored session(s). A stage "
            f"change needs the new stage in {MIN_CYCLE_CONFIRMATIONS} of the last "
            f"{MIN_CYCLE_DWELL_DAYS} readings, so early readings can lag.")

    consistency = m.get("consistency_pct")
    if consistency is not None and consistency < LOW_CONSISTENCY_PCT:
        notes.append(
            f"Sector-consistency is {consistency:.1f}% — measured over a trailing "
            "120-session window that is not yet full, so it is not yet meaningful.")

    if matched_by_fallback == "Y":
        notes.append(
            "No specific cycle rule matched; the neutral fallback was used. Treat "
            "this stage as low-conviction.")

    if m.get("rs_1y") is None or m.get("rs_6m") is None:
        notes.append("Long-horizon Relative Strength unavailable — insufficient price history.")

    if data_method and "/5 members" in data_method and not data_method.startswith(
            "basket_from_v1_price_history (5/5"):
        notes.append(
            f"Sector series built from a partial basket ({data_method}) — less "
            "representative than a full 5-member basket.")

    if not notes:
        notes.append("All inputs available; stage confirmed by the standard rule set.")
    return notes


def apply_cycle_hysteresis(raw_stage: str, prior_stage: str | None,
                           prior_days_in_stage: int,
                           recent_raw_stages: list[str]) -> tuple[str, int, bool]:
    """Confirm or hold back a cycle-stage change.

    A change commits when the candidate `raw_stage` appears at least
    MIN_CYCLE_CONFIRMATIONS times within the last MIN_CYCLE_DWELL_DAYS
    readings (today included) — a majority rule, not a consecutive-run rule.
    See the rationale comment in config/market_cycle.py: the consecutive-run
    variant could freeze a sector on a stale stage indefinitely when raw
    readings alternate near a threshold.

    `recent_raw_stages` is the raw stage of the most recent
    (MIN_CYCLE_DWELL_DAYS - 1) stored rows, newest first, excluding today.

    Returns (confirmed_stage, days_in_stage, transitioned).
    """
    if prior_stage is None:
        return raw_stage, 1, False   # first ever reading — nothing to hold against

    if raw_stage == prior_stage:
        return prior_stage, prior_days_in_stage + 1, False

    window = [raw_stage] + recent_raw_stages[: MIN_CYCLE_DWELL_DAYS - 1]
    if window.count(raw_stage) >= MIN_CYCLE_CONFIRMATIONS:
        return raw_stage, 1, True    # confirmed transition

    return prior_stage, prior_days_in_stage + 1, False  # held — not yet confirmed
