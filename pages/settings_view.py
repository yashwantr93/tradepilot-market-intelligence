"""
Settings — a lightweight, read-only operational status page.

Shows database status, last refresh per engine, data directory, version, and
scheduler status. No user accounts, no configuration editing — this is a
single-user personal terminal, not a multi-tenant app. Every value here is
read directly from existing data (job_runs audit trail, schema_version
tables, filesystem paths) — nothing is computed or inferred.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from components import badge, kpi_card, section_header
from core.branding import APP_FULL_NAME, APP_VERSION
from core.config import DATA_STORE_DIR
from data import contracts as v1
from intelligence_v2.config.settings import CURRENT_SCHEMA_VERSION, V2_DB_PATH
from intelligence_v2.database.migrations import get_latest_schema_version


def render() -> None:
    st.title("⚙️ Settings")
    st.caption("Read-only operational status for this personal terminal — no accounts, "
              "no configuration editing.")

    _render_database_status()
    st.write("")
    _render_data_freshness()
    st.write("")
    _render_scheduler_status()
    st.write("")
    _render_build_info()


def _render_database_status() -> None:
    section_header("Database Status")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**V1 — `market.db`** (read-write, pipelines only)")
        v1_path = DATA_STORE_DIR / "market.db"
        if v1_path.exists():
            size_mb = v1_path.stat().st_size / (1024 * 1024)
            st.markdown(badge(f"Available · {size_mb:.1f} MB", "green"), unsafe_allow_html=True)
        else:
            st.markdown(badge("Not found", "red"), unsafe_allow_html=True)
        st.caption(f"`{v1_path}`")

    with c2:
        st.markdown("**V2 — `market_v2.db`** (read-write V2, read-only bridge into V1)")
        if V2_DB_PATH.exists():
            size_mb = V2_DB_PATH.stat().st_size / (1024 * 1024)
            st.markdown(badge(f"Available · {size_mb:.1f} MB", "green"), unsafe_allow_html=True)
        else:
            st.markdown(badge("Not found", "red"), unsafe_allow_html=True)
        st.caption(f"`{V2_DB_PATH}`")

    latest_schema = get_latest_schema_version()
    schema_ok = latest_schema == CURRENT_SCHEMA_VERSION
    st.markdown(
        badge(f"V2 schema version: {latest_schema} / {CURRENT_SCHEMA_VERSION}",
             "green" if schema_ok else "amber"),
        unsafe_allow_html=True)


def _render_data_freshness() -> None:
    section_header("Last Refresh")
    items = v1.data_freshness()
    if items:
        cols = st.columns(len(items))
        for col, item in zip(cols, items):
            with col:
                st.markdown(badge(item["value"], item["kind"]), unsafe_allow_html=True)
    else:
        st.caption("_No V1 refresh data yet._")

    from intelligence_v2.contracts import (
        bearish_opportunity as c4,
        early_momentum as c3,
        market_cycle as c2,
        position_opportunity as c5,
        sector_intelligence as c1,
    )
    # Each V2 phase's contract module names its meta-getter slightly
    # differently (pre-existing, approved code — not renamed here to avoid
    # touching frozen/tested modules for a cosmetic naming inconsistency).
    v2_engines = [
        ("Sector Intelligence", c1, "get_freshness"),
        ("Market Cycle", c2, "get_cycle_meta"),
        ("Early Momentum", c3, "get_meta"),
        ("Bearish Opportunity", c4, "get_meta"),
        ("Position Opportunity", c5, "get_meta"),
    ]
    rows = []
    for label, mod, meta_fn in v2_engines:
        if mod.is_data_available():
            meta = getattr(mod, meta_fn)()
            rows.append({"Engine": label, "Latest Date": str(meta.get("latest_date", "—")),
                        "Sessions of History": meta.get("days_of_history", "—")})
        else:
            rows.append({"Engine": label, "Latest Date": "No data yet",
                        "Sessions of History": "—"})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_scheduler_status() -> None:
    section_header("Scheduler Status")
    runs = v1.recent_job_runs(limit=8)
    if runs.empty:
        st.caption("_No job-run history recorded yet._")
    else:
        st.markdown("**V1 pipelines** — recent runs (`job_runs` audit trail)")
        st.dataframe(runs, width="stretch", hide_index=True)

    st.markdown(
        badge("V2 pipelines: no automated scheduler configured", "amber"),
        unsafe_allow_html=True)
    st.caption(
        "V1's `run_daily_scheduled.ps1` (Windows Task Scheduler) refreshes V1 data "
        "automatically. The five V2 engines (`run_v2_*.py`) must currently be run "
        "manually, in order: sector_intelligence → market_cycle → early_momentum "
        "→ bearish_opportunity → position_opportunity.")


def _render_build_info() -> None:
    section_header("Build Information")
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Version", APP_VERSION, delta="Feature-frozen intelligence engine",
                 delta_dir="flat")
    with c2:
        commit = _git_commit_short()
        kpi_card("Build", commit or "unknown", delta="git commit", delta_dir="flat")
    with c3:
        kpi_card("Data Directory", "data_store/", delta=str(DATA_STORE_DIR),
                 delta_dir="flat")

    st.caption(f"{APP_FULL_NAME} · Python {sys.version.split()[0]} · "
              f"Streamlit {st.__version__}")


def _git_commit_short() -> str | None:
    """Best-effort, read-only git short SHA — returns None if unavailable
    (e.g. not a git checkout). Never touches git state, only reads HEAD."""
    try:
        head = Path(".git/HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref_path = Path(".git") / head.split(" ", 1)[1]
            sha = ref_path.read_text(encoding="utf-8").strip()
        else:
            sha = head
        return sha[:8]
    except Exception:
        return None
