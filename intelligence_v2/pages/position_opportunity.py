"""
Position Opportunities — the Phase 5 dashboard page.

Four tabs: High Conviction · Position Candidates · Accumulation Watch · History.
Read-only over intelligence_v2.contracts.position_opportunity; no calculation here.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components import badge, kpi_card, section_header, style_fig
from intelligence_v2.contracts import position_opportunity as contracts

_CATEGORY_KIND = {
    "High Conviction Position": "green", "Position Candidate": "amber",
    "Accumulation Watch": "blue", "Not Qualified": "gray",
}
_CATEGORY_COLOR = {
    "High Conviction Position": "#22c55e", "Position Candidate": "#ca8a04",
    "Accumulation Watch": "#2563eb", "Not Qualified": "#64748b",
}

_TABLE_COLS = {
    "rank_in_category": "Rank", "symbol": "Stock", "sector": "Sector",
    "sector_state": "Sector State", "cycle_stage": "Market Cycle",
    "early_momentum_category": "Early Momentum (P3)",
    "rs_3m": "RS 3M %", "rs_slope": "RS Trend", "signal_count": "Signals",
    "close": "Price",
}


def render() -> None:
    st.title("🧭 Position Opportunities")
    st.caption("Stocks showing objective, measurable signs of medium-to-long-term "
              "position suitability — a research lens, not an execution signal")

    if not contracts.is_data_available():
        st.info("No Position Opportunity data yet. Run `python run_v2_position_opportunity.py`.")
        return

    meta = contracts.get_meta()
    st.markdown(
        badge(f"Position Opportunities: {meta['latest_date']} "
             f"({meta['days_of_history']} session(s) of history)", "green"),
        unsafe_allow_html=True)

    counts = contracts.get_category_counts()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("High Conviction", str(counts.get("High Conviction Position", 0)),
                 delta="Complete evidence", delta_dir="up")
    with c2:
        kpi_card("Position Candidates", str(counts.get("Position Candidate", 0)),
                 delta="Trend building", delta_dir="up")
    with c3:
        kpi_card("Accumulation Watch", str(counts.get("Accumulation Watch", 0)),
                 delta="One early sign", delta_dir="flat")
    with c4:
        kpi_card("Universe Scanned", str(meta["universe_size"]),
                 delta=f"{meta['sector_mapped']} with sector context", delta_dir="flat")

    if meta["sector_mapped"] < meta["universe_size"]:
        st.caption(
            f"ℹ️ **Known limitation:** only **{meta['sector_mapped']} of "
            f"{meta['universe_size']}** scanned stocks belong to one of the 12 sectors "
            "that Phase 1 / Phase 2 classify. The remaining stocks cannot earn the "
            "*Sector strength* or *Bullish market cycle* signals, but can still reach "
            "**High Conviction Position** via a Phase 3 Early Momentum confirmation, "
            "or qualify as Position Candidate / Accumulation Watch on their own "
            "price/trend evidence.")

    st.write("")
    tabs = st.tabs(["High Conviction", "Position Candidates", "Accumulation Watch", "History"])
    with tabs[0]:
        _render_category("High Conviction Position")
    with tabs[1]:
        _render_category("Position Candidate")
    with tabs[2]:
        _render_category("Accumulation Watch")
    with tabs[3]:
        _render_history()


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ("sector", "sector_state", "cycle_stage", "early_momentum_category"):
        out[col] = out[col].fillna("—")
    return out[list(_TABLE_COLS)].rename(columns=_TABLE_COLS)


def _render_category(category: str) -> None:
    df = contracts.get_category(category)
    section_header(f"{category} ({len(df)})")
    st.caption(contracts.get_category_meaning(category))

    if df.empty:
        st.info(f"No stocks currently qualify as **{category}**.")
        return

    st.dataframe(
        _prep(df), width="stretch", hide_index=True,
        column_config={
            "Rank": st.column_config.NumberColumn(
                help="Rank WITHIN this category only — never comparable across categories."),
            "RS 3M %": st.column_config.NumberColumn(format="%.2f%%"),
            "RS Trend": st.column_config.NumberColumn(
                format="%.2f",
                help="Change in 1-month relative strength over the last 20 sessions. "
                     "Positive = Relative Strength improving."),
            "Signals": st.column_config.NumberColumn(
                help="Count of the nine signals satisfied. Shown for explainability, not "
                     "used as a ranking key."),
            "Price": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    st.write("")
    section_header("Supporting Evidence")
    symbols = df["symbol"].tolist()
    sel = st.selectbox("Stock", symbols, key=f"detail_{category}")
    row = df[df["symbol"] == sel].iloc[0]

    left, right = st.columns([1, 1.3])
    with left:
        st.markdown(f"### {sel}")
        st.markdown(badge(row["category"], _CATEGORY_KIND.get(row["category"], "gray")),
                   unsafe_allow_html=True)
        st.write("")
        sector_val = row['sector'] if pd.notna(row['sector']) else '— (not in a tracked sector)'
        state_val = row['sector_state'] if pd.notna(row['sector_state']) else '—'
        cycle_val = row['cycle_stage'] if pd.notna(row['cycle_stage']) else '—'
        em_val = row['early_momentum_category'] if pd.notna(row['early_momentum_category']) else '—'
        sma50_val = row['above_50_sma'] if pd.notna(row['above_50_sma']) else '—'
        sma200_val = row['above_200_sma'] if pd.notna(row['above_200_sma']) else '—'
        st.markdown(f"**Sector:** {sector_val}")
        st.markdown(f"**Sector state:** {state_val}")
        st.markdown(f"**Market Cycle:** {cycle_val}")
        st.markdown(f"**Early Momentum (Phase 3):** {em_val}")
        rs = row["rs_3m"]
        st.markdown(f"**Relative Strength (3M):** {rs:+.2f}%" if pd.notna(rs) else
                   "**Relative Strength (3M):** n/a")
        st.markdown(f"**Trend status:** above 50-SMA: {sma50_val} · above 200-SMA: {sma200_val}")
        st.markdown(f"**Rank in category:** #{row['rank_in_category']}")
        st.caption(f"Last updated: {row['trade_date']}")
    with right:
        st.markdown("**Reason**")
        st.success(row["category_reason"])
        st.markdown(f"**Supporting signals ({len(row['reasons'])} of 9)**")
        for reason in row["reasons"]:
            st.markdown(f"- ✅ {reason}")
        if row["missing"]:
            with st.expander(f"Not satisfied ({len(row['missing'])})"):
                for miss in row["missing"]:
                    st.markdown(f"- ⬜ {miss}")

    with st.expander("📖 How categories, signals and ranking are decided"):
        st.markdown("**The nine signals**")
        for sig in contracts.get_signal_definitions():
            st.markdown(f"- **{sig['label']}** — {sig['rule']}")
        st.markdown("**Categories** (evaluated in order; first match wins, so every "
                   "stock lands in exactly one)")
        for rule in contracts.get_category_rules():
            st.markdown(f"**{rule['order']}. {rule['category']}**")
            for cond in rule["conditions"]:
                st.markdown(f"- {cond}")
        st.markdown("**Ranking** (applied separately inside each category)")
        st.code(contracts.get_ranking_doc(), language="text")
        st.caption("There is deliberately no market-wide score. Ranks are only "
                  "meaningful within a single category.")


def _render_history() -> None:
    section_header("Category Counts Over Time")
    hist = contracts.get_category_history()
    if hist.empty:
        st.caption("_No history._")
    else:
        fig = px.line(hist, x="trade_date", y="count", color="category", markers=True,
                     color_discrete_map=_CATEGORY_COLOR,
                     labels={"trade_date": "Date", "count": "Stocks", "category": ""})
        st.plotly_chart(style_fig(fig, height=340), width="stretch")

    st.write("")
    section_header("Stock History")
    symbols = contracts.get_all_symbols()
    if not symbols:
        return
    sel = st.selectbox("Stock", symbols, key="history_symbol")
    sh = contracts.get_symbol_history(sel)
    if sh.empty:
        st.caption("_No history for this stock._")
        return

    cols = {"trade_date": "Date", "category": "Category", "rank_in_category": "Rank",
           "signal_count": "Signals", "rs_3m": "RS 3M %", "rs_slope": "RS Trend",
           "close": "Price"}
    st.dataframe(
        sh[list(cols)].rename(columns=cols).sort_values("Date", ascending=False),
        width="stretch", hide_index=True,
        column_config={
            "RS 3M %": st.column_config.NumberColumn(format="%.2f%%"),
            "RS Trend": st.column_config.NumberColumn(format="%.2f"),
            "Price": st.column_config.NumberColumn(format="%.2f"),
        },
    )
