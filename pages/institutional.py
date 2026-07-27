"""Dashboard page: Institutional Watchlist (FII/DII + sector rotation)."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from components import COLORS, COLUMN_HELP, kpi_card, section_header, style_fig
from data import contracts

_TREND_COLORS = {"Strong": COLORS["positive"], "Improving": "#65a30d",
                 "Neutral": COLORS["neutral"], "Weak": COLORS["negative"]}


def render() -> None:
    st.title("🏦 Institutional Watchlist")
    st.caption("FII/DII flows + rule-based sector rotation · real data")

    # ---- FII/DII flow summary --------------------------------------------
    flows = contracts.fii_dii(limit=10)
    section_header("Market Flow Summary")
    if flows.empty:
        st.info("No FII/DII data yet. Run `python run_institutional.py`.")
    else:
        latest = flows.iloc[-1]
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi_card("FII Net (₹ Cr)", f'{latest["fii_net"]:,.0f}',
                     delta_dir="up" if latest["fii_net"] >= 0 else "down",
                     delta="Foreign")
        with c2:
            kpi_card("DII Net (₹ Cr)", f'{latest["dii_net"]:,.0f}',
                     delta_dir="up" if latest["dii_net"] >= 0 else "down",
                     delta="Domestic")
        with c3:
            kpi_card("As of", latest["trade_date"].strftime("%d %b %Y"),
                     delta=f"{len(flows)} session(s)", delta_dir="flat")

    # ---- Sector rotation --------------------------------------------------
    sec_dates = contracts.distinct_dates("sector_rotation", "trade_date")
    if sec_dates:
        sel = st.selectbox("Date", sec_dates, format_func=lambda d: d.strftime("%d %b %Y"))
        rot = contracts.sector_rotation(sel)
        section_header("Sector Rotation")
        if not rot.empty:
            rot = rot.sort_values("rs_vs_nifty", ascending=False)
            fig = px.bar(rot, x="rs_vs_nifty", y="sector", orientation="h",
                         color="trend_status", color_discrete_map=_TREND_COLORS,
                         labels={"rs_vs_nifty": "RS vs Nifty (20D)", "sector": ""})
            st.plotly_chart(style_fig(fig, height=420), width="stretch")
    else:
        rot = contracts.sector_rotation()

    # ---- Institutional watchlist -----------------------------------------
    inst_dates = contracts.distinct_dates("institutional_watchlist", "trade_date")
    if not inst_dates:
        st.info("No institutional watchlist yet. Run `python run_institutional.py`.")
        return
    idate = inst_dates[0]
    df = contracts.institutional_watchlist(idate)
    if df.empty:
        return

    section_header(f"Institutional Watchlist — {idate.strftime('%d %b %Y')}")
    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card("Stocks", str(len(df)))
    with k2:
        kpi_card("Strong Sector", str(int((df["sector_trend"] == "Strong").sum())),
                 delta="Leadership", delta_dir="up")
    with k3:
        kpi_card("Strong RS", str(int((df["relative_strength"] == "Strong").sum())),
                 delta="vs Nifty", delta_dir="up")

    trends = st.multiselect("Sector Trend", sorted(df["sector_trend"].dropna().unique()),
                            placeholder="All")
    view = df.copy()
    view["near_breakout"] = view["dist_52w_high_pct"].map(contracts.near_breakout_label)
    if trends:
        view = view[view["sector_trend"].isin(trends)]
    cols = {"symbol": "Symbol", "sector": "Sector", "sector_trend": "Sector Trend",
            "relative_strength": "Rel. Strength", "above_20_sma": "Above 20 SMA",
            "current_price": "Price", "sma_20": "20 SMA", "high_52w": "52W High",
            "low_52w": "52W Low", "dist_52w_high_pct": "↓ High %",
            "dist_52w_low_pct": "↑ Low %", "near_breakout": "Breakout"}
    st.dataframe(
        view[list(cols)].rename(columns=cols), width="stretch", hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="%.2f"),
            "20 SMA": st.column_config.NumberColumn(format="%.2f"),
            "52W High": st.column_config.NumberColumn(format="%.2f"),
            "52W Low": st.column_config.NumberColumn(format="%.2f"),
            "↓ High %": st.column_config.NumberColumn(format="%.1f%%",
                                                      help=COLUMN_HELP["↓ High %"]),
            "↑ Low %": st.column_config.NumberColumn(format="%.1f%%",
                                                     help=COLUMN_HELP["↑ Low %"]),
            "Sector Trend": st.column_config.Column(help=COLUMN_HELP["Sector Trend"]),
            "Rel. Strength": st.column_config.Column(help=COLUMN_HELP["Rel. Strength"]),
            "Above 20 SMA": st.column_config.Column(help=COLUMN_HELP["Above 20 SMA"]),
            "Breakout": st.column_config.Column(help=COLUMN_HELP["Breakout"]),
        },
    )
