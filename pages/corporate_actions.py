"""
Tab 2: Corporate Actions

A filterable, professional table of corporate announcements (buybacks, bonus,
splits, dividends, rights, QIP, fund raising, large orders, M&A) with KPI cards
summarising the current view. All data is dummy/sample for V1.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from components import COLORS, kpi_card, section_header, style_fig
from data import sample_data

_IMPACT_COLORS = {
    "Positive": COLORS["positive"],
    "Negative": COLORS["negative"],
    "Neutral": COLORS["neutral"],
}


def render() -> None:
    st.title("🏛️ Corporate Actions")
    st.caption("Track market-moving corporate announcements. *(Sample data — V1)*")

    df = sample_data.get_corporate_actions()

    # ---- Filters ----------------------------------------------------------
    section_header("Filters")
    f1, f2, f3 = st.columns([1.2, 1, 1.4])
    with f1:
        types = st.multiselect(
            "Announcement Type",
            options=sorted(df["Announcement Type"].unique()),
            default=[],
            placeholder="All types",
        )
    with f2:
        impacts = st.multiselect(
            "Impact",
            options=["Positive", "Neutral", "Negative"],
            default=[],
            placeholder="All impacts",
        )
    with f3:
        min_d = df["Announcement Date"].min().date()
        max_d = df["Announcement Date"].max().date()
        date_range = st.date_input(
            "Date Range",
            value=(min_d, max_d),
            min_value=min_d,
            max_value=max_d,
        )

    # ---- Apply filters ----------------------------------------------------
    view = df.copy()
    if types:
        view = view[view["Announcement Type"].isin(types)]
    if impacts:
        view = view[view["Impact"].isin(impacts)]
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start, end = date_range
        view = view[
            (view["Announcement Date"].dt.date >= start)
            & (view["Announcement Date"].dt.date <= end)
        ]

    # ---- KPI cards --------------------------------------------------------
    st.write("")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Total Actions", f"{len(view)}", delta="In current view", delta_dir="flat")
    with k2:
        pos = int((view["Impact"] == "Positive").sum())
        kpi_card("Positive Impact", f"{pos}", delta="Bullish", delta_dir="up")
    with k3:
        neg = int((view["Impact"] == "Negative").sum())
        kpi_card("Negative Impact", f"{neg}", delta="Bearish", delta_dir="down")
    with k4:
        top_type = view["Announcement Type"].mode()
        kpi_card("Most Common", top_type.iloc[0] if not top_type.empty else "—",
                 delta="By count", delta_dir="flat")

    st.write("")

    # ---- Table ------------------------------------------------------------
    section_header("Announcements")
    if view.empty:
        st.info("No corporate actions match the selected filters.")
    else:
        display = view.sort_values("Announcement Date", ascending=False).copy()
        display["Announcement Date"] = display["Announcement Date"].dt.strftime("%d %b %Y")
        st.dataframe(
            display,
            width="stretch",
            hide_index=True,
            column_config={
                "Key Details": st.column_config.TextColumn(width="large"),
                "Impact": st.column_config.TextColumn(width="small"),
            },
        )

    # ---- Breakdown chart --------------------------------------------------
    if not view.empty:
        c1, c2 = st.columns(2)
        with c1:
            section_header("Actions by Type")
            by_type = view["Announcement Type"].value_counts().reset_index()
            by_type.columns = ["Announcement Type", "Count"]
            fig = px.bar(by_type, x="Count", y="Announcement Type", orientation="h",
                         color="Count", color_continuous_scale="Blues")
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(fig, height=340), width="stretch")
        with c2:
            section_header("Impact Distribution")
            by_impact = view["Impact"].value_counts().reset_index()
            by_impact.columns = ["Impact", "Count"]
            fig2 = px.pie(by_impact, names="Impact", values="Count", hole=0.55,
                          color="Impact", color_discrete_map=_IMPACT_COLORS)
            fig2.update_layout(
                height=340,
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=40, b=10),
                font=dict(family="Inter, Segoe UI, sans-serif", size=13),
                legend=dict(orientation="h", yanchor="bottom", y=-0.1,
                            xanchor="center", x=0.5),
            )
            st.plotly_chart(fig2, width="stretch")
