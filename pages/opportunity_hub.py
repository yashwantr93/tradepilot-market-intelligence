"""
Daily Opportunity Hub — the decision-support landing page.

Shows the top actionable opportunities first, with deterministic rule-based
Priority (A/B/C) and Action (Ready/Research/Watch/Avoid), so a swing trader can
scan the best ideas in under two minutes. Read-only over the existing engine
tables — no scoring, no ML, no backend changes.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components import COLUMN_HELP, badge, kpi_card, section_header
from core.branding import APP_FULL_NAME
from data import contracts

# Emoji cues keep the table scannable without HTML.
_ACTION_LABEL = {"Ready": "🟢 Ready", "Research": "🟡 Research",
                 "Watch": "🔵 Watch", "Avoid": "⚪ Avoid"}
_PRIORITY_LABEL = {"A": "🅰 A", "B": "🅱 B", "C": "🅲 C"}

# Compact decision table — only what drives a "open this chart?" decision.
_DISPLAY = {
    "symbol": "Symbol", "sector": "Sector", "priority": "Priority",
    "action": "Action", "setup_quality": "Setup", "near_breakout": "Breakout",
    "results_status": "Results", "corp_action_status": "Corp Action",
    "action_cue": "Do Now",
}

# Action -> accent colour for the Today's Focus cards.
_ACTION_ACCENT = {"Ready": "#22c55e", "Research": "#ca8a04",
                  "Watch": "#2563eb", "Avoid": "#f87171"}
_ACTION_BADGE_KIND = {"Ready": "green", "Research": "amber",
                      "Watch": "blue", "Avoid": "red"}

# Full price-metric set (shared logic, now available for every stock).
_METRICS = {
    "symbol": "Symbol", "current_price": "Price", "sma_20": "20 SMA",
    "high_52w": "52W High", "low_52w": "52W Low",
    "dist_52w_high_pct": "↓ from High %", "dist_52w_low_pct": "↑ from Low %",
    "near_breakout": "Breakout",
}


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["priority"] = out["priority"].map(_PRIORITY_LABEL).fillna(out["priority"])
    out["action"] = out["action"].map(_ACTION_LABEL).fillna(out["action"])
    return out[list(_DISPLAY)].rename(columns=_DISPLAY)


def _table(df: pd.DataFrame) -> None:
    cfg = {name: st.column_config.Column(help=COLUMN_HELP[name])
           for name in _DISPLAY.values() if name in COLUMN_HELP}
    cfg["Do Now"] = st.column_config.TextColumn("Do Now", width="medium",
                                                help=COLUMN_HELP["Do Now"])
    st.dataframe(_prep(df), width="stretch", hide_index=True, column_config=cfg)


# Action -> the native Streamlit status box used for the directive.
def _cue_box(action: str):
    return {"Ready": st.success, "Research": st.warning,
            "Watch": st.info, "Avoid": st.error}.get(action, st.info)


def _focus_cards(focus: pd.DataFrame) -> None:
    """Render the Today's Focus picks as native cards (no raw HTML).

    Built entirely from Streamlit components so raw HTML can never leak through.
    """
    for col, (_, r) in zip(st.columns(len(focus)), focus.iterrows()):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {r['symbol']}")
                st.caption(r["sector"])
                if r["setup_quality"] != "—":
                    st.markdown(r["setup_quality"])
                st.caption(f"**Why:** {r['setup_reason']}")
                _cue_box(r["action"])(f"**{r['action_cue']}**")
                if r.get("corp_action_status") and r["corp_action_status"] != "—":
                    st.caption(f"**Catalyst:** {r['corp_action_status']}")
                st.caption(f"✅ **Check:** {r['chart_check']}")


_WHYNOT_DISPLAY = {
    "symbol": "Symbol", "sector": "Sector", "action": "Action",
    "setup_quality": "Setup", "why_not": "Why Not Selected",
}


def _table_whynot(df: pd.DataFrame) -> None:
    out = df.copy()
    out["action"] = out["action"].map(_ACTION_LABEL).fillna(out["action"])
    st.dataframe(
        out[list(_WHYNOT_DISPLAY)].rename(columns=_WHYNOT_DISPLAY),
        width="stretch", hide_index=True,
        column_config={
            "Why Not Selected": st.column_config.TextColumn(
                width="large", help="The rule gates this stock did not satisfy."),
            "Setup": st.column_config.Column(help=COLUMN_HELP["Setup"]),
        },
    )


def render() -> None:
    st.title("🎯 Daily Opportunity Hub")
    st.caption(f"{APP_FULL_NAME} · rule-based research candidates "
               "(~1–8 week horizon) · real data, no AI / no buy-sell calls")

    df = contracts.opportunity_hub()
    if df.empty:
        st.info("No opportunities yet. Run the engine pipelines, then reload.")
        return

    # ---- Data freshness badges -------------------------------------------
    fresh = contracts.data_freshness()
    st.markdown(" ".join(badge(f["value"], f["kind"]) for f in fresh),
                unsafe_allow_html=True)
    st.write("")

    # ---- Headline KPIs (high-contrast, with tooltips) --------------------
    a = int((df["priority"] == "A").sum())
    ready = int((df["action"] == "Ready").sum())
    strong_res = int((df["results_status"] == "Strong").sum())
    avoid = int((df["action"] == "Avoid").sum())
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Priority A", str(a), delta="Highest conviction", delta_dir="up",
                 help="Stocks meeting the strictest rule set — open these first.")
    with c2:
        kpi_card("Ready to Act", str(ready), delta="Clean setup", delta_dir="up",
                 help="Above 20-SMA, near breakout, results not weak — a clean chart to inspect now.")
    with c3:
        kpi_card("Strong Results", str(strong_res), delta="Fundamental backing",
                 delta_dir="up", help="Latest quarter: revenue & profit both grew ≥15% YoY.")
    with c4:
        kpi_card("Avoid", str(avoid), delta="Weak — skip", delta_dir="down",
                 help="Below trend and weak — not research candidates today.")

    st.write("")

    # ---- Today's Strong Sectors (institutional sector-rotation data) ------
    ss = contracts.strong_sectors_summary()
    if ss["strong"] or ss["improving"]:
        section_header("🔥 Today's Strong Sectors")
        items = [(s, "green") for s in ss["strong"]] + \
                [(s, "amber") for s in ss["improving"]]
        st.markdown(" ".join(badge(t, k) for t, k in items), unsafe_allow_html=True)
        st.caption("Strong (green) / Improving (amber) sectors by relative strength vs "
                   "Nifty — favour setups that sit in these sectors.")
        st.write("")

    # ---- Today's Focus — open these charts first -------------------------
    focus = contracts.todays_focus(df, n=5)
    section_header("🔭 Today's Focus — open these charts first")
    st.caption("Your 2-minute shortlist. **Open these 3–5 charts → apply your strategy "
               "(Price Action · Fibonacci · 20 SMA · Volume · RSI · Bollinger) → trade "
               "only if the setup confirms.**")
    if focus.empty:
        st.info("No high-conviction focus candidates today — review Priority B below.")
    else:
        _focus_cards(focus)

    st.write("")

    # ---- Top opportunities (Priority A) ----------------------------------
    a_df = df[df["priority"] == "A"]
    section_header(f"⚡ Priority A — Highest Conviction ({len(a_df)})")
    st.caption("Strong/leading sector **and** technically ready (near breakout), "
               "confirmed by strong results or a bullish high-impact corporate action.")
    if a_df.empty:
        st.info("No Priority-A confluence today. Review Priority B below.")
    else:
        _table(a_df)

    # ---- Priority B -------------------------------------------------------
    b_df = df[df["priority"] == "B"]
    section_header(f"Priority B — Solid Setups ({len(b_df)})")
    if b_df.empty:
        st.caption("_None today._")
    else:
        _table(b_df)

    # ---- Priority C + Avoid in expanders (with Why-Not explanations) ------
    c_df = df[(df["priority"] == "C") & (df["action"] != "Avoid")]
    with st.expander(f"Priority C — Watch / lower conviction ({len(c_df)})  ·  why not higher?"):
        if c_df.empty:
            st.caption("_None._")
        else:
            _table_whynot(c_df)

    avoid_df = df[df["action"] == "Avoid"]
    with st.expander(f"⚪ Avoid — weak setups ({len(avoid_df)})  ·  why not selected?"):
        if avoid_df.empty:
            st.caption("_None._")
        else:
            _table_whynot(avoid_df)

    # ---- Full price metrics (all stocks) ---------------------------------
    with st.expander("📐 Full price metrics — Price · 20 SMA · 52W High/Low · Distances"):
        m = df.copy()
        for col in ("current_price", "sma_20", "high_52w", "low_52w"):
            m[col] = m[col].map(lambda v: f"{v:,.2f}" if pd.notna(v) else "—")
        for col in ("dist_52w_high_pct", "dist_52w_low_pct"):
            m[col] = m[col].map(lambda v: f"{v:.1f}%" if pd.notna(v) else "—")
        st.dataframe(m[list(_METRICS)].rename(columns=_METRICS),
                     width="stretch", hide_index=True)

    # ---- How to read this dashboard (transparency + workflow) ------------
    with st.expander("📖 How to read this dashboard (rules + workflow)"):
        st.markdown(
            "**Daily workflow**\n"
            "1. Check the freshness badges (green = today's data).\n"
            "2. Read **Today's Focus** — your 3–5 charts to open.\n"
            "3. Skim **Priority A → B**; C and Avoid are tucked away below.\n"
            "4. On each chart, apply your own strategy — **Price Action · Fibonacci · "
            "20 SMA · Volume · RSI · Bollinger Bands** — and trade only if it confirms.\n\n"
            "**Do Now (rule-based directives):** Open chart now · Wait for breakout · "
            "Wait for pullback · Review earnings first · Ignore for now.\n\n"
            "---\n"
        )
        st.markdown(
            "**Priority A (strictest — typically 3–5 names).** ALL of: Above 20-SMA, "
            "Strong RS, Near Breakout (≤5% from 52W high), **and** at least one "
            "confirmation (Strong Sector / Strong Results / bullish high-impact "
            "corporate action) — and **not** weak results.\n\n"
            "**Priority B.** Above 20-SMA, not weak, with **two of three** pillars: "
            "{Strong RS, Near Breakout, a confirmation (Strong Sector / Strong Results)}.\n\n"
            "**Priority C.** Everything else (including any weak-results name).\n\n"
            "**Action** (reflects setup quality):\n"
            "- 🟢 **Ready** — clean setup, near breakout, results not weak.\n"
            "- 🟡 **Research** — building / has a catalyst or earnings to validate "
            "(weak-results names land here, never Ready).\n"
            "- 🔵 **Watch** — monitor only, no trigger yet.\n"
            "- ⚪ **Avoid** — below trend & weak.\n\n"
            "**⭐ Setup Quality** (display-only, NOT used for ranking): one star each "
            "for Strong Sector · Strong RS · Above 20 SMA · Near Breakout · Strong "
            "Results (max 5).\n\n"
            "**Breakout:** 🟢 ≤5% from 52W high · 🟡 ≤15% · ⚪ >15%.\n\n"
            "All rules are deterministic — **no scoring, no weights, no prediction, "
            "no ML**. Price metrics come from one shared module for every stock."
        )
