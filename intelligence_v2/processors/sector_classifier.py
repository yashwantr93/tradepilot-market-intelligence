"""
7-state sector classification — deterministic, threshold-based, no ML/scoring.

Rules are exactly as specified in
docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §1.5. Evaluated strictest/most
specific first (Strong Leader, Downtrend) down to the Sideways default, so a
sector can only ever match one state per day.

Both functions here are PURE (no database access) — deliberately, so
classification determinism can be unit-tested directly: same input dict
(or same state-history list) always produces the same output, every time.
"""

from __future__ import annotations

from intelligence_v2.config.sectors import (
    CONSISTENCY_STRONG_MIN_PCT,
    INFLECTION_LOOKBACK_DAYS,
    MIN_DWELL_DAYS,
    RS_NEAR_ZERO_BAND,
    RS_STRONG_THRESHOLD,
)


def classify_raw(metrics: dict, consistency_pct: float | None) -> str:
    """The threshold-based candidate state, before hysteresis is applied."""
    rs1w, rs1m, rs3m, rs6m, rs1y = (
        metrics.get("rs_1w"), metrics.get("rs_1m"), metrics.get("rs_3m"),
        metrics.get("rs_6m"), metrics.get("rs_1y"),
    )
    a20, a50, a200 = (metrics.get("above_20_sma"), metrics.get("above_50_sma"),
                     metrics.get("above_200_sma"))
    rs3m_ago = metrics.get(f"rs_3m_{INFLECTION_LOOKBACK_DAYS}d_ago")
    rs6m_ago = metrics.get(f"rs_6m_{INFLECTION_LOOKBACK_DAYS}d_ago")
    slope = metrics.get("rs_1m_slope")
    consistency = consistency_pct if consistency_pct is not None else 0.0

    S = RS_STRONG_THRESHOLD
    Z = RS_NEAR_ZERO_BAND

    def pos(v: float | None) -> bool:
        return v is not None and v > S

    def neg(v: float | None) -> bool:
        return v is not None and v < -S

    # 1. Strong Leader — sustained outperformance across 1M/3M/6M, full SMA
    #    stack, and already confirmed by consistency (not a one-off).
    if pos(rs1m) and pos(rs3m) and pos(rs6m) and a20 == "Y" and a50 == "Y" and a200 == "Y" \
            and consistency >= CONSISTENCY_STRONG_MIN_PCT:
        return "Strong Leader"

    # 2. Downtrend — sustained underperformance, below the full SMA stack.
    if neg(rs1m) and neg(rs3m) and neg(rs6m) and a20 == "N" and a50 == "N" and a200 == "N":
        return "Downtrend"

    # 3. Weakening — was clearly strong recently (3M RS was strong ~40
    #    sessions ago) but has now turned down on the short end while the
    #    long end hasn't broken yet.
    if rs6m is not None and rs6m > 0 and rs1w is not None and rs1w < 0 \
            and rs1m is not None and rs1m < 0 and rs3m_ago is not None and rs3m_ago > S:
        return "Weakening"

    # 4. Recovery — a long-term laggard (6M or 1Y still negative) showing a
    #    genuine short-term inflection back above trend.
    if ((rs6m is not None and rs6m < 0) or (rs1y is not None and rs1y < 0)) \
            and rs1m is not None and rs1m > 0 and rs1w is not None and rs1w > 0 \
            and a20 == "Y" and a50 == "Y":
        return "Recovery"

    # 5. Early Momentum — 1W/1M strongly positive NOW, but 3M/6M RS were
    #    flat-or-negative as recently as INFLECTION_LOOKBACK_DAYS ago (a fresh
    #    inflection, not sustained leadership — that's Strong Leader's job).
    if pos(rs1w) and pos(rs1m) \
            and (rs3m_ago is None or rs3m_ago <= Z) and (rs6m_ago is None or rs6m_ago <= Z) \
            and a50 == "Y":
        return "Early Momentum"

    # 6. Improving — RS drifting up over the last month but not yet crossing
    #    the Strong Leader bar, and not in outright decline.
    if slope is not None and slope > 0 and (rs1m is None or rs1m > -Z):
        return "Improving"

    # 7. Default — no directional conviction either way.
    return "Sideways"


def apply_hysteresis(raw_state: str, prior_confirmed_state: str | None,
                     prior_days_in_state: int, recent_raw_states: list[str]) -> tuple[str, int]:
    """Confirm or hold back a state change.

    A change from `prior_confirmed_state` only commits once `raw_state` has
    been the raw (threshold) classification for MIN_DWELL_DAYS consecutive
    sessions INCLUDING today — `recent_raw_states` is the raw_state of the
    most recent (MIN_DWELL_DAYS - 1) stored rows, newest first, and does NOT
    include today's raw_state (the caller passes today's separately).

    Returns (confirmed_state_for_today, days_in_state_for_today).
    """
    if prior_confirmed_state is None:
        # First ever classification for this sector — nothing to hold against.
        return raw_state, 1

    if raw_state == prior_confirmed_state:
        return prior_confirmed_state, prior_days_in_state + 1

    # Candidate differs from the currently confirmed state — only flip once
    # the raw classification has agreed for MIN_DWELL_DAYS consecutive sessions.
    streak = [raw_state] + recent_raw_states[: MIN_DWELL_DAYS - 1]
    if len(streak) >= MIN_DWELL_DAYS and all(s == raw_state for s in streak):
        return raw_state, 1

    # Not yet confirmed — stay on the current state.
    return prior_confirmed_state, prior_days_in_state + 1
