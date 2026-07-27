"""
Sector Intelligence — the first V2 dashboard page.

Read-only over intelligence_v2.contracts.sector_intelligence. No calculation
happens here — this module only formats and displays what the contract layer
already computed. Reuses the project's shared `components.py` presentation
kit (KPI cards, badges, plot styling) for visual consistency with V1's pages
— that file is a UI kit, not V1 business logic, so sharing it does not
violate the V1 isolation principle (see docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §0).
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from components import badge, kpi_card, section_header, style_fig
from intelligence_v2.contracts import sector_intelligence as contracts

_STATE_BADGE_KIND = {
    "Strong Leader": "green", "Early Momentum": "green", "Improving": "amber",
    "Sideways": "gray", "Weakening": "amber", "Downtrend": "red", "Recovery": "blue",
}

_OVERVIEW_DISPLAY = {
    "sector": "Sector", "state": "State", "days_in_state": "Days in State",
    "rs_1w": "RS 1W %", "rs_1m": "RS 1M %", "rs_3m": "RS 3M %",
    "above_20_sma": "Above 20-SMA", "above_200_sma": "Above 200-SMA",
    "consistency_pct": "Consistency %", "data_method": "Method",
}

_PERF_DISPLAY = {
    "sector": "Sector", "state": "State",
    "perf_1w": "Perf 1W %", "perf_1m": "Perf 1M %", "perf_3m": "Perf 3M %",
    "perf_6m": "Perf 6M %", "perf_1y": "Perf 1Y %",
    "rs_1w": "RS 1W %", "rs_1m": "RS 1M %", "rs_3m": "RS 3M %",
    "rs_6m": "RS 6M %", "rs_1y": "RS 1Y %",
}


def _pct_cols(cols: list[str]) -> dict:
    return {c: st.column_config.NumberColumn(format="%.2f%%") for c in cols}


def render() -> None:
    st.title("🔥 Sector Intelligence")
    st.caption("Multi-horizon sector rotation — 1W / 1M / 3M / 6M / 1Y · "
              "rule-based 7-state classification · read-only over market_v2.db")

    if not contracts.is_data_available():
        st.info("No Sector Intelligence data yet. Run `python run_v2_sector_intelligence.py`.")
        return

    fresh = contracts.get_freshness()
    badge_kind = "green" if fresh["days_of_history"] >= 5 else "amber"
    st.markdown(badge(
        f"Sector Intelligence: {fresh['latest_date']} "
        f"({fresh['days_of_history']} day(s) of history accumulated)", badge_kind),
        unsafe_allow_html=True)
    if fresh["days_of_history"] < fresh["consistency_lookback_days"]:
        st.caption(
            f"ℹ️ Consistency % is measured over a trailing "
            f"{fresh['consistency_lookback_days']}-day window; only "
            f"{fresh['days_of_history']} day(s) exist so far, so today's "
            f"consistency values will be low/zero until more history accumulates. "
            f"This is expected for a freshly-launched module, not a data error."
        )
    st.write("")

    dist = contracts.get_state_distribution()
    dist_map = dict(zip(dist["state"], dist["count"])) if not dist.empty else {}
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Sectors Tracked", str(len(contracts.get_sector_list())))
    with c2:
        kpi_card("Strong Leader", str(dist_map.get("Strong Leader", 0)), delta_dir="up")
    with c3:
        kpi_card("Early Momentum / Improving",
                 str(dist_map.get("Early Momentum", 0) + dist_map.get("Improving", 0)),
                 delta_dir="up")
    with c4:
        kpi_card("Downtrend / Weakening",
                 str(dist_map.get("Downtrend", 0) + dist_map.get("Weakening", 0)),
                 delta_dir="down")

    st.write("")

    tab_overview, tab_performance, tab_history, tab_cycle = st.tabs(
        ["Overview", "Performance", "History", "Market Cycle"])

    with tab_overview:
        _render_overview()
    with tab_performance:
        _render_performance()
    with tab_history:
        _render_history()
    with tab_cycle:
        _render_cycle_placeholder()


def _render_overview() -> None:
    section_header("Sector States")
    df = contracts.get_overview()
    if df.empty:
        st.caption("_No data._")
        return
    view = df[list(_OVERVIEW_DISPLAY)].rename(columns=_OVERVIEW_DISPLAY)
    st.dataframe(
        view, width="stretch", hide_index=True,
        column_config={
            **_pct_cols(["RS 1W %", "RS 1M %", "RS 3M %", "Consistency %"]),
            "State": st.column_config.Column(
                help="7-state rule-based classification — see docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §1.5"),
            "Method": st.column_config.Column(
                help="Sector series source: equal-weighted basket average from V1's stored price history."),
        },
    )
    st.caption("Rows sorted Strong Leader → Recovery. No scoring — this is a rule-based label, not a rank.")


def _render_performance() -> None:
    section_header("Multi-Horizon Performance & Relative Strength")
    df = contracts.get_performance_table()
    if df.empty:
        st.caption("_No data._")
        return
    view = df[list(_PERF_DISPLAY)].rename(columns=_PERF_DISPLAY)
    st.dataframe(
        view, width="stretch", hide_index=True,
        column_config=_pct_cols([c for c in _PERF_DISPLAY.values() if c != "Sector" and c != "State"]),
    )

    st.write("")
    section_header("1-Month Relative Strength by Sector")
    plot_df = df.dropna(subset=["rs_1m"]).sort_values("rs_1m")
    if not plot_df.empty:
        fig = px.bar(plot_df, x="rs_1m", y="sector", orientation="h", color="state",
                    color_discrete_map={
                        "Strong Leader": "#22c55e", "Early Momentum": "#22c55e",
                        "Improving": "#ca8a04", "Sideways": "#64748b",
                        "Weakening": "#ca8a04", "Downtrend": "#dc2626", "Recovery": "#2563eb",
                    },
                    labels={"rs_1m": "RS 1M %", "sector": ""})
        st.plotly_chart(style_fig(fig, height=420), width="stretch")


def _render_history() -> None:
    section_header("Sector History")
    sectors = contracts.get_sector_list()
    sel = st.selectbox("Sector", sectors)
    hist = contracts.get_sector_history(sel)
    if hist.empty:
        st.caption("_No history yet for this sector._")
        return

    fig = px.line(hist, x="trade_date", y="rs_1m", markers=True,
                 labels={"trade_date": "Date", "rs_1m": "RS 1M %"},
                 title=f"{sel} — 1-Month Relative Strength vs Nifty")
    st.plotly_chart(style_fig(fig, height=340), width="stretch")

    cols = {"trade_date": "Date", "close": "Close (rebased)", "rs_1w": "RS 1W %",
           "rs_1m": "RS 1M %", "rs_3m": "RS 3M %", "state": "State",
           "days_in_state": "Days in State"}
    st.dataframe(
        hist[list(cols)].rename(columns=cols).sort_values("Date", ascending=False),
        width="stretch", hide_index=True,
        column_config=_pct_cols(["RS 1W %", "RS 1M %", "RS 3M %"]),
    )


def _render_cycle_placeholder() -> None:
    section_header("Market Cycle")
    st.success(
        "✅ **Built in Phase 2.** The Market Cycle engine (7-stage wheel — "
        "Accumulation → Early Momentum → Strong Trend → Mature Trend → "
        "Distribution → Weak Trend → Recovery) now lives on its own page: "
        "select **🔄 Market Cycle (V2)** in the sidebar."
    )
    st.caption("This tab is kept as a signpost only — all cycle logic and display "
              "live in the dedicated page, not here.")
