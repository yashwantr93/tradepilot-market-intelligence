"""
Stock/Event Detail — Phase 12C shared drill-down experience.

NOT a primary navigation entry (per the approved architecture). Opened from
Opportunities, Events, or Sector & Theme via `open_detail()`; `app.py`'s
main() checks `is_open()` ahead of the normal page dispatch and renders this
instead, regardless of which sidebar item is selected. This is the single
convergence point for both discovery journeys the product architecture
requires:

    Event → Stock → Evidence → Trade
    Sector/Theme → Stock → Catalyst → Trade

Every field rendered here already exists in the database, assembled by
`data.contracts.stock_event_detail()`. This module adds NO new computation,
thresholds, or logic — presentation only. Missing/UNKNOWN data is always
shown as "UNKNOWN", never inferred or defaulted to a value.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components import badge, section_header

_REACTION_BADGE = {
    "STRONG POSITIVE": "green", "POSITIVE": "green", "NEUTRAL": "gray",
    "NEGATIVE": "red", "STRONG NEGATIVE": "red", "UNKNOWN": "gray",
}
_DIRECTION_BADGE = {"LONG": "green", "SHORT": "red", "NO_TRADE": "gray", "WATCH": "blue"}
_TIER_BADGE = {"PRIME": "green", "STRONG": "green", "MODERATE": "amber",
              "SPECULATIVE": "amber", "WATCH": "blue", "NO_TRADE": "gray"}
_CONFIRM_BADGE = {"CONFIRMED": "green", "PARTIAL": "amber",
                  "NOT_CONFIRMED": "red", "UNKNOWN": "gray"}
_CONTEXT_BADGE = {
    "LONG_CONTEXT": "green", "SHORT_CONTEXT": "red",
    "WATCH_CANDIDATE": "amber", "MATURE_CAUTION": "amber",
    "CONTRADICTED": "red", "INSUFFICIENT_EVIDENCE": "gray", "NO_CATALYST": "gray",
}

_SESSION_KEYS = ("_detail_symbol", "_detail_ca_id", "_detail_source_page")


def open_detail(symbol: str, corporate_action_id: int | None = None,
                source_page: str | None = None) -> None:
    """Call from a row/card click handler, then `st.rerun()`."""
    st.session_state["_detail_symbol"] = symbol
    st.session_state["_detail_ca_id"] = corporate_action_id
    st.session_state["_detail_source_page"] = source_page


def close_detail() -> None:
    for k in _SESSION_KEYS:
        st.session_state.pop(k, None)


def is_open() -> bool:
    return bool(st.session_state.get("_detail_symbol"))


def _na(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v))


def _val(v, unit: str = "") -> str:
    return "UNKNOWN" if _na(v) else f"{v}{unit}"


def _pct(v) -> str:
    return "UNKNOWN" if _na(v) else f"{v:+.2f}%"


def render_detail() -> None:
    # Deferred import — avoids a circular import (data.contracts doesn't
    # import pages, but importing here keeps this module's own import graph
    # obviously one-directional).
    from data import contracts

    symbol = st.session_state.get("_detail_symbol")
    ca_id = st.session_state.get("_detail_ca_id")

    if st.button("← Back", key="detail_back"):
        close_detail()
        st.rerun()

    if not symbol:
        st.info("No stock selected.")
        return

    d = contracts.stock_event_detail(symbol, ca_id)
    ca, opp, sig = d["corporate_action"], d["opportunity"], d["signal"]
    reaction, mat, exp = d["reaction"], d["materiality"], d["expectation"]
    results_row = d["results"]
    signal_source = opp or sig  # opportunity is the fuller record when it exists

    # --- Header ---------------------------------------------------------
    st.title(f"🔍 {symbol}")
    direction = (signal_source or {}).get("direction", "UNKNOWN")
    tier = (opp or {}).get("tier")
    header_badges = []
    if direction != "UNKNOWN":
        header_badges.append((direction, _DIRECTION_BADGE.get(direction, "gray")))
    if tier:
        header_badges.append((tier, _TIER_BADGE.get(tier, "gray")))
    for cr in d["cross_references"]:
        header_badges.append((cr["sector_or_theme"], "blue"))
    if header_badges:
        st.markdown(" ".join(badge(t, k) for t, k in header_badges), unsafe_allow_html=True)
    else:
        st.caption("No current signal, tier, or sector context on record for this stock.")
    st.write("")

    # --- Event / Catalyst -------------------------------------------------
    section_header("🏛️ Event / Catalyst")
    if ca:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Event Type", ca.get("event_type") or "UNKNOWN")
        with c2:
            st.metric("Announced", str(ca.get("announcement_date") or "UNKNOWN"))
        with c3:
            st.metric("Impact", ca.get("impact_tag") or "UNKNOWN")
        if ca.get("event_summary"):
            st.caption(ca["event_summary"])
        if mat:
            reason = f" — {mat['materiality_reason']}" if mat.get("materiality_reason") else ""
            st.caption(f"**Materiality:** {mat.get('materiality_tier', 'UNKNOWN')}{reason}")
        else:
            st.caption("**Materiality:** UNKNOWN (not computed for this event type).")
    else:
        st.caption("No specific event anchors this view — reached via sector/theme "
                  "participation only. No current company catalyst on record.")

    if results_row:
        st.markdown(
            f"**Latest results ({results_row.get('period_end', 'UNKNOWN')}):** "
            f"{results_row.get('result_classification', 'UNKNOWN')} — "
            f"revenue {_pct(results_row.get('revenue_growth_pct'))} YoY, "
            f"profit {_pct(results_row.get('profit_growth_pct'))} YoY"
        )
        if not ca:
            # Results currently have no `corporate_actions` row of their own
            # (a known architecture gap — see
            # data.contracts.results_for_symbol) so they never carry a
            # LONG/SHORT signal on their own.
            st.caption("Note: quarterly results do not yet flow through the "
                      "event/signal engine — no LONG/SHORT thesis originates "
                      "from results alone today.")
    if exp:
        st.caption(
            f"**Expectation/Surprise:** actual {_pct(exp.get('actual_pct'))} vs "
            f"expected {_pct(exp.get('expectation_pct'))} "
            f"({exp.get('expectation_source', 'UNKNOWN')}) → "
            f"surprise {_pct(exp.get('surprise_pct'))}, "
            f"materiality {exp.get('materiality_tier', 'UNKNOWN')}"
        )

    # --- Market Reaction ----------------------------------------------
    section_header("📈 Market Reaction")
    if reaction:
        rs = reaction.get("reaction_state", "UNKNOWN")
        st.markdown(badge(rs, _REACTION_BADGE.get(rs, "gray")), unsafe_allow_html=True)
        cols = st.columns(4)
        windows = [("1D", "relative_return_1d"), ("5D", "relative_return_5d"),
                  ("10D", "relative_return_10d"), ("20D", "relative_return_20d")]
        for col, (label, key) in zip(cols, windows):
            with col:
                st.metric(f"{label} vs Nifty", _pct(reaction.get(key)))
        st.caption(
            f"**Continuation:** {reaction.get('continuation_state', 'UNKNOWN')} · "
            f"**Event alignment:** {reaction.get('event_alignment', 'UNKNOWN')} · "
            f"**Gap:** {_pct(reaction.get('gap_pct'))} · "
            f"**Volume ratio (day 0):** {_val(reaction.get('volume_ratio_day0'))}"
        )
    else:
        st.caption("UNKNOWN — market reaction not yet computed for this event "
                  "(insufficient price history, or the reaction pipeline hasn't run).")

    # --- Sector / Theme Context -----------------------------------------
    section_header("🔥 Sector / Theme Context")
    if d["cross_references"]:
        for cr in d["cross_references"]:
            ctx = cr.get("trade_context", "UNKNOWN")
            st.markdown(
                f"**{cr['sector_or_theme']}** — stage: {cr.get('sector_stage', 'UNKNOWN')} "
                f"({cr.get('sector_direction', 'UNKNOWN')}) · "
                f"role: {cr.get('participation_role', 'UNKNOWN')} · "
                + badge(ctx, _CONTEXT_BADGE.get(ctx, "gray")),
                unsafe_allow_html=True,
            )
    else:
        st.caption("UNKNOWN — not currently tracked in any sector/theme's constituent set.")
    if d["conflicts"]:
        for c in d["conflicts"]:
            st.warning(f"⚠️ {c}")

    # --- Technical Confirmation -----------------------------------------
    section_header("⚡ Technical Confirmation")
    tc = (signal_source or {}).get("technical_confirmation", "UNKNOWN")
    st.markdown(badge(tc, _CONFIRM_BADGE.get(tc, "gray")), unsafe_allow_html=True)
    if sig and sig.get("technical_category"):
        st.caption(f"Basis: {sig['technical_category']}")
    st.caption("Confirmation only — this never originates the thesis above; "
              "the event or sector context does.")

    # --- Signal -----------------------------------------------------------
    section_header("🎯 Signal")
    if signal_source:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Direction", signal_source.get("direction", "UNKNOWN"))
        with c2:
            st.metric("Strength / Tier", tier or (sig or {}).get("signal_strength", "UNKNOWN"))
        with c3:
            st.metric("Time Horizon", signal_source.get("time_horizon", "UNKNOWN"))
        if sig and sig.get("no_trade_reason"):
            st.caption(f"No-trade reason: {sig['no_trade_reason']}")
    else:
        st.caption("UNKNOWN — no trade signal computed yet for this event.")

    # --- Evidence -----------------------------------------------------
    section_header("✅ Evidence")
    ec1, ec2 = st.columns(2)
    with ec1:
        st.markdown("**For**")
        if d["evidence_for"]:
            for e in d["evidence_for"]:
                st.markdown(f"- {e}")
        else:
            st.caption("None recorded.")
    with ec2:
        st.markdown("**Against**")
        if d["evidence_against"]:
            for e in d["evidence_against"]:
                st.markdown(f"- {e}")
        else:
            st.caption("None recorded.")

    # --- Risk / Invalidation --------------------------------------------
    section_header("⚠️ Risk / Invalidation")
    risk = (signal_source or {}).get("risk") or "UNKNOWN"
    invalidation = (signal_source or {}).get("invalidation") or "UNKNOWN"
    st.markdown(f"**Risk:** {risk}")
    st.markdown(f"**Invalidation:** {invalidation}")

    # --- Basis / data quality --------------------------------------------
    st.write("")
    quality = (signal_source or {}).get("data_quality", "UNKNOWN")
    basis = (opp or {}).get("tier_basis") or (sig or {}).get("signal_strength_basis") or "UNKNOWN"
    predictive = (signal_source or {}).get("predictive_status", "UNKNOWN")
    st.caption(
        f"Data quality: **{quality}** · Basis: **{basis}** · "
        f"Predictive status: **{predictive}** — exploratory, not empirically "
        f"validated. See ✅ Validation for track record."
    )
