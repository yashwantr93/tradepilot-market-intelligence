"""
TradePilot AI — Market Intelligence Platform
=============================================

Rule-Based Swing Trading Intelligence System for the Indian Stock Market.

The UI layer for the rule-based intelligence backend. Every page reads directly
(read-only) from the existing SQLite database via data/contracts.py — the
dashboard performs NO data fetching, NO scoring and NO backend logic. It is the
primary way to review the daily watchlists and validation metrics produced by the
engine pipelines.

Backend pipelines that populate the database (run separately):
    run_live.py · run_institutional.py · run_corp_actions.py · run_results.py
    run_combined.py · run_validation.py

Run the dashboard with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from core.branding import (
    APP_FULL_NAME,
    APP_NAME,
    APP_SUBTITLE,
    DATA_SOURCES,
    DISCLAIMERS,
    FAVICON_PNG,
    LOGO_FULL_DARK,
    MARK_96,
)
from components import inject_global_css
from data import contracts
from pages import (
    combined_view,
    corp_actions_view,
    deal_flow,
    institutional,
    opportunity_hub,
    results_view,
    validation_view,
)
from intelligence_v2.pages import market_cycle as v2_market_cycle
from intelligence_v2.pages import sector_intelligence as v2_sector_intelligence

st.set_page_config(
    page_title=APP_FULL_NAME,
    page_icon=str(FAVICON_PNG) if FAVICON_PNG.exists() else "📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()

# label -> render function. Order matters: the first entry is the default landing
# page (the decision-support hub). Adding a page = one import + one line here.
PAGES = {
    "🎯 Daily Opportunity Hub": opportunity_hub.render,
    "🧩 Combined Watchlist": combined_view.render,
    "📈 Deal Flow Watchlist": deal_flow.render,
    "🏦 Institutional Watchlist": institutional.render,
    "🏛️ Corporate Actions": corp_actions_view.render,
    "📊 Results Watchlist": results_view.render,
    "✅ Validation Dashboard": validation_view.render,
    "🔥 Sector Intelligence (V2)": v2_sector_intelligence.render,
    "🔄 Market Cycle (V2)": v2_market_cycle.render,
}


def render_sidebar() -> str:
    with st.sidebar:
        if MARK_96.exists():
            logo_col, title_col = st.columns([1, 3])
            with logo_col:
                st.image(str(MARK_96), width=48)
            with title_col:
                st.markdown(f"### {APP_NAME}")
        else:
            st.markdown(f"## {APP_NAME}")
        st.caption(APP_SUBTITLE)
        st.divider()
        selection = st.radio("Navigation", list(PAGES.keys()),
                             label_visibility="collapsed")
        st.divider()
        if contracts.db_available():
            st.caption("**Data source:** local SQLite (read-only)")
        else:
            st.warning("Database not found. Run the backend pipelines first.")
        st.caption("Refresh data by re-running the engine pipelines, then reload.")

        with st.expander("ℹ️ About this platform"):
            st.markdown(
                f"**{APP_FULL_NAME}** — identify high-quality **swing trading** "
                "opportunities (~1–8 weeks) by combining independent rule-based sources:\n\n"
                + " · ".join(DATA_SOURCES) + "\n\n"
                + "\n".join(f"- {d}" for d in DISCLAIMERS)
            )
        st.caption(f"© 2026 {APP_FULL_NAME}")
    return selection


def main() -> None:
    if not contracts.db_available():
        st.title(f"📈 {APP_FULL_NAME}")
        st.error("No backend database found at `data_store/market.db`.")
        st.markdown(
            "Run the engine pipelines first, for example:\n\n"
            "```bash\n"
            "python run_live.py\npython run_institutional.py\n"
            "python run_corp_actions.py\npython run_results.py\n"
            "python run_combined.py\npython run_validation.py\n"
            "```"
        )
        render_sidebar()
        return
    selection = render_sidebar()
    PAGES[selection]()


if __name__ == "__main__":
    main()
