"""
Opportunity Intelligence — Phase 8. Pure synthesis logic, no DB access.

Reads (never recomputes) Phase 5's per-event trade signal and, where
available, Phase 7's sector/stock cross-reference for the SAME symbol —
combines them into one explainable Opportunity record. No new materiality/
reaction/RS/breadth computation happens here; this module's only job is
deciding `opportunity_type`, `tier`, and `maturity` from evidence that
already exists, and building one final explanation.

WHY NOT A 0-100 SCORE (per the phase brief's explicit instruction to
justify this before choosing): with a handful of real LONG signals and
zero real SHORT signals in the current dataset (see the Phase 8 report's
REAL-DATA RESULTS), there is nowhere near enough historical outcome data to
fit or validate numeric weights — Phase 4/6's own historical-validation
sections already found no dimension here empirically predicts forward
returns yet. A numeric score would present false precision. A categorical
tier (PRIME/STRONG/MODERATE/SPECULATIVE/WATCH/NO_TRADE), each with a
transparent evidence-count/confluence rule and an explicit HEURISTIC label,
is the same choice already made for `signal_strength` (Phase 5) and
`confirmed_state` (Phase 6) — consistency, not improvisation.

OPPORTUNITY TYPES:
  EVENT_DRIVEN   — a Phase 5 LONG/SHORT signal exists; no sector confluence
                   data available or applicable (symbol outside the
                   tracked GICS universe, or sector story doesn't clearly
                   align either way).
  CONFLUENCE     — a Phase 5 LONG/SHORT signal AND Phase 7's sector/stock
                   cross-reference independently point the same direction
                   (LONG_CONTEXT/SHORT_CONTEXT/WATCH_CANDIDATE aligned with
                   the signal's own direction). The two are measured from
                   genuinely separate inputs (Phase 5: this event's own
                   materiality/reaction/technical; Phase 7: the WHOLE
                   sector basket's breadth/RS) — combining them is not
                   double counting.
  EMERGING_THEME — sector/theme shows a developing story (Phase 7
                   WATCH_CANDIDATE) for a symbol that does NOT yet have its
                   own confirmed Phase 5 LONG/SHORT signal — the sector-led
                   case, explicitly distinct from a company-catalyst-led one.
  NO_TRADE       — neither an event-driven nor a sector-led case exists.

CONTRADICTION HANDLING (per the phase brief's explicit instruction not to
blindly eliminate every contradiction): Phase 5's OWN internal contradiction
check (event vs. its own reaction) already eliminates outright upstream —
an opportunity never reaches this module in that state (direction is
already NO_TRADE). Phase 7's CROSS-LAYER conflicts (sector vs. stock
divergence) are a different, additional kind of evidence — this module
DOWNGRADES the tier by one level and surfaces the conflict as risk, it does
NOT eliminate the opportunity outright, since the stock's own evidence
chain remains internally consistent even when the broader sector disagrees.
"""

from __future__ import annotations

_TIER_ORDER = ["NO_TRADE", "WATCH", "SPECULATIVE", "MODERATE", "STRONG", "PRIME"]
# Maturity labels are deliberately NOT named EARLY/DEVELOPING/MATURE to
# match Phase 6's sector-state names one-for-one — "DEVELOPING" is itself a
# Phase 6 STATE name, and reusing it here for a DIFFERENT maturity meaning
# caused a real bug caught by this phase's own tests (see the Phase 8
# report's DISCOVERED ISSUES). MID_STAGE is the non-colliding replacement.
_EARLY_MATURITY_SECTOR_STAGES = {"EMERGING", "DEVELOPING"}
_MID_MATURITY_SECTOR_STAGES = {"EARLY_MOMENTUM"}
_MATURE_SECTOR_STAGES = {"CONFIRMED_STRONG", "MATURE"}
_ALIGNED_CONTEXT_FOR = {"LONG": {"LONG_CONTEXT", "WATCH_CANDIDATE", "MATURE_CAUTION"},
                       "SHORT": {"SHORT_CONTEXT"}}


def _downgrade(tier: str) -> str:
    idx = _TIER_ORDER.index(tier)
    return _TIER_ORDER[max(idx - 1, 0)]


