"""
Sector & Theme — the emergence discovery page (Phase 12C, reordered Phase 14).

Entry point #2 of the product's two discovery journeys ("Sector/Theme →
Stock → Catalyst → Trade"). Presents `sector_theme_state` (Phase 6)'s
7-state lifecycle and participation roles directly — no new sector-rotation
algorithm, no new RS calculation. Per-sector drill-down uses
`sector_stock_cross_reference` (Phase 7) to answer "which participating
stocks already have their own catalyst" without recomputing anything.

Phase 13's live audit found the page's original ordering (state-group,
then arbitrary within-group order) put a sector with ZERO actionable
participants first on the page, while the sector with the product's best
real example sat unlabeled, several scrolls down. Phase 14 fixes this
WITHOUT a numeric score or any change to the underlying engine: within
each state group, sectors are sorted by a plain, transparent COUNT of
existing `trade_context` values already meaning "actionable"
(LONG_CONTEXT/SHORT_CONTEXT/WATCH_CANDIDATE — Phase 7's own categories,
unchanged), and a highlight strip surfaces every sector with at least one
such participant before the full state-grouped list. This count is always
shown alongside its state/direction badges, never merged into them — sector
strength/maturity (the engine's own state) and "does it currently have an
actionable participant" (a UI-computed transparency aid over Phase 7's
existing per-symbol field) are kept visibly distinct, per the explicit
instruction not to imply a sector is strong merely because it has one
actionable stock.

V2's RS/breadth pages (Sector Intelligence, Market Cycle) are the
underlying primitives this table reuses (`shared_relative_strength.py`,
`apply_hysteresis`) — deliberately not surfaced here as their own top-level
pages.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from components import badge, freshness_badge, kpi_card, section_header
from core.branding import APP_FULL_NAME
from data import contracts
from pages import stock_detail

# The real 7-state lifecycle from event_intelligence/sector_state.py — ordered
# earliest -> most mature -> declining -> neutral for consistent display
# grouping. NOT a numeric progression; DIRECTION_CONTEXT (BULLISH/BEARISH/
# NEUTRAL) is the only ordering the engine itself asserts.
_STATE_ORDER = ["EMERGING", "DEVELOPING", "EARLY_MOMENTUM", "MATURE",
               "CONFIRMED_STRONG", "WEAKENING", "SIDEWAYS"]
_STATE_BADGE = {
    "EMERGING": "blue", "DEVELOPING": "blue", "EARLY_MOMENTUM": "green",
    "MATURE": "green", "CONFIRMED_STRONG": "green",
    "WEAKENING": "red", "SIDEWAYS": "gray",
}
_DIRECTION_BADGE = {"BULLISH": "green", "BEARISH": "red", "NEUTRAL": "gray"}
_ROLE_LABEL = {"leader": "🏆 Leader", "early_participant": "🌱 Early",
              "laggard": "🐢 Laggard", "non_participant": "— Non-participant"}
_CONTEXT_BADGE = {
    "LONG_CONTEXT": "green", "SHORT_CONTEXT": "red",
    "WATCH_CANDIDATE": "amber", "MATURE_CAUTION": "amber",
    "CONTRADICTED": "red", "INSUFFICIENT_EVIDENCE": "gray", "NO_CATALYST": "gray",
}
# Phase 7's own categories that mean "there is a stated directional/watch
# read for this participant" — used only to COUNT and SORT, never to
# fabricate a new label. LONG_CONTEXT/SHORT_CONTEXT/WATCH_CANDIDATE.
_ACTIONABLE_CONTEXTS = {"LONG_CONTEXT", "SHORT_CONTEXT", "WATCH_CANDIDATE"}


def _actionable_counts(cross_df: pd.DataFrame) -> dict[str, dict]:
    """Per sector_or_theme: {total, long, short, watch} counts of
    participants whose trade_context is one of the actionable categories.
    Pure aggregation over an already-computed column — no new evidence."""
    out: dict[str, dict] = {}
    if cross_df.empty:
        return out
    actionable = cross_df[cross_df["trade_context"].isin(_ACTIONABLE_CONTEXTS)]
    for sector, g in actionable.groupby("sector_or_theme"):
        out[sector] = {
            "total": len(g),
            "long": int((g["trade_context"] == "LONG_CONTEXT").sum()),
            "short": int((g["trade_context"] == "SHORT_CONTEXT").sum()),
            "watch": int((g["trade_context"] == "WATCH_CANDIDATE").sum()),
        }
    return out


def _actionable_summary(counts: dict | None) -> str:
    if not counts or counts["total"] == 0:
        return "no actionable participants yet"
    parts = []
    if counts["long"]:
        parts.append(f"{counts['long']} LONG_CONTEXT")
    if counts["short"]:
        parts.append(f"{counts['short']} SHORT_CONTEXT")
    if counts["watch"]:
        parts.append(f"{counts['watch']} WATCH_CANDIDATE")
    return ", ".join(parts)


def _sector_card(row: pd.Series, cross_df: pd.DataFrame, counts: dict | None) -> None:
    with st.container(border=True):
        st.markdown(f"### {row['sector_or_theme']}")
        st.markdown(
            badge(row["confirmed_state"], _STATE_BADGE.get(row["confirmed_state"], "gray"))
            + badge(row["direction_context"], _DIRECTION_BADGE.get(row["direction_context"], "gray")),
            unsafe_allow_html=True,
        )
        st.caption(
            f"{row['taxonomy']} · {row['days_in_state']} days in this state · "
            f"{row['constituent_count']} constituents ({row['measurable_count']} measurable) · "
            f"data quality: {row['data_quality']}"
        )
        # Kept visibly separate from the state/direction badges above — this
        # is a participation fact (Phase 7), not a claim about sector
        # strength (Phase 6's own state already says that, unchanged).
        if counts and counts["total"]:
            st.caption(f"🎯 Actionable participants: {_actionable_summary(counts)}")
        else:
            st.caption("No actionable participants yet (all NO_CATALYST / INSUFFICIENT_EVIDENCE).")

        with st.expander(f"Participants ({len(cross_df)})"):
            if cross_df.empty:
                st.caption("No participant data for this sector/theme yet.")
            else:
                for role in ("leader", "early_participant", "laggard", "non_participant"):
                    role_df = cross_df[cross_df["participation_role"] == role]
                    if role_df.empty:
                        continue
                    st.markdown(f"**{_ROLE_LABEL.get(role, role)}** ({len(role_df)})")
                    for _, r in role_df.iterrows():
                        cols = st.columns([3, 2, 1])
                        with cols[0]:
                            has_event = pd.notna(r.get("event_type"))
                            catalyst = r["event_type"] if has_event else "No current catalyst"
                            st.caption(f"{r['symbol']} · {catalyst}")
                        with cols[1]:
                            ctx = r.get("trade_context", "UNKNOWN")
                            st.markdown(badge(ctx, _CONTEXT_BADGE.get(ctx, "gray")),
                                       unsafe_allow_html=True)
                        with cols[2]:
                            if st.button("View →", key=f"st_{row['sector_or_theme']}_{r['symbol']}"):
                                stock_detail.open_detail(r["symbol"], source_page="🔥 Sector & Theme")
                                st.rerun()

        evidence_for = json.loads(row["evidence_for_json"]) if row.get("evidence_for_json") else []
        evidence_against = json.loads(row["evidence_against_json"]) if row.get("evidence_against_json") else []
        if evidence_for or evidence_against:
            with st.expander("Evidence"):
                if evidence_for:
                    st.markdown("**For:**")
                    for e in evidence_for:
                        st.markdown(f"- {e}")
                if evidence_against:
                    st.markdown("**Against:**")
                    for e in evidence_against:
                        st.markdown(f"- {e}")


def _highlight_strip(df: pd.DataFrame, counts_by_sector: dict) -> None:
    ranked = sorted(
        (s for s in df["sector_or_theme"] if counts_by_sector.get(s, {}).get("total", 0)),
        key=lambda s: counts_by_sector[s]["total"], reverse=True,
    )
    if not ranked:
        st.caption("No sector/theme currently has an actionable participant "
                  "(LONG_CONTEXT / SHORT_CONTEXT / WATCH_CANDIDATE) — everything "
                  "below is state/breadth information without a confirmed "
                  "individual stock thesis yet.")
        return
    section_header("🎯 Sectors With Actionable Participants Today")
    st.caption("Sorted by count of participants with a stated LONG_CONTEXT / "
              "SHORT_CONTEXT / WATCH_CANDIDATE read (Phase 7, unchanged) — a "
              "plain count for ordering, not a strength score. Full detail below.")
    row_by_sector = df.set_index("sector_or_theme")
    for sector in ranked:
        r = row_by_sector.loc[sector]
        state = r["confirmed_state"] if not isinstance(r, pd.DataFrame) else r.iloc[0]["confirmed_state"]
        st.markdown(
            f"**{sector}** ({state}) — {_actionable_summary(counts_by_sector[sector])}"
        )
    st.write("")


def _list_view() -> None:
    st.title("🔥 Sector & Theme")
    st.caption(f"{APP_FULL_NAME} · breadth- and participation-based sector/theme emergence "
              "— which are early, which are already extended, and who's participating")

    freshness_badge(contracts.refresh_status())
    st.write("")

    df = contracts.sector_theme_latest()
    if df.empty:
        st.info("No sector/theme data yet. Run `run_sector_theme.py`, then reload.")
        return

    n_emerging = int(df["confirmed_state"].isin(["EMERGING", "DEVELOPING"]).sum())
    n_early = int((df["confirmed_state"] == "EARLY_MOMENTUM").sum())
    n_mature = int(df["confirmed_state"].isin(["MATURE", "CONFIRMED_STRONG"]).sum())
    n_weakening = int((df["confirmed_state"] == "WEAKENING").sum())
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Emerging/Developing", str(n_emerging), delta="Earliest signal", delta_dir="up")
    with c2:
        kpi_card("Early Momentum", str(n_early), delta="Building", delta_dir="up")
    with c3:
        kpi_card("Mature/Confirmed Strong", str(n_mature), delta="Already extended", delta_dir="flat")
    with c4:
        kpi_card("Weakening", str(n_weakening), delta="Losing strength", delta_dir="down")
    st.write("")

    # Fetched once, sliced per sector below — avoids one query per card and
    # lets the highlight strip / within-group sort share the same counts.
    all_cross = contracts.cross_reference_latest()
    counts_by_sector = _actionable_counts(all_cross)

    state_filter = st.selectbox("State", ["All"] + _STATE_ORDER, key="sec_state")
    filtered = df if state_filter == "All" else df[df["confirmed_state"] == state_filter]

    _highlight_strip(filtered, counts_by_sector)

    def _cross_for(sector: str) -> pd.DataFrame:
        return all_cross[all_cross["sector_or_theme"] == sector] if not all_cross.empty else all_cross

    def _sort_key(sector: str) -> int:
        return counts_by_sector.get(sector, {}).get("total", 0)

    for state in _STATE_ORDER:
        group = filtered[filtered["confirmed_state"] == state]
        if group.empty:
            continue
        section_header(f"{state} ({len(group)})")
        ordered = group.assign(_actionable=group["sector_or_theme"].map(_sort_key)) \
                       .sort_values(["_actionable", "days_in_state"], ascending=[False, True])
        for _, row in ordered.iterrows():
            sector = row["sector_or_theme"]
            _sector_card(row, _cross_for(sector), counts_by_sector.get(sector))

    other = filtered[~filtered["confirmed_state"].isin(_STATE_ORDER)]
    if not other.empty:
        section_header(f"Other ({len(other)})")
        for _, row in other.iterrows():
            sector = row["sector_or_theme"]
            _sector_card(row, _cross_for(sector), counts_by_sector.get(sector))


def render() -> None:
    if stock_detail.is_open():
        stock_detail.render_detail()
        return
    _list_view()
