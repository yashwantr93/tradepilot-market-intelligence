"""
Opportunities — the primary landing page (Phase 12C, regrouped Phase 14).

Answers "what deserves my attention today?" directly from
`event_intelligence.opportunity` (Phase 8) — the final synthesis of every
prior Event Intelligence layer (materiality, expectation/surprise, market
reaction, sector/theme context, technical confirmation). This page adds NO
new ranking, scoring, or logic: it presents the engine's own categorical
tier/direction/type fields, unmodified, and links every card into the
shared Stock/Event Detail drill-down for the full evidence chain.

Phase 14: opportunities are grouped by symbol before rendering — a stock
with several qualifying events (e.g. three separate Large Order Wins)
previously appeared as several near-identical-looking cards, reading as
noise/duplication rather than "several real, distinct events for this
stock." Grouping is presentation-only: every underlying opportunity row
stays individually visible and individually linked into Stock Detail — see
`_group_by_symbol()`.

Read-only, same pattern as every other page — `data/contracts.py` is the
only bridge to the database.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from components import badge, freshness_badge, kpi_card, section_header
from core.branding import APP_FULL_NAME
from data import contracts
from pages import stock_detail

_DIRECTION_BADGE = {"LONG": "green", "SHORT": "red"}
_TIER_BADGE = {"PRIME": "green", "STRONG": "green", "MODERATE": "amber",
              "SPECULATIVE": "amber", "WATCH": "blue"}
_TIER_ORDER = ["PRIME", "STRONG", "MODERATE", "SPECULATIVE", "WATCH"]
_TIER_RANK = {t: i for i, t in enumerate(_TIER_ORDER)}
_TYPE_LABEL = {"EVENT_DRIVEN": "📌 Event-Driven", "CONFLUENCE": "🔗 Confluence",
              "EMERGING_THEME": "🌱 Emerging Theme"}
_TYPE_HELP = {
    "EVENT_DRIVEN": "The stock's own event/catalyst is enough evidence on its own — "
                    "sector context wasn't needed to reach this tier.",
    "CONFLUENCE": "The stock's own event AND its sector/theme context agree — "
                  "two independent kinds of evidence pointing the same way.",
    "EMERGING_THEME": "Sector-led only — the sector/theme is developing and this "
                      "stock participates, but its OWN event didn't independently "
                      "confirm a trade. Watch-only, never above SPECULATIVE tier.",
}


def _evidence_line(row) -> str:
    try:
        evidence = json.loads(row["evidence_for_json"]) if row.get("evidence_for_json") else []
    except (TypeError, ValueError):
        evidence = []
    return evidence[0] if evidence else "See detail for full evidence."


def _event_row(row: pd.Series, show_symbol: bool = False) -> None:
    """One event's compact line inside a symbol group — every individual
    opportunity keeps its own visible evidence line and its own detail link."""
    prefix = f"{row['symbol']} · " if show_symbol else ""
    date = row.get("announcement_date")
    date_s = str(date) if pd.notna(date) else "date UNKNOWN"
    st.markdown(
        f"{prefix}**{row['event_type']}** ({date_s}) "
        + badge(row["direction"], _DIRECTION_BADGE.get(row["direction"], "gray")),
        unsafe_allow_html=True,
    )
    st.caption(f"{_TYPE_LABEL.get(row['opportunity_type'], row['opportunity_type'])} · "
              f"reaction: {row.get('market_reaction_state', 'UNKNOWN')} · "
              f"technical: {row.get('technical_confirmation', 'UNKNOWN')}")
    st.caption(f"Why: {_evidence_line(row)}")
    cols = st.columns([1, 1, 2])
    with cols[0]:
        st.caption(f"Quality: {row.get('data_quality', 'UNKNOWN')}")
    with cols[1]:
        st.caption(f"Horizon: {row.get('time_horizon', 'UNKNOWN')}")
    with cols[2]:
        if st.button("View evidence →", key=f"opp_{row['id']}"):
            stock_detail.open_detail(row["symbol"], int(row["corporate_action_id"]),
                                    source_page="🎯 Opportunities")
            st.rerun()


def _group_by_symbol(df: pd.DataFrame) -> list[dict]:
    """One group per symbol. `best_tier` (the highest tier among that
    symbol's events, used only to decide which tier SECTION the group is
    displayed under) and `directions` (the distinct set of directions
    across its events, so a genuine LONG/SHORT split on one symbol is
    flagged rather than silently picking one) — both derived directly from
    already-computed per-event fields, not a new score."""
    groups = []
    for symbol, g in df.groupby("symbol", sort=False):
        g = g.sort_values("tier", key=lambda s: s.map(_TIER_RANK).fillna(99))
        best_tier = g.iloc[0]["tier"]
        groups.append({
            "symbol": symbol, "best_tier": best_tier,
            "directions": sorted(g["direction"].unique().tolist()),
            "rows": g,
        })
    return groups


def _group_card(group: dict) -> None:
    rows = group["rows"]
    n = len(rows)
    with st.container(border=True):
        st.markdown(f"#### {group['symbol']}")
        header_badges = "".join(
            badge(d, _DIRECTION_BADGE.get(d, "gray")) for d in group["directions"]
        ) + badge(group["best_tier"], _TIER_BADGE.get(group["best_tier"], "gray"))
        st.markdown(header_badges, unsafe_allow_html=True)

        if n == 1:
            _event_row(rows.iloc[0])
            return

        # Multiple events for this symbol — every one stays individually
        # visible and traceable, not collapsed away. Whether they reinforce
        # or conflict is stated plainly, from the existing direction field
        # only (no new agreement/strength logic).
        if len(group["directions"]) == 1:
            st.caption(f"📎 {n} separate events, all {group['directions'][0]} — "
                      f"each below strengthens the same thesis independently.")
        else:
            st.warning(f"⚠️ {n} separate events with MIXED directions "
                      f"({', '.join(group['directions'])}) — these do not agree; "
                      f"review each individually.")
        for i, (_, row) in enumerate(rows.iterrows()):
            if i > 0:
                st.divider()
            _event_row(row)


def _legend() -> None:
    with st.expander("ℹ️ What do PRIME / Confluence / Emerging Theme mean?"):
        st.caption(
            "**Tier** (PRIME → STRONG → MODERATE → SPECULATIVE → WATCH) — how much "
            "evidence currently supports the thesis. Categorical, not a score; "
            "always HEURISTIC, never a guarantee."
        )
        for key, label in _TYPE_LABEL.items():
            st.caption(f"**{label}** — {_TYPE_HELP[key]}")


def _list_view() -> None:
    st.title("🎯 Opportunities")
    st.caption(f"{APP_FULL_NAME} · today's event-driven and sector-driven LONG/SHORT "
              "candidates, with full evidence · rule-based, exploratory — not validated calls")

    freshness_badge(contracts.refresh_status())
    st.write("")

    df = contracts.opportunities()
    if df.empty:
        st.info("No opportunities yet. Run `run_opportunity_intelligence.py` "
               "(after the earlier Event Intelligence pipelines), then reload.")
        return

    # ---- KPIs -------------------------------------------------------------
    n_long = int((df["direction"] == "LONG").sum())
    n_short = int((df["direction"] == "SHORT").sum())
    n_prime = int((df["tier"] == "PRIME").sum())
    n_emerging = int((df["opportunity_type"] == "EMERGING_THEME").sum())
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("LONG", str(n_long), delta="Bullish thesis", delta_dir="up")
    with c2:
        kpi_card("SHORT", str(n_short), delta="Bearish thesis", delta_dir="down")
    with c3:
        kpi_card("PRIME tier", str(n_prime), delta="Highest conviction", delta_dir="up",
                 help="Strongest available combination of evidence — still HEURISTIC, not a guarantee.")
    with c4:
        kpi_card("Emerging themes", str(n_emerging),
                 delta="Sector-led, watch only" if n_emerging else "None active today",
                 delta_dir="flat")
    if n_short == 0 and n_long > 0:
        st.caption("⚠️ No SHORT opportunities today — this reflects what the evidence "
                  "currently shows, not a bias in the engine (it supports both directions equally).")
    _legend()
    st.write("")

    # ---- Filters ------------------------------------------------------
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        direction = st.selectbox("Direction", ["All", "LONG", "SHORT"])
    with fc2:
        otype = st.selectbox("Type", ["All"] + sorted(df["opportunity_type"].unique().tolist()),
                             help="See the legend above for what each type means.")
    with fc3:
        horizon = st.selectbox("Time Horizon", ["All"] + sorted(df["time_horizon"].dropna().unique().tolist()))

    filtered = df.copy()
    if direction != "All":
        filtered = filtered[filtered["direction"] == direction]
    if otype != "All":
        filtered = filtered[filtered["opportunity_type"] == otype]
    if horizon != "All":
        filtered = filtered[filtered["time_horizon"] == horizon]

    if filtered.empty:
        st.info("No opportunities match this filter.")
        return

    groups = _group_by_symbol(filtered)
    n_events = len(filtered)
    n_symbols = len(groups)
    if n_events != n_symbols:
        st.caption(f"{n_symbols} stocks across {n_events} qualifying events today.")

    # ---- Tiered feed, grouped by symbol -----------------------------------
    for tier in _TIER_ORDER:
        tier_groups = [g for g in groups if g["best_tier"] == tier]
        if not tier_groups:
            continue
        section_header(f"{tier} ({len(tier_groups)})")
        cols = st.columns(2)
        for i, g in enumerate(tier_groups):
            with cols[i % 2]:
                _group_card(g)

    other = [g for g in groups if g["best_tier"] not in _TIER_ORDER]
    if other:
        section_header(f"Other ({len(other)})")
        cols = st.columns(2)
        for i, g in enumerate(other):
            with cols[i % 2]:
                _group_card(g)


def render() -> None:
    if stock_detail.is_open():
        stock_detail.render_detail()
        return
    _list_view()
