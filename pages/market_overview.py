"""
Tab 1: Market Overview

High-level pulse of the Indian market - headline indices, breadth, sentiment,
sector heatmap and key technical levels. All data is dummy/sample for V1.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components import COLORS, kpi_card, section_header, style_fig
from data import sample_data


def _delta_dir(value: float) -> str:
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def render() -> None:
    st.title("📊 Market Overview")
    st.caption("A real-time pulse of the Indian equity market. *(Sample data — V1)*")

    # ---- KPI cards: headline indices -------------------------------------
    snapshot = sample_data.get_index_snapshot()
    cols = st.columns(len(snapshot))
    for col, (_, row) in zip(cols, snapshot.iterrows()):
        with col:
            kpi_card(
                label=row["Index"],
                value=f'{row["Last"]:,.2f}',
                delta=f'{row["Change"]:+,.2f} ({row["% Change"]:+.2f}%)',
                delta_dir=_delta_dir(row["Change"]),
            )

    st.write("")

    # ---- Sentiment + breadth row -----------------------------------------
    left, right = st.columns([1, 1.4])

    with left:
        section_header("Market Sentiment Indicator")
        sentiment = sample_data.get_market_sentiment()
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=sentiment["score"],
                number={"suffix": " / 100"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": sentiment["color"]},
                    "steps": [
                        {"range": [0, 25], "color": "rgba(220,38,38,0.25)"},
                        {"range": [25, 45], "color": "rgba(234,88,12,0.25)"},
                        {"range": [45, 55], "color": "rgba(202,138,4,0.25)"},
                        {"range": [55, 75], "color": "rgba(101,163,13,0.25)"},
                        {"range": [75, 100], "color": "rgba(22,163,74,0.25)"},
                    ],
                },
            )
        )
        gauge.update_layout(height=240, margin=dict(l=20, r=20, t=10, b=10),
                            paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(gauge, width="stretch")
        st.markdown(
            f'<div style="text-align:center;"><span class="pill" '
            f'style="background:{sentiment["color"]};">{sentiment["label"]}</span></div>',
            unsafe_allow_html=True,
        )

    with right:
        section_header("Advance vs Decline (Last 15 Sessions)")
        adv_dec = sample_data.get_advance_decline_history()
        fig = go.Figure()
        fig.add_bar(x=adv_dec["Date"], y=adv_dec["Advances"], name="Advances",
                    marker_color=COLORS["positive"])
        fig.add_bar(x=adv_dec["Date"], y=adv_dec["Declines"], name="Declines",
                    marker_color=COLORS["negative"])
        fig.update_layout(barmode="stack")
        st.plotly_chart(style_fig(fig, height=300), width="stretch")

    # ---- Market breadth KPIs ---------------------------------------------
    section_header("Market Breadth")
    breadth = sample_data.get_market_breadth()
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        kpi_card("Advances", f'{breadth["advances"]:,}', delta_dir="up", delta="Gainers")
    with b2:
        kpi_card("Declines", f'{breadth["declines"]:,}', delta_dir="down", delta="Losers")
    with b3:
        kpi_card("Unchanged", f'{breadth["unchanged"]:,}', delta="Flat", delta_dir="flat")
    with b4:
        kpi_card("Breadth Ratio", f'{breadth["breadth_pct"]:.1f}%',
                 delta="Adv / (Adv+Dec)", delta_dir="up")

    st.write("")

    # ---- Sector heatmap ---------------------------------------------------
    section_header("Sector Performance Heatmap")
    sectors = sample_data.get_sector_performance().sort_values("% Change")
    heat = px.bar(
        sectors,
        x="% Change",
        y="Sector",
        orientation="h",
        color="% Change",
        color_continuous_scale=["#dc2626", "#f1f5f9", "#16a34a"],
        color_continuous_midpoint=0,
        text="% Change",
    )
    heat.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    heat.update_layout(coloraxis_showscale=False)
    st.plotly_chart(style_fig(heat, height=420), width="stretch")

    # ---- Support / resistance --------------------------------------------
    sup_col, res_col = st.columns(2)
    levels = sample_data.get_support_resistance()
    with sup_col:
        section_header("Key Support Levels")
        st.dataframe(
            levels[["Index", "S1", "S2"]].rename(columns={"S1": "Support 1", "S2": "Support 2"}),
            width="stretch",
            hide_index=True,
        )
    with res_col:
        section_header("Key Resistance Levels")
        st.dataframe(
            levels[["Index", "R1", "R2"]].rename(columns={"R1": "Resistance 1", "R2": "Resistance 2"}),
            width="stretch",
            hide_index=True,
        )
