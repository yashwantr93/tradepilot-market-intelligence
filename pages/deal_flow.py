"""Dashboard page: Deal Flow Watchlist (bulk/block deal candidates)."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from components import COLORS, COLUMN_HELP, kpi_card, section_header, style_fig
from data import contracts

_DISPLAY = {
    "symbol": "Symbol", "sector": "Sector", "catalyst_tag": "Catalyst",
    "current_price": "Price", "sma_20": "20 SMA", "high_52w": "52W High",
    "low_52w": "52W Low", "relative_strength": "Rel. Strength",
    "above_20_sma": "Above 20 SMA", "volume_expansion": "Vol Expansion",
    "dist_52w_high_pct": "↓ High %", "dist_52w_low_pct": "↑ Low %",
    "near_breakout": "Breakout", "technical_status": "Technical Status",
}


def render() -> None:
    st.title("📈 Deal Flow Watchlist")
    st.caption("Bulk & block-deal candidates with rule-based technicals · real data")

    dates = contracts.distinct_dates("daily_watchlist", "trade_date")
    if not dates:
        st.info("No deal-flow data yet. Run `python run_live.py` to populate it.")
        return

    sel = st.selectbox("Trade date", dates, format_func=lambda d: d.strftime("%d %b %Y"))
    df = contracts.deal_watchlist(sel)
    if df.empty:
        st.warning("No rows for the selected date.")
        return

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Candidates", str(len(df)))
    with c2:
        kpi_card("Ready", str(int((df["technical_status"] == "Ready").sum())),
                 delta="Technical setup", delta_dir="up")
    with c3:
        kpi_card("Strong RS", str(int((df["relative_strength"] == "Strong").sum())),
                 delta="vs Nifty", delta_dir="up")
    with c4:
        kpi_card("Volume Expansion", str(int((df["volume_expansion"] == "Y").sum())),
                 delta="Above avg vol", delta_dir="up")

    st.write("")

    # Filters
    f1, f2 = st.columns(2)
    with f1:
        statuses = st.multiselect("Technical Status",
                                  sorted(df["technical_status"].dropna().unique()),
                                  placeholder="All")
    with f2:
        rs = st.multiselect("Relative Strength",
                            sorted(df["relative_strength"].dropna().unique()),
                            placeholder="All")
    view = df.copy()
    view["near_breakout"] = view["dist_52w_high_pct"].map(contracts.near_breakout_label)
    if statuses:
        view = view[view["technical_status"].isin(statuses)]
    if rs:
        view = view[view["relative_strength"].isin(rs)]

    section_header("Watchlist")
    st.dataframe(
        view[list(_DISPLAY)].rename(columns=_DISPLAY),
        width="stretch", hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="%.2f"),
            "20 SMA": st.column_config.NumberColumn(format="%.2f"),
            "52W High": st.column_config.NumberColumn(format="%.2f"),
            "52W Low": st.column_config.NumberColumn(format="%.2f"),
            "↓ High %": st.column_config.NumberColumn(format="%.1f%%",
                                                      help=COLUMN_HELP["↓ High %"]),
            "↑ Low %": st.column_config.NumberColumn(format="%.1f%%",
                                                     help=COLUMN_HELP["↑ Low %"]),
            "Rel. Strength": st.column_config.Column(help=COLUMN_HELP["Rel. Strength"]),
            "Above 20 SMA": st.column_config.Column(help=COLUMN_HELP["Above 20 SMA"]),
            "Breakout": st.column_config.Column(help=COLUMN_HELP["Breakout"]),
        },
    )

    section_header("Technical Status Breakdown")
    counts = df["technical_status"].value_counts().rename_axis("Status").reset_index(name="Count")
    fig = px.bar(counts, x="Status", y="Count", color="Status",
                 color_discrete_map={"Ready": COLORS["positive"],
                                     "Monitor": COLORS["neutral"],
                                     "Avoid": COLORS["negative"]})
    fig.update_layout(showlegend=False)
    st.plotly_chart(style_fig(fig, height=300), width="stretch")
