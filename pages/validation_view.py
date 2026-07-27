"""Dashboard page: Validation Dashboard (engine performance from signals)."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from components import COLORS, kpi_card, section_header, style_fig
from data import contracts

_HORIZONS = {"1-Day": "ret_1d", "5-Day": "ret_5d", "20-Day": "ret_20d"}


def render() -> None:
    st.title("✅ Validation Dashboard")
    st.caption("How each engine's signals perform after generation · measurement only")

    sig = contracts.signals()
    if sig.empty:
        st.info("No signals yet. Run `python run_validation.py`.")
        return

    evaluated = int((sig["status"] == "evaluated").sum())
    partial = int((sig["status"] == "partial").sum())
    no_price = int((sig["status"] == "no_price").sum())
    pending = len(sig) - evaluated - partial - no_price

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Signals Tracked", str(len(sig)))
    with c2:
        kpi_card("Fully Evaluated", str(evaluated), delta="1/5/20d done", delta_dir="up")
    with c3:
        kpi_card("Partial / Pending", f"{partial} / {pending}",
                 delta="Window not elapsed", delta_dir="flat")
    with c4:
        kpi_card("No Price Data", str(no_price), delta="Uncovered symbols",
                 delta_dir="flat")

    st.caption("Win rate / averages are computed only over signals whose horizon has "
               "elapsed. Recent signals stay pending until enough trading days pass.")

    horizon = st.radio("Forward-return horizon", list(_HORIZONS), horizontal=True)
    ret_col = _HORIZONS[horizon]

    perf = contracts.engine_performance(ret_col)
    section_header(f"Engine Performance — {horizon} Forward Return")
    if perf.empty or perf["Evaluated"].fillna(0).sum() == 0:
        st.warning(f"No signals have an elapsed {horizon} window yet.")
    else:
        st.dataframe(
            perf, width="stretch", hide_index=True,
            column_config={
                "Win Rate": st.column_config.NumberColumn(format="%.0f%%"),
                "Avg %": st.column_config.NumberColumn(format="%.2f"),
                "Median %": st.column_config.NumberColumn(format="%.2f"),
                "Best %": st.column_config.NumberColumn(format="%.2f"),
                "Worst %": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        plot = perf.dropna(subset=["Win Rate"])
        if not plot.empty:
            fig = px.bar(plot, x="Engine", y="Win Rate", color="Avg %",
                         color_continuous_scale=["#dc2626", "#f1f5f9", "#16a34a"],
                         color_continuous_midpoint=0, text="Win Rate")
            fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
            fig.add_hline(y=50, line_dash="dot", line_color=COLORS["muted"])
            st.plotly_chart(style_fig(fig, height=340), width="stretch")

    # Sub-breakdowns: Results by classification, Confluence by tier.
    section_header("Signal Detail")
    eng = st.selectbox("Filter by engine", ["All"] + sorted(sig["source_engine"].unique()))
    view = sig if eng == "All" else sig[sig["source_engine"] == eng]
    cols = {"signal_date": "Signal Date", "symbol": "Symbol",
            "source_engine": "Engine", "signal_type": "Signal Type",
            "entry_price": "Entry", "ret_1d": "1D %", "ret_5d": "5D %",
            "ret_20d": "20D %", "status": "Status"}
    st.dataframe(
        view[list(cols)].rename(columns=cols), width="stretch", hide_index=True,
        column_config={
            "1D %": st.column_config.NumberColumn(format="%.2f"),
            "5D %": st.column_config.NumberColumn(format="%.2f"),
            "20D %": st.column_config.NumberColumn(format="%.2f"),
            "Entry": st.column_config.NumberColumn(format="%.2f"),
        },
    )
