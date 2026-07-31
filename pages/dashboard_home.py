"""
Dashboard — the home page. A single-screen synthesis across every engine
(V1 deal-flow/institutional/sector-rotation + V2 Sector Intelligence / Market
Cycle / Early Momentum / Bearish Opportunity / Position Opportunity) so the
five questions below never require opening more than one page:

  • What is the market doing?
  • Which sectors are strongest / weakest?
  • What opportunities deserve attention?
  • What risks exist today?

Strictly read-only: every figure here comes from an existing contracts.py
getter (V1's data/contracts.py or a V2 intelligence_v2/contracts/*.py module).
No new computation, scoring, ranking, or filter logic lives in this file.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components import badge, kpi_card, section_header
from core.branding import APP_FULL_NAME, TAGLINE
from data import contracts as v1
from intelligence_v2.contracts import bearish_opportunity as v2_bearish
from intelligence_v2.contracts import early_momentum as v2_momentum
from intelligence_v2.contracts import market_cycle as v2_cycle
from intelligence_v2.contracts import position_opportunity as v2_position
from intelligence_v2.contracts import sector_intelligence as v2_sectors

_SECTOR_STRENGTH_ORDER = ("Strong Leader", "Early Momentum", "Improving")
_SECTOR_WEAKNESS_ORDER = ("Downtrend", "Weakening")


def render() -> None:
    st.title("🏠 Dashboard")
    st.caption(TAGLINE)

    if not v1.db_available():
        st.error("No backend database found at `data_store/market.db`.")
        st.markdown(
            "Run the engine pipelines first — see the sidebar for the exact commands.")
        return

    _render_freshness_row()
    st.write("")

    left, right = st.columns([1, 1])
    with left:
        _render_market_cycle_summary()
    with right:
        _render_sector_strength_weakness()

    st.write("")
    _render_opportunities_and_risks()

    st.write("")
    _render_v1_snapshot()


def _render_freshness_row() -> None:
    section_header("Data Freshness")
    items = v1.data_freshness()
    v2_meta = v2_sectors.get_freshness()
    if items:
        cols = st.columns(len(items) + 1)
        for col, item in zip(cols, items):
            with col:
                st.markdown(badge(item["value"], item["kind"]), unsafe_allow_html=True)
        with cols[-1]:
            if v2_meta.get("latest_date"):
                st.markdown(badge(f"V2 Intelligence: {v2_meta['latest_date']}", "blue"),
                           unsafe_allow_html=True)
            else:
                st.markdown(badge("V2 Intelligence: no data yet", "gray"),
                           unsafe_allow_html=True)
    else:
        st.caption("_No V1 data yet — run the engine pipelines._")


def _render_market_cycle_summary() -> None:
    section_header("🔄 What Is the Market Doing?")
    if not v2_cycle.is_data_available():
        st.info("No Market Cycle data yet. Run `python run_v2_market_cycle.py`.")
        return

    dist = v2_cycle.get_stage_distribution()
    meta = v2_cycle.get_cycle_meta()
    st.caption(f"Market Cycle as of {meta.get('latest_date', '—')} "
              f"— {meta.get('days_of_history', 0)} session(s) of history")

    bullish = dist[dist["stage"].isin(
        ("Early Momentum", "Strong Trend", "Accumulation", "Recovery"))]["count"].sum()
    late_or_weak = dist[dist["stage"].isin(
        ("Mature Trend", "Distribution", "Weak Trend"))]["count"].sum()

    c1, c2 = st.columns(2)
    with c1:
        kpi_card("Constructive Stages", str(int(bullish)),
                 delta="Accumulation / Early Momentum / Strong Trend / Recovery",
                 delta_dir="up")
    with c2:
        kpi_card("Late-Stage / Weak", str(int(late_or_weak)),
                 delta="Mature Trend / Distribution / Weak Trend", delta_dir="down")

    st.dataframe(dist.rename(columns={"stage": "Stage", "count": "Sectors"}),
                width="stretch", hide_index=True)


def _render_sector_strength_weakness() -> None:
    section_header("🔥 Strongest & Weakest Sectors")
    if not v2_sectors.is_data_available():
        st.info("No Sector Intelligence data yet. Run `python run_v2_sector_intelligence.py`.")
        return

    ov = v2_sectors.get_overview()
    if ov.empty:
        st.caption("_No sector data available._")
        return

    strong = ov[ov["state"].isin(_SECTOR_STRENGTH_ORDER)].sort_values("rs_1m", ascending=False)
    weak = ov[ov["state"].isin(_SECTOR_WEAKNESS_ORDER)].sort_values("rs_1m")

    st.markdown("**Strongest**")
    if strong.empty:
        st.caption("_No sector currently qualifies as Strong Leader / Early Momentum / Improving._")
    else:
        for _, r in strong.head(5).iterrows():
            st.markdown(f"- **{r['sector']}** — {r['state']} (RS 1M {r['rs_1m']:+.2f}%)"
                       if pd.notna(r['rs_1m']) else f"- **{r['sector']}** — {r['state']}")

    st.markdown("**Weakest**")
    if weak.empty:
        st.caption("_No sector currently qualifies as Downtrend / Weakening._")
    else:
        for _, r in weak.head(5).iterrows():
            st.markdown(f"- **{r['sector']}** — {r['state']} (RS 1M {r['rs_1m']:+.2f}%)"
                       if pd.notna(r['rs_1m']) else f"- **{r['sector']}** — {r['state']}")


def _render_opportunities_and_risks() -> None:
    section_header("🎯 Opportunities & Risks Today")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if v2_momentum.is_data_available():
            counts = v2_momentum.get_category_counts()
            kpi_card("Emerging Leaders", str(counts.get("Emerging Leader", 0)),
                     delta="Early Momentum (V2)", delta_dir="up",
                     help="Phase 3: complete bullish evidence set.")
        else:
            kpi_card("Emerging Leaders", "—", delta="No data yet", delta_dir="flat")
    with c2:
        if v2_position.is_data_available():
            counts = v2_position.get_category_counts()
            kpi_card("High Conviction Position", str(counts.get("High Conviction Position", 0)),
                     delta="Position Opportunities (V2)", delta_dir="up",
                     help="Phase 5: sustained medium/long-term trend + backdrop.")
        else:
            kpi_card("High Conviction Position", "—", delta="No data yet", delta_dir="flat")
    with c3:
        if v2_bearish.is_data_available():
            counts = v2_bearish.get_category_counts()
            kpi_card("High Conviction Bearish", str(counts.get("High Conviction Bearish", 0)),
                     delta="Bearish Opportunities (V2)", delta_dir="down",
                     help="Phase 4: complete bearish evidence set — research risk, not a signal.")
        else:
            kpi_card("High Conviction Bearish", "—", delta="No data yet", delta_dir="flat")
    with c4:
        hub = v1.opportunity_hub()
        avoid_n = int((hub["action"] == "Avoid").sum()) if not hub.empty else 0
        kpi_card("V1 Avoid-Flagged", str(avoid_n), delta="Daily Opportunity Hub",
                 delta_dir="down", help="Below trend & weak — not research candidates today.")

    st.caption("Every count above links to its own page for full explainability "
              "(reasons, supporting signals, ranking) — use the sidebar to open it.")


def _render_v1_snapshot() -> None:
    section_header("📈 Today's V1 Snapshot")
    hub = v1.opportunity_hub()
    if hub.empty:
        st.caption("_No Daily Opportunity Hub data yet — run the V1 pipelines._")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Priority A", str(int((hub["priority"] == "A").sum())),
                 delta="Highest conviction", delta_dir="up")
    with c2:
        kpi_card("Ready to Act", str(int((hub["action"] == "Ready").sum())),
                 delta="Clean setup", delta_dir="up")
    with c3:
        strong = v1.strong_sectors_summary()
        st.markdown("**Today's Strong Sectors (V1)**")
        if strong["strong"] or strong["improving"]:
            st.write(", ".join(strong["strong"] + strong["improving"]))
        else:
            st.caption("_None currently._")

    st.caption("Open **🎯 Daily Opportunity Hub** in the sidebar for the full, "
              "stock-level decision table.")