def _maturity(cross_ref: dict | None, technical_confirmation: str) -> str:
    """EARLY / MID_STAGE / MATURE / UNKNOWN — never invents a threshold
    beyond what Phase 6/7 already classified the sector as."""
    if cross_ref is None:
        return "MATURE" if technical_confirmation == "CONFIRMED" else "UNKNOWN"
    stage = cross_ref["sector_stage"]
    if stage in _MATURE_SECTOR_STAGES:
        return "MATURE"
    if stage in _MID_MATURITY_SECTOR_STAGES:
        return "MID_STAGE"
    if stage in _EARLY_MATURITY_SECTOR_STAGES:
        return "EARLY"
    return "UNKNOWN"


def build_opportunity(signal: dict, cross_ref: dict | None) -> dict:
    """`signal` — one event_trade_signal row (dict, LONG or SHORT — callers
    should not call this for NO_TRADE signals; see opportunity_pipeline.py).
    `cross_ref` — this symbol's sector_stock_cross_reference row, if one
    exists (None if the symbol is outside the tracked sector/theme universe
    or Phase 7 hasn't been run for it)."""
    direction = signal["direction"]
    strength = signal["signal_strength"]
    conflicts = list(cross_ref["conflicts_json"]) if cross_ref else []

    if cross_ref is None:
        opportunity_type = "EVENT_DRIVEN"
    elif cross_ref["trade_context"] in _ALIGNED_CONTEXT_FOR.get(direction, set()):
        opportunity_type = "CONFLUENCE"
    else:
        opportunity_type = "EVENT_DRIVEN"  # sector data exists but doesn't clearly align either way

    # --- base tier from Phase 5's own signal_strength ---
    # (signal_strength is only ever STRONG/MODERATE/WEAK for a LONG/SHORT
    # direction — Phase 5's own engine routes INSUFFICIENT to NO_TRADE
    # before a signal ever reaches this module.)
    base_tier = {"STRONG": "STRONG", "MODERATE": "STRONG", "WEAK": "MODERATE"}[strength]
    tier = base_tier

    if opportunity_type == "CONFLUENCE":
        # Confluence is independent, additional evidence (a whole sector
        # basket's breadth/RS, never counted in Phase 5's own evidence) —
        # one tier upgrade, capped at PRIME.
        tier = _TIER_ORDER[min(_TIER_ORDER.index(base_tier) + 1, len(_TIER_ORDER) - 1)]

    maturity = _maturity(cross_ref, signal["technical_confirmation"])
    if maturity == "MATURE" and opportunity_type == "CONFLUENCE":
        tier = _downgrade(tier)  # already extended — a genuine caution, not a fresh entry

    if conflicts:
        tier = _downgrade(tier)

    evidence_for = list(signal.get("evidence_for", []))
    evidence_against = list(signal.get("evidence_against", []))
    risk = signal.get("risk") or ""
    if cross_ref is not None:
        evidence_for.extend(cross_ref.get("sector_evidence_json", []))
        if conflicts:
            evidence_against.extend(conflicts)
            risk = (risk + " " if risk else "") + "Sector/theme context conflicts with this " \
                                                   "stock's own evidence — see conflicts above."
        elif opportunity_type == "CONFLUENCE":
            evidence_for.append(f"Sector/theme confluence: {cross_ref['sector_or_theme']} is "
                               f"{cross_ref['sector_stage']} and this stock is a "
                               f"{cross_ref['participation_role']}.")

    time_horizon = signal.get("time_horizon") or "SWING"
    if maturity == "MATURE" and time_horizon == "POSITION_CANDIDATE":
        # already extended -> don't present a fresh position entry as attractive
        time_horizon = "SWING"

    return {
        "symbol": signal["symbol"], "corporate_action_id": signal["corporate_action_id"],
        "event_type": signal["event_type"], "direction": direction,
        "opportunity_type": opportunity_type, "tier": tier, "tier_basis": "HEURISTIC",
        "maturity": maturity, "time_horizon": time_horizon,
        "materiality_tier": signal["materiality_tier"],
        "market_reaction_state": signal["market_reaction_state"],
        "continuation_state": signal["continuation_state"],
        "technical_confirmation": signal["technical_confirmation"],
        "sector_or_theme": cross_ref["sector_or_theme"] if cross_ref else None,
        "sector_stage": cross_ref["sector_stage"] if cross_ref else None,
        "participation_role": cross_ref["participation_role"] if cross_ref else None,
        "has_sector_data": cross_ref is not None,
        "evidence_for_json": evidence_for, "evidence_against_json": evidence_against,
        "conflicts_json": conflicts, "risk": risk or None,
        "invalidation": signal.get("invalidation"),
        "data_quality": signal["data_quality"], "predictive_status": "EXPLORATORY",
    }
