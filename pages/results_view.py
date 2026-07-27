"""Dashboard page: Results Watchlist (quarterly earnings)."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from components import COLORS, kpi_card, section_header, style_fig
from data import contracts

_CLS_COLORS = {"Strong": COLORS["positive"], "Neutral": COLORS["neutral"],
               "Weak": COLORS["negative"]}
_CLS_ORDER = {"Strong": 0, "Neutral": 1, "Weak": 2}


def render() -> None:
    st.title("📊 Results Watchlist")
    st.caption("Quarterly earnings, rule-classified by YoY growth · real data")

    periods = contracts.distinct_dates("results_tracker", "period_end")
    if not periods:
        st.info("No results yet. Run `python run_results.py`.")
        return

    sel = st.selectbox("Reporting period (quarter end)", periods,
                       format_func=lambda d: d.strftime("%d %b %Y"))
    df = contracts.results(sel)
    if df.empty:
        st.warning("No rows for the selected period.")
        return

    df["_c"] = df["result_classification"].map(_CLS_ORDER).fillna(9)
    df = df.sort_values(["_c", "profit_growth_pct"], ascending=[True, False])

    quarter = df["quarter"].mode().iloc[0] if not df["quarter"].mode().empty else ""
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Companies", str(len(df)), delta=quarter, delta_dir="flat")
    with c2:
        kpi_card("Strong", str(int((df["result_classification"] == "Strong").sum())),
                 delta_dir="up", delta="Rev & PAT >15%")
    with c3:
        kpi_card("Neutral", str(int((df["result_classification"] == "Neutral").sum())),
                 delta_dir="flat", delta="In between")
    with c4:
        kpi_card("Weak", str(int((df["result_classification"] == "Weak").sum())),
                 delta_dir="down", delta="Contraction")

    st.write("")

    cls = st.multiselect("Result Classification", ["Strong", "Neutral", "Weak"],
                         placeholder="All")
    view = df if not cls else df[df["result_classification"].isin(cls)]

    section_header("Results")
    cols = {"symbol": "Symbol", "quarter": "Quarter",
            "revenue_growth_pct": "Revenue Growth %", "profit_growth_pct": "Profit Growth %",
            "margin_change_pct": "Margin Change %", "result_classification": "Classification",
            "basis": "Basis"}
    st.dataframe(
        view[list(cols)].rename(columns=cols), width="stretch", hide_index=True,
        column_config={
            "Revenue Growth %": st.column_config.NumberColumn(format="%.1f%%"),
            "Profit Growth %": st.column_config.NumberColumn(format="%.1f%%"),
            "Margin Change %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    section_header("Revenue vs Profit Growth")
    plot = df.dropna(subset=["revenue_growth_pct", "profit_growth_pct"])
    if not plot.empty:
        fig = px.scatter(plot, x="revenue_growth_pct", y="profit_growth_pct",
                         color="result_classification", color_discrete_map=_CLS_COLORS,
                         hover_name="symbol",
                         labels={"revenue_growth_pct": "Revenue Growth %",
                                 "profit_growth_pct": "Profit Growth %"})
        fig.add_hline(y=15, line_dash="dot", line_color=COLORS["muted"])
        fig.add_vline(x=15, line_dash="dot", line_color=COLORS["muted"])
        st.plotly_chart(style_fig(fig, height=420), width="stretch")
