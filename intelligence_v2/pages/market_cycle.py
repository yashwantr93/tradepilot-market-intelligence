"""
Market Cycle — the Phase 2 dashboard page.

Three tabs: Current Market · Sector Cycle · Transition History.
Read-only over intelligence_v2.contracts.market_cycle; no calculation here.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from components import badge, kpi_card, section_header, style_fig
from intelligence_v2.contracts import market_cycle as contracts

# Stage -> badge colour. Bullish stages green, topping/warning amber, weak red,
# early/basing blue — consistent with the project's existing colour language.
_STAGE_KIND = {
    "Accumulation": "blue", "Early Momentum": "green", "Strong Trend": "green",
    "Mature Trend": "amber", "Distribution": "amber", "Weak Trend": "red",
    "Recovery": "blue",
}
_STAGE_COLOR = {
    "Accumulation": "#2563eb", "Early Momentum": "#22c55e", "Strong Trend": "#16a34a",
    "Mature Trend": "#ca8a04", "Distribution": "#f59e0b", "Weak Trend": "#dc2626",
    "Recovery": "#3b82f6",
}


def render() -> None:
    st.title("🔄 Market Cycle")
    st.caption("Deterministic 7-stage sector cycle — built from Phase 1 Sector "
              "Intelligence · rule-based, no AI / no scoring / no prediction")

    if not contracts.is_data_available():
        st.info("No Market Cycle data yet. Run `python run_v2_market_cycle.py`.")
        return

    meta = contracts.get_cycle_meta()
    st.markdown(
        badge(f"Market Cycle: {meta['latest_date']} "
             f"({meta['days_of_history']} session(s) of cycle history)",
             "green" if meta["days_of_history"] >= 5 else "amber"),
        unsafe_allow_html=True)
    st.caption(
        f"Hysteresis: a stage change commits only when the new stage appears in "
        f"{meta['confirmations']} of the last {meta['dwell_days']} readings — so a "
        "single day's move does not flip a sector.")
    st.write("")

    tab_current, tab_sector, tab_transitions = st.tabs(
        ["Current Market", "Sector Cycle", "Transition History"])

    with tab_current:
        _render_current()
    with tab_sector:
        _render_sector_cycle()
    with tab_transitions:
        _render_transitions()


def _render_current() -> None:
    df = contracts.get_current_market_cycle()
    if df.empty:
        st.caption("_No data._")
        return

    dist = dict(zip(contracts.get_stage_distribution()["stage"],
                   contracts.get_stage_distribution()["count"]))
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Strong / Early Momentum",
                 str(dist.get("Strong Trend", 0) + dist.get("Early Momentum", 0)),
                 delta_dir="up")
    with c2:
        kpi_card("Mature / Distribution",
                 str(dist.get("Mature Trend", 0) + dist.get("Distribution", 0)),
                 delta="Late-stage", delta_dir="flat")
    with c3:
        kpi_card("Weak Trend", str(dist.get("Weak Trend", 0)), delta_dir="down")
    with c4:
        kpi_card("Accumulation / Recovery",
                 str(dist.get("Accumulation", 0) + dist.get("Recovery", 0)),
                 delta="Basing / turning", delta_dir="flat")

    st.write("")
    section_header("Sectors by Cycle Stage")

    pending = df[df["stage"] != df["raw_stage"]]
    if not pending.empty:
        st.caption(
            f"⏳ {len(pending)} sector(s) show a *different* raw reading today than "
            "their confirmed stage — a stage change is pending confirmation. Both "
            "values are shown below so nothing is hidden.")

    cols = {"sector": "Sector", "stage": "Current Stage", "prior_stage": "Previous Stage",
           "days_in_stage": "Days in Stage", "stage_start_date": "Since",
           "raw_stage": "Today's Raw Reading"}
    st.dataframe(
        df[list(cols)].rename(columns=cols), width="stretch", hide_index=True,
        column_config={
            "Current Stage": st.column_config.Column(
                help="Confirmed stage after hysteresis — one of the 7 cycle stages."),
            "Today's Raw Reading": st.column_config.Column(
                help="Unconfirmed threshold result for today. If it differs from the "
                     "confirmed stage, a transition may be building."),
        },
    )

    st.write("")
    section_header("Cycle Distribution")
    dist_df = contracts.get_stage_distribution()
    plot = dist_df[dist_df["count"] > 0]
    if not plot.empty:
        fig = px.bar(plot, x="stage", y="count", color="stage",
                    color_discrete_map=_STAGE_COLOR, labels={"stage": "", "count": "Sectors"})
        fig.update_layout(showlegend=False)
        st.plotly_chart(style_fig(fig, height=320), width="stretch")

    with st.expander("📖 How every stage is decided (full documented rule set)"):
        for rule in contracts.get_rules_doc():
            label = rule["stage"] if rule["stage"] != "FALLBACK" else "Fallback (no rule matched)"
            st.markdown(f"**{rule['order']}. {label}**")
            for cond in rule["conditions"]:
                st.markdown(f"- {cond}")
            st.caption(f"Possible behaviour: {rule['behaviour']}")
        st.caption("Rules are evaluated strictly in this order; the first match wins, "
                  "which is what guarantees exactly one stage per sector.")


def _render_sector_cycle() -> None:
    sectors = contracts.get_sector_list()
    if not sectors:
        st.caption("_No data._")
        return
    sel = st.selectbox("Sector", sectors)

    df = contracts.get_current_market_cycle()
    row = df[df["sector"] == sel]
    if row.empty:
        st.caption("_No current reading for this sector._")
        return
    r = row.iloc[0]

    left, right = st.columns([1, 1.4])
    with left:
        st.markdown(f"### {sel}")
        st.markdown(badge(r["stage"], _STAGE_KIND.get(r["stage"], "gray")),
                   unsafe_allow_html=True)
        st.write("")
        st.markdown(f"**Previous stage:** {r['prior_stage'] or '—'}")
        st.markdown(f"**Days in current stage:** {r['days_in_stage']}")
        st.markdown(f"**Stage started:** {r['stage_start_date'] or '—'}")
        st.markdown(f"**Today's raw reading:** {r['raw_stage']}")
    with right:
        st.markdown("**Reason**")
        for reason in r["reasons"]:
            st.markdown(f"- {reason}")
        if r["possible_behaviour"]:
            st.info(f"**Possible behaviour:** {r['possible_behaviour']}")
        if r["confidence_notes"]:
            st.markdown("**Confidence notes**")
            for note in r["confidence_notes"]:
                st.caption(f"• {note}")

    st.write("")
    section_header(f"{sel} — Stage History")
    hist = contracts.get_sector_cycle_history(sel)
    if hist.empty:
        st.caption("_No history._")
        return

    plot = hist.copy()
    plot["stage_label"] = plot["stage"]
    fig = px.scatter(plot, x="trade_date", y="stage_label", color="stage",
                    color_discrete_map=_STAGE_COLOR,
                    labels={"trade_date": "Date", "stage_label": ""},
                    category_orders={"stage_label": list(contracts.get_cycle_meta()["stages"])})
    fig.update_traces(marker=dict(size=13))
    fig.update_layout(showlegend=False)
    st.plotly_chart(style_fig(fig, height=320), width="stretch")

    hcols = {"trade_date": "Date", "stage": "Confirmed Stage", "raw_stage": "Raw Reading",
            "days_in_stage": "Days in Stage"}
    st.dataframe(
        hist[list(hcols)].rename(columns=hcols).sort_values("Date", ascending=False),
        width="stretch", hide_index=True)


def _render_transitions() -> None:
    section_header("Confirmed Stage Transitions")
    st.caption("Only CONFIRMED changes are logged here — readings that failed "
              "hysteresis confirmation never become transitions.")

    sectors = ["All"] + contracts.get_sector_list()
    sel = st.selectbox("Filter by sector", sectors, key="transition_sector")
    df = contracts.get_transition_history(None if sel == "All" else sel)

    if df.empty:
        st.info("No confirmed transitions recorded yet.")
        return

    view = df.copy()
    view["Transition"] = view["from_stage"].fillna("—") + "  →  " + view["to_stage"]
    view["Reason"] = view["reasons"].map(lambda rs: " · ".join(rs) if rs else "—")
    cols = {"transition_date": "Date", "sector": "Sector", "Transition": "Transition",
           "days_in_previous_stage": "Days in Previous Stage", "Reason": "Reason"}
    st.dataframe(
        view[list(cols)].rename(columns=cols), width="stretch", hide_index=True,
        column_config={"Reason": st.column_config.TextColumn(width="large")},
    )
