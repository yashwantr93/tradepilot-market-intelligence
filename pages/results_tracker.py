"""
Tab 3: Results Tracker

Quarterly earnings dashboard - revenue/profit growth, margin change, management
guidance and a derived result score, plus comparison charts. Sample data for V1.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components import COLORS, kpi_card, section_header, style_fig
from data import sample_data

_VERDICT_COLORS = {
    "Beat": COLORS["positive"],
    "In-Line": COLORS["neutral"],
    "Missed": COLORS["negative"],
}


def render() -> None:
    st.title("📈 Results Tracker")
    st.caption("Quarterly earnings scorecard for tracked companies. *(Sample data — V1)*")

    df = sample_data.get_results_tracker()

    # ---- Filter -----------------------------------------------------------
    section_header("Filters")
    verdicts = st.multiselect(
        "Result Verdict",
        options=["Beat", "In-Line", "Missed"],
        default=[],
        placeholder="All verdicts",
    )
    view = df if not verdicts else df[df["Result Verdict"].isin(verdicts)]

    # ---- KPI cards --------------------------------------------------------
    st.write("")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Companies", f"{len(view)}", delta="Reported", delta_dir="flat")
    with k2:
        beat = int((view["Result Verdict"] == "Beat").sum())
        kpi_card("Beat Expectations", f"{beat}", delta="Outperformers", delta_dir="up")
    with k3:
        inline = int((view["Result Verdict"] == "In-Line").sum())
        kpi_card("In-Line Results", f"{inline}", delta="As expected", delta_dir="flat")
    with k4:
        missed = int((view["Result Verdict"] == "Missed").sum())
        kpi_card("Missed Expectations", f"{missed}", delta="Underperformers", delta_dir="down")

    st.write("")

    # ---- Table ------------------------------------------------------------
    section_header("Results Summary")
    if view.empty:
        st.info("No results match the selected filter.")
        return

    st.dataframe(
        view.sort_values("Result Score", ascending=False),
        width="stretch",
        hide_index=True,
        column_config={
            "Revenue Growth %": st.column_config.NumberColumn(format="%.1f%%"),
            "Profit Growth %": st.column_config.NumberColumn(format="%.1f%%"),
            "Margin Change %": st.column_config.NumberColumn(format="%.1f%%"),
            "Result Score": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%d"
            ),
        },
    )

    st.write("")

    # ---- Comparison charts ------------------------------------------------
    c1, c2 = st.columns(2)
    with c1:
        section_header("Revenue Growth Comparison")
        rev = view.sort_values("Revenue Growth %")
        fig = px.bar(rev, x="Revenue Growth %", y="Company Name", orientation="h",
                     color="Result Verdict", color_discrete_map=_VERDICT_COLORS)
        st.plotly_chart(style_fig(fig, height=380), width="stretch")
    with c2:
        section_header("Profit Growth Comparison")
        prof = view.sort_values("Profit Growth %")
        fig2 = px.bar(prof, x="Profit Growth %", y="Company Name", orientation="h",
                      color="Result Verdict", color_discrete_map=_VERDICT_COLORS)
        st.plotly_chart(style_fig(fig2, height=380), width="stretch")

    # ---- Margin trend -----------------------------------------------------
    section_header("Margin Change Trend")
    margin = view.sort_values("Margin Change %", ascending=False)
    fig3 = go.Figure()
    fig3.add_bar(
        x=margin["Company Name"],
        y=margin["Margin Change %"],
        marker_color=[COLORS["positive"] if v >= 0 else COLORS["negative"]
                      for v in margin["Margin Change %"]],
    )
    fig3.add_scatter(
        x=margin["Company Name"],
        y=margin["Margin Change %"],
        mode="lines+markers",
        line=dict(color=COLORS["accent"], width=2),
        name="Trend",
    )
    st.plotly_chart(style_fig(fig3, height=340), width="stretch")
