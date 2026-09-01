"""
Events — the catalyst discovery page (Phase 12C).

Entry point #1 of the product's two discovery journeys ("Event → Stock →
Evidence → Trade"). Two tabs over existing, already-computed tables — no new
event engine:

  * Corporate Actions — dividends, buybacks, orders, regulatory/legal
    action, management change, M&A, etc. (`core.db.models.CorporateAction`,
    classified by `core/config.py`'s EVENT_TYPE_RULES).
  * Results — quarterly earnings (`results_tracker`). Results do not
    currently flow through the corporate-action/signal engine (see
    `data.contracts.results_for_symbol`'s docstring) — a real, known gap
    this page surfaces rather than hides, not something it works around.

Every row links into the shared Stock/Event Detail drill-down.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components import badge, freshness_badge, kpi_card, section_header
from core.branding import APP_FULL_NAME
from data import contracts
from pages import stock_detail

_IMPACT_BADGE = {"Bullish": "green", "Bearish": "red", "Neutral": "gray", "Ambiguous": "amber"}
_PRIORITY_BADGE = {"High": "red", "Medium": "amber", "Low": "gray"}
_DIRECTION_BADGE = {"LONG": "green", "SHORT": "red", "NO_TRADE": "gray"}
_RESULT_BADGE = {"Strong": "green", "Neutral": "gray", "Weak": "red"}


def _corp_actions_tab() -> None:
    df = contracts.corporate_actions_with_signal()
    if df.empty:
        st.info("No corporate actions yet. Run `run_corp_actions.py`, then reload.")
        return

    n_tradeable = int(df["direction"].isin(["LONG", "SHORT"]).sum())
    st.caption(
        f"{n_tradeable} of {len(df)} events produced a LONG/SHORT signal — the "
        f"rest are stored, classified evidence that this engine's rules judged "
        f"not (yet) tradeable, not noise to be deleted."
    )
    c0, c1, c2, c3 = st.columns(4)
    with c0:
        relevance = st.selectbox(
            "Relevance", ["All", "Tradeable (has signal)", "No Trade"], key="ev_relevance",
            help="Tradeable = this event's own trade signal is LONG or SHORT "
                "(from event_trade_signal, unchanged). No Trade = the signal "
                "engine evaluated it and found insufficient/contradicted/neutral "
                "evidence — a stated conclusion, not a gap.",
        )
    with c1:
        etype = st.selectbox("Event Type", ["All"] + sorted(df["event_type"].unique().tolist()),
                             key="ev_etype")
    with c2:
        impact = st.selectbox("Impact", ["All", "Bullish", "Bearish", "Neutral", "Ambiguous"],
                              key="ev_impact")
    with c3:
        priority = st.selectbox("Priority", ["All", "High", "Medium", "Low"], key="ev_priority")

    filtered = df.copy()
    if relevance == "Tradeable (has signal)":
        filtered = filtered[filtered["direction"].isin(["LONG", "SHORT"])]
    elif relevance == "No Trade":
        filtered = filtered[~filtered["direction"].isin(["LONG", "SHORT"])]
    if etype != "All":
        filtered = filtered[filtered["event_type"] == etype]
    if impact != "All":
        filtered = filtered[filtered["impact_tag"] == impact]
    if priority != "All":
        filtered = filtered[filtered["priority"] == priority]

    filtered = filtered.sort_values("announcement_date", ascending=False)
    st.caption(f"{len(filtered)} of {len(df)} events")

    for _, row in filtered.head(100).iterrows():
        with st.container(border=True):
            st.markdown(f"**{row['symbol']}** — {row['event_type']}")
            badges = [badge(row["impact_tag"], _IMPACT_BADGE.get(row["impact_tag"], "gray"))]
            if pd.notna(row.get("materiality_tier")):
                badges.append(badge(f"Materiality: {row['materiality_tier']}", "blue"))
            if pd.notna(row.get("direction")):
                badges.append(badge(row["direction"], _DIRECTION_BADGE.get(row["direction"], "gray")))
            st.markdown("".join(badges), unsafe_allow_html=True)
            st.caption(f"{row['announcement_date']} · Priority: {row['priority']}"
                      + (f" · {row['event_summary'][:140]}" if row.get("event_summary") else ""))
            if st.button("View evidence →", key=f"ev_{row['id']}"):
                stock_detail.open_detail(row["symbol"], int(row["id"]), source_page="🏛️ Events")
                st.rerun()

    if len(filtered) > 100:
        st.caption(f"Showing the most recent 100 of {len(filtered)} matching events.")


def _results_tab() -> None:
    period = contracts.latest_date("results_tracker", "period_end")
    df = contracts.results(period)
    if df.empty:
        st.info("No results data yet. Run `run_results.py`, then reload.")
        return

    st.caption(f"Latest reporting period: {period}")
    c1, c2 = st.columns(2)
    with c1:
        strong = int((df["result_classification"] == "Strong").sum())
        kpi_card("Strong", str(strong), delta="Beat both revenue & profit", delta_dir="up")
    with c2:
        weak = int((df["result_classification"] == "Weak").sum())
        kpi_card("Weak", str(weak), delta="Declined", delta_dir="down")

    classification = st.selectbox("Classification", ["All", "Strong", "Neutral", "Weak"],
                                  key="res_class")
    filtered = df if classification == "All" else df[df["result_classification"] == classification]
    filtered = filtered.sort_values("result_classification")

    for _, row in filtered.iterrows():
        with st.container(border=True):
            st.markdown(f"**{row['symbol']}**")
            st.markdown(badge(row["result_classification"],
                              _RESULT_BADGE.get(row["result_classification"], "gray")),
                       unsafe_allow_html=True)
            rev = row.get("revenue_growth_pct")
            prof = row.get("profit_growth_pct")
            rev_s = f"{rev:+.1f}%" if pd.notna(rev) else "UNKNOWN"
            prof_s = f"{prof:+.1f}%" if pd.notna(prof) else "UNKNOWN"
            st.caption(f"Revenue YoY: {rev_s} · Profit YoY: {prof_s}")
            if st.button("View evidence →", key=f"res_{row['symbol']}"):
                stock_detail.open_detail(row["symbol"], source_page="🏛️ Events")
                st.rerun()


def _list_view() -> None:
    st.title("🏛️ Events")
    st.caption(f"{APP_FULL_NAME} · every corporate action and quarterly result, "
              "with its rule-based impact and any resulting signal")

    freshness_badge(contracts.refresh_status())
    st.write("")

    tab1, tab2 = st.tabs(["📋 Corporate Actions", "📊 Results"])
    with tab1:
        _corp_actions_tab()
    with tab2:
        _results_tab()


def render() -> None:
    if stock_detail.is_open():
        stock_detail.render_detail()
        return
    _list_view()
