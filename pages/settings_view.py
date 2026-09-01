"""
Settings — a lightweight, read-only operational status page.

Shows database status, last refresh per engine, data directory, version, and
scheduler status. No user accounts, no configuration editing — this is a
single-user personal terminal, not a multi-tenant app. Every value here is
read directly from existing data (job_runs audit trail, schema_version
tables, filesystem paths) — nothing is computed or inferred.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from components import badge, kpi_card, section_header
from core.branding import APP_FULL_NAME, APP_VERSION
from core.config import DATA_STORE_DIR, IS_RENDER
from data import contracts as v1
from intelligence_v2.config.settings import CURRENT_SCHEMA_VERSION, V2_DB_PATH
from intelligence_v2.database.migrations import get_latest_schema_version


def render() -> None:
    st.title("⚙️ Settings")
    st.caption("Read-only operational status for this personal terminal — no accounts, "
              "no configuration editing.")

    _render_overall_freshness()
    st.write("")
    _render_database_status()
    st.write("")
    _render_data_freshness()
    st.write("")
    _render_scheduler_status()
    st.write("")
    _render_build_info()


def _render_overall_freshness() -> None:
    """Phase 11 — a single rollup answer to "is today's dashboard current",
    computed from actual stage dates + job status (never "exit code 0"
    alone). See `data.contracts.refresh_status()`."""
    section_header("Overall Refresh Status")
    rs = v1.refresh_status()
    kind = {"CURRENT": "green", "PARTIALLY_REFRESHED": "amber",
           "STALE": "amber", "FAILED": "red"}.get(rs["status"], "gray")
    ref = f" (reference date: {rs['reference_date']})" if rs["reference_date"] else ""
    st.markdown(badge(f"V1 + Event Intelligence: {rs['status']}{ref}", kind),
               unsafe_allow_html=True)
    if rs["status"] != "CURRENT" and rs["reasons"]:
        with st.expander(f"Why not CURRENT? ({len(rs['reasons'])} reason(s))"):
            for reason in rs["reasons"]:
                st.markdown(f"- {reason}")
    st.caption("V2's freshness is reported separately below (own database) — "
              "this rollup covers V1 + the Event Intelligence layer only.")
    if IS_RENDER:
        st.warning(
            "📦 **This is the production deployment** — a static, git-shipped "
            "SQLite snapshot (see DEPLOYMENT.md). It does NOT refresh itself; "
            "the status above reflects whatever `market.db`/`market_v2.db` "
            "were last committed and pushed, not live data. To refresh "
            "production, run the local pipeline, then `git add data_store/"
            "market.db data_store/market_v2.db && git commit && git push`."
        )


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

    st.markdown("**Event Intelligence** (Phases 3–8, V1 database)")
    ei_rows = [{"Stage": s["stage"], "Latest Date": str(s["latest_date"] or "No data yet"),
               "Current": "✅" if s["current"] else "—"}
              for s in v1.refresh_status()["stages"]
              if s["stage"] not in ("price_history", "corporate_actions")]
    st.dataframe(pd.DataFrame(ei_rows), width="stretch", hide_index=True)


def _render_scheduler_status() -> None:
    section_header("Scheduler Status")
    runs = v1.recent_job_runs(limit=8)
    if runs.empty:
        st.caption("_No job-run history recorded yet._")
    else:
        st.markdown("**V1 pipelines** — recent runs (`job_runs` audit trail)")
        st.dataframe(runs, width="stretch", hide_index=True)

    st.caption(
        "`run_daily_scheduled.ps1` (invoked by the local Windows Task Scheduler entry "
        "\"SwingTradingIntelligence_DailyRun\") now calls `run_daily_all.py`, which "
        "chains V1 → V2 → Event Intelligence in one command (Phase 11) — see the "
        "Phase 11 report's SCHEDULER AUDIT section for whether the registered Task "
        "Scheduler entry itself is currently pointed at the right path.")


def _render_build_info() -> None:
    section_header("Build Information")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Version", APP_VERSION, delta="Feature-frozen intelligence engine",
                 delta_dir="flat")
    with c2:
        commit = _git_commit_short()
        kpi_card("Build", commit or "unknown", delta="git commit", delta_dir="flat")
    with c3:
        kpi_card("Deployment", "Render (production)" if IS_RENDER else "Local",
                 delta="Static snapshot" if IS_RENDER else "Live, Task-Scheduler-refreshed",
                 delta_dir="flat")
    with c4:
        kpi_card("Data Directory", "data_store/", delta=str(DATA_STORE_DIR),
                 delta_dir="flat")

    st.caption(f"{APP_FULL_NAME} · Python {sys.version.split()[0]} · "
              f"Streamlit {st.__version__}")


def _git_commit_short() -> str | None:
    """Best-effort, read-only git short SHA. On Render, `RENDER_GIT_COMMIT`
    (set by the platform itself for every deploy, per Render's documented
    env vars) is authoritative and preferred over reading `.git/HEAD`
    locally, since it's guaranteed accurate regardless of whether the
    deployed filesystem's `.git` directory is intact. Returns None if
    neither is available (e.g. not a git checkout). Never touches git
    state, only reads."""
    render_commit = os.environ.get("RENDER_GIT_COMMIT")
    if render_commit:
        return render_commit[:8]
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
