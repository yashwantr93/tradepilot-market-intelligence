"""Dashboard page: Corporate Actions Watchlist."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from components import COLORS, kpi_card, section_header, style_fig
from data import contracts

_IMPACT_COLORS = {"Bullish": COLORS["positive"], "Neutral": COLORS["neutral"],
                  "Bearish": COLORS["negative"]}
_PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def render() -> None:
    st.title("🏛️ Corporate Actions Watchlist")
    st.caption("NSE announcements + corporate actions, rule-classified · real data")

    df = contracts.corporate_actions()
    if df.empty:
        st.info("No corporate actions yet. Run `python run_corp_actions.py`.")
        return

    df["_p"] = df["priority"].map(_PRIORITY_ORDER).fillna(9)
    df = df.sort_values(["_p", "announcement_date"], ascending=[True, False])

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Events", str(len(df)))
    with c2:
        kpi_card("High Priority", str(int((df["priority"] == "High").sum())),
                 delta="Material", delta_dir="up")
    with c3:
        kpi_card("Bullish", str(int((df["impact_tag"] == "Bullish").sum())),
                 delta_dir="up", delta="Positive")
    with c4:
        kpi_card("Bearish", str(int((df["impact_tag"] == "Bearish").sum())),
                 delta_dir="down", delta="Negative")

    st.write("")

    # Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        prio = st.multiselect("Priority", ["High", "Medium", "Low"], placeholder="All")
    with f2:
        etypes = st.multiselect("Event Type", sorted(df["event_type"].dropna().unique()),
                                placeholder="All")
    with f3:
        impacts = st.multiselect("Impact", ["Bullish", "Neutral", "Bearish"],
                                 placeholder="All")
    view = df.copy()
    if prio:
        view = view[view["priority"].isin(prio)]
    if etypes:
        view = view[view["event_type"].isin(etypes)]
    if impacts:
        view = view[view["impact_tag"].isin(impacts)]

    section_header("Corporate Actions")
    cols = {"announcement_date": "Date", "symbol": "Symbol", "company_name": "Company",
            "event_type": "Event Type", "impact_tag": "Impact", "priority": "Priority",
            "event_summary": "Summary"}
    st.dataframe(view[list(cols)].rename(columns=cols), width="stretch",
                 hide_index=True,
                 column_config={"Summary": st.column_config.TextColumn(width="large")})

    section_header("Event Type Distribution")
    counts = df["event_type"].value_counts().rename_axis("Event Type").reset_index(name="Count")
    fig = px.bar(counts, x="Count", y="Event Type", orientation="h", color="Count",
                 color_continuous_scale="Blues")
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(style_fig(fig, height=360), width="stretch")
