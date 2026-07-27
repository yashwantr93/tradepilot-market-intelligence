"""Dashboard page: Combined Watchlist (tiered confluence)."""

from __future__ import annotations

import streamlit as st

from components import COLUMN_HELP, kpi_card, section_header
from data import contracts

_TIER_REASON = {
    1: "Catalyst + Sector Strength alignment",
    2: "Strong sector leadership",
    3: "Event-driven — needs validation",
}


def render() -> None:
    st.title("🎯 Combined Watchlist")
    st.caption("Confluence of Deal Flow + Institutional watchlists, tiered · real data")

    dates = contracts.distinct_dates("combined_watchlist", "trade_date")
    if not dates:
        st.info("No combined watchlist yet. Run `python run_combined.py`.")
        return

    sel = st.selectbox("Trade date", dates, format_func=lambda d: d.strftime("%d %b %Y"))
    df = contracts.combined_enriched(sel)
    if df.empty:
        st.warning("No rows for the selected date.")
        return

    t1, t2, t3 = (int((df["tier"] == t).sum()) for t in (1, 2, 3))
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Total", str(len(df)))
    with c2:
        kpi_card("Tier 1", str(t1), delta="Highest priority", delta_dir="up")
    with c3:
        kpi_card("Tier 2", str(t2), delta="Sector leaders", delta_dir="flat")
    with c4:
        kpi_card("Tier 3", str(t3), delta="Event-driven", delta_dir="flat")

    st.write("")

    cols = {"symbol": "Symbol", "sector": "Sector", "catalyst": "Catalyst",
            "relative_strength": "Rel. Strength", "above_20_sma": "Above 20 SMA",
            "current_price": "Price", "dist_52w_high_pct": "↓ High %",
            "dist_52w_low_pct": "↑ Low %", "near_breakout": "Breakout",
            "technical_status": "Technical Status"}

    for tier in (1, 2, 3):
        sub = df[df["tier"] == tier]
        section_header(f"Tier {tier} — {_TIER_REASON[tier]} ({len(sub)})")
        if sub.empty:
            st.caption("_None for this date._")
            continue
        st.dataframe(
            sub[list(cols)].rename(columns=cols), width="stretch", hide_index=True,
            column_config={
                "Price": st.column_config.NumberColumn(format="%.2f"),
                "↓ High %": st.column_config.NumberColumn(format="%.1f%%",
                                                          help=COLUMN_HELP["↓ High %"]),
                "↑ Low %": st.column_config.NumberColumn(format="%.1f%%",
                                                         help=COLUMN_HELP["↑ Low %"]),
                "Rel. Strength": st.column_config.Column(help=COLUMN_HELP["Rel. Strength"]),
                "Above 20 SMA": st.column_config.Column(help=COLUMN_HELP["Above 20 SMA"]),
                "Breakout": st.column_config.Column(help=COLUMN_HELP["Breakout"]),
            },
        )
