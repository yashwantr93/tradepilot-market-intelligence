"""
Dashboard data contracts — the ONLY bridge between the UI and the database.

Read-only. Reads directly from the existing SQLite database produced by the
backend pipelines. It never imports connectors, never fetches live data, and
never modifies anything. The Streamlit pages consume only these functions, so
the UI stays ignorant of how the data was produced.

All getters are cached (short TTL) for snappy navigation.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from core.db.engine import get_engine

_DATE_COLS = {"trade_date", "announcement_date", "period_end", "signal_date"}


def _read(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a read-only query against the backend SQLite DB."""
    try:
        df = pd.read_sql_query(sql, get_engine(), params=params or {})
    except Exception:  # noqa: BLE001 - empty/missing table -> empty frame
        return pd.DataFrame()
    for c in df.columns:
        if c in _DATE_COLS:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    return df


@st.cache_data(ttl=120)
def distinct_dates(table: str, date_col: str) -> list[dt.date]:
    df = _read(f"SELECT DISTINCT {date_col} AS d FROM {table} ORDER BY {date_col} DESC")
    if df.empty:
        return []
    parsed = pd.to_datetime(df["d"], errors="coerce").dt.date
    return [d for d in parsed.tolist() if d is not None and pd.notna(d)]


@st.cache_data(ttl=120)
def latest_date(table: str, date_col: str) -> dt.date | None:
    dates = distinct_dates(table, date_col)
    return dates[0] if dates else None


# ---------------------------------------------------------------------------
# Per-engine getters
# ---------------------------------------------------------------------------
@st.cache_data(ttl=120)
def deal_watchlist(trade_date: dt.date | None = None) -> pd.DataFrame:
    if trade_date is None:
        return _read("SELECT * FROM daily_watchlist ORDER BY rule_count DESC")
    return _read("SELECT * FROM daily_watchlist WHERE trade_date = :d "
                 "ORDER BY rule_count DESC", {"d": trade_date.isoformat()})


@st.cache_data(ttl=120)
def institutional_watchlist(trade_date: dt.date | None = None) -> pd.DataFrame:
    if trade_date is None:
        return _read("SELECT * FROM institutional_watchlist")
    return _read("SELECT * FROM institutional_watchlist WHERE trade_date = :d",
                 {"d": trade_date.isoformat()})


@st.cache_data(ttl=120)
def sector_rotation(trade_date: dt.date | None = None) -> pd.DataFrame:
    if trade_date is None:
        return _read("SELECT * FROM sector_rotation")
    return _read("SELECT * FROM sector_rotation WHERE trade_date = :d",
                 {"d": trade_date.isoformat()})


@st.cache_data(ttl=120)
def fii_dii(limit: int = 30) -> pd.DataFrame:
    df = _read("SELECT * FROM fii_dii_activity ORDER BY trade_date DESC LIMIT :n",
               {"n": limit})
    return df.sort_values("trade_date").reset_index(drop=True) if not df.empty else df


@st.cache_data(ttl=120)
def corporate_actions(since: dt.date | None = None) -> pd.DataFrame:
    if since is None:
        return _read("SELECT * FROM corporate_actions ORDER BY announcement_date DESC")
    return _read("SELECT * FROM corporate_actions WHERE announcement_date >= :d "
                 "ORDER BY announcement_date DESC", {"d": since.isoformat()})


@st.cache_data(ttl=120)
def results(period_end: dt.date | None = None) -> pd.DataFrame:
    if period_end is None:
        return _read("SELECT * FROM results_tracker ORDER BY period_end DESC")
    return _read("SELECT * FROM results_tracker WHERE period_end = :d",
                 {"d": period_end.isoformat()})


@st.cache_data(ttl=120)
def combined_watchlist(trade_date: dt.date | None = None) -> pd.DataFrame:
    if trade_date is None:
        return _read("SELECT * FROM combined_watchlist ORDER BY tier ASC")
    return _read("SELECT * FROM combined_watchlist WHERE trade_date = :d "
                 "ORDER BY tier ASC", {"d": trade_date.isoformat()})


@st.cache_data(ttl=120)
def signals() -> pd.DataFrame:
    return _read("SELECT * FROM signals")


@st.cache_data(ttl=120)
def combined_enriched(trade_date: dt.date | None = None) -> pd.DataFrame:
    """Combined watchlist left-joined with shared price metrics + Near Breakout.

    Read-only enrichment — does not modify the confluence engine.
    """
    base = combined_watchlist(trade_date)
    if base.empty:
        return base
    df = base.merge(price_metrics_map(), on="symbol", how="left")
    df["near_breakout"] = df["dist_52w_high_pct"].map(near_breakout_label)
    return df


# ---------------------------------------------------------------------------
# Validation aggregation (measurement only — mirrors the report logic)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=120)
def engine_performance(ret_col: str) -> pd.DataFrame:
    """Per-engine win rate / avg / median / best / worst for a return horizon."""
    sig = signals()
    if sig.empty or ret_col not in sig.columns:
        return pd.DataFrame()
    rows = []
    for engine, g in sig.groupby("source_engine"):
        ev = g[g[ret_col].notna()]
        if ev.empty:
            rows.append({"Engine": engine, "Signals": len(g), "Evaluated": 0,
                         "Win Rate": None, "Avg %": None, "Median %": None,
                         "Best %": None, "Worst %": None})
            continue
        rows.append({
            "Engine": engine, "Signals": len(g), "Evaluated": len(ev),
            "Win Rate": round((ev[ret_col] > 0).mean() * 100, 0),
            "Avg %": round(ev[ret_col].mean(), 2),
            "Median %": round(ev[ret_col].median(), 2),
            "Best %": round(ev[ret_col].max(), 2),
            "Worst %": round(ev[ret_col].min(), 2),
        })
    return pd.DataFrame(rows).sort_values("Signals", ascending=False)


# ---------------------------------------------------------------------------
# Daily Opportunity Hub — deterministic rule-based prioritization
# ---------------------------------------------------------------------------
# This is a READ-ONLY derivation over the existing engine tables. It introduces
# NO scoring and NO ML — only transparent if/else classification for display.

_ARROW = {"Bullish": "▲", "Bearish": "▼", "Neutral": "■"}

# The five transparent setup conditions (used for the star checklist + Today's
# Focus explanation). Each is a plain boolean on already-computed fields.
_STAR_CONDITIONS = [
    ("Strong Sector", "strong_sector"),
    ("Strong RS", "strong_rs"),
    ("Above 20 SMA", "above_sma"),
    ("Near Breakout", "near_breakout"),
    ("Strong Results", "results_strong"),
]


def _conditions(row) -> dict:
    """Compute the deterministic boolean conditions for one stock."""
    rs = row.get("relative_strength")
    dist = row.get("dist_52w_high_pct")
    has_dist = dist is not None and not pd.isna(dist)
    return {
        "strong_sector": row.get("sector_trend") == "Strong",
        "strong_rs": rs == "Strong",
        "above_sma": row.get("above_20_sma") == "Y",
        "near_breakout": has_dist and dist <= 5,
        "building": has_dist and 5 < dist <= 15,
        "far": has_dist and dist > 15,
        "results_strong": row.get("results_status") == "Strong",
        "results_weak": row.get("results_status") == "Weak",
        "ca_bull_high": (row.get("_ca_impact") == "Bullish"
                         and row.get("_ca_priority") == "High"),
        "ca_bear": row.get("_ca_impact") == "Bearish",
        "rs": rs,
        "tech": row.get("technical_status"),
        "in_deal": row.get("in_deal") == "Y",
        # price levels (existing stored metrics) for the concrete chart checklist
        "high_52w": row.get("high_52w"),
        "sma_20": row.get("sma_20"),
        "low_52w": row.get("low_52w"),
    }


def _priority(c: dict) -> str:
    """Priority A is the STRICTEST combination of existing rules (no scoring).

    A — above 20 SMA AND Strong RS AND Near Breakout AND at least one strength
        confirmation (Strong Sector / Strong Results / bullish high-impact CA),
        and NOT weak results.
    B — strong but missing one hard gate (e.g. not yet near breakout).
    C — everything else.
    """
    if c["results_weak"]:
        return "C"  # weak earnings are never top priority
    # A — the strictest setup: trend + leadership + near breakout + a confirmation.
    if (c["above_sma"] and c["strong_rs"] and c["near_breakout"]
            and (c["strong_sector"] or c["results_strong"] or c["ca_bull_high"])):
        return "A"
    # B — above trend, not weak, and at least TWO of the three pillars
    #     {Strong RS, Near Breakout, a confirmation (sector/results)}.
    confirm = c["strong_sector"] or c["results_strong"]
    if c["above_sma"] and c["rs"] != "Weak" and (
            (c["strong_rs"] and c["near_breakout"])
            or (c["strong_rs"] and confirm)
            or (c["near_breakout"] and confirm)):
        return "B"
    return "C"


def _action(c: dict) -> str:
    """Action reflects setup quality. 'Ready' now requires a clean, near-breakout
    setup AND non-weak results — so weak-earnings names are never 'Ready'."""
    below_trend = not c["above_sma"]
    clean = c["above_sma"] and c["rs"] != "Weak" and not c["results_weak"]
    if c["tech"] == "Avoid" or (c["rs"] == "Weak" and below_trend) \
            or (c["results_weak"] and c["ca_bear"]):
        return "Avoid"
    if clean and c["near_breakout"]:
        return "Ready"
    if c["results_weak"] and c["above_sma"]:
        return "Research"   # decent chart but weak earnings -> review first
    if clean and c["building"]:
        return "Research"
    if c["in_deal"] or c["results_strong"] or c["ca_bull_high"]:
        return "Research"
    return "Watch"


def _next_step(c: dict) -> str:
    """Rule-specific next step (most important blocker first)."""
    if c["results_weak"]:
        return "Review earnings before considering entry."
    if not c["above_sma"]:
        return "Wait until price regains the 20-SMA trend."
    if c["near_breakout"]:
        return "Watch for breakout above recent swing high."
    if c["building"]:
        return "Wait for confirmation before entry."
    if c["far"]:
        return "Monitor only. No immediate action."
    return "Monitor only. No immediate action."


def _setup(c: dict) -> tuple[int, str, str]:
    """Visual checklist: (star_count, ⭐ string, satisfied-condition text).

    DISPLAY ONLY — never used in priority/action/sort.
    """
    labels = [name for name, key in _STAR_CONDITIONS if c[key]]
    n = len(labels)
    stars = "⭐" * n if n else "—"
    return n, stars, " · ".join(labels) if labels else "—"


def _action_cue(c: dict) -> str:
    """One-line directive verb (display-only) derived from the same conditions."""
    if c["results_weak"]:
        return "Review earnings first"
    if c["tech"] == "Avoid" or (c["rs"] == "Weak" and not c["above_sma"]):
        return "Ignore for now"
    if not c["above_sma"]:
        return "Wait for pullback"
    if c["near_breakout"]:
        return "Open chart now"
    if c["building"]:
        return "Wait for breakout"
    if c["far"]:
        return "Ignore for now"
    return "Monitor"


def _money(v) -> str:
    return f"₹{v:,.0f}" if (v is not None and not pd.isna(v)) else "n/a"


def _chart_check(c: dict) -> str:
    """Concrete pre-trade checklist with real levels: breakout, volume, invalidation.

    Uses already-stored metrics (52W high, 20-SMA, 52W low) — no new data/logic.
    """
    hi, sma, lo = _money(c["high_52w"]), _money(c["sma_20"]), _money(c["low_52w"])
    if c["results_weak"]:
        return (f"Review earnings first. Only act if price holds above 20-SMA {sma} "
                f"with a clean base.")
    if not c["above_sma"]:
        return (f"Wait to reclaim 20-SMA {sma}. Watch pullback support near 52W low "
                f"{lo}; need an RSI reset + volume to turn up.")
    if c["near_breakout"]:
        return (f"Breakout level: close above 52W high {hi} on above-average volume. "
                f"Invalidation: below 20-SMA {sma}.")
    if c["building"]:
        return (f"Trigger: break & hold above {hi} on rising volume. "
                f"Invalidation: loss of 20-SMA {sma}.")
    if c["far"]:
        return f"No setup near highs (52W high {hi}). Monitor only; invalidation 20-SMA {sma}."
    return f"Revisit on a clean setup: reclaim 20-SMA {sma}, then test 52W high {hi}."


def _why_not(c: dict) -> str:
    """Plain-English reasons a stock is NOT higher priority (for C / Avoid rows)."""
    reasons = []
    if c["results_weak"]:
        reasons.append("Weak results")
    if not c["above_sma"]:
        reasons.append("Below 20-SMA")
    if c["rs"] == "Weak":
        reasons.append("Weak RS")
    elif not c["strong_rs"]:
        reasons.append("RS not strong")
    if not c["near_breakout"]:
        reasons.append("Far from 52W high" if c["far"] else "Not near breakout")
    if not (c["strong_sector"] or c["results_strong"] or c["ca_bull_high"]):
        reasons.append("No sector/results confirmation")
    return " · ".join(reasons) if reasons else "Borderline — just missed a gate"

# Shared price metrics (now stored by BOTH deal-flow and institutional pipelines).
PRICE_METRIC_COLS = ["current_price", "sma_20", "high_52w", "low_52w",
                     "dist_52w_high_pct", "dist_52w_low_pct"]


def near_breakout_label(dist_high) -> str:
    """Display-only classification from distance-to-52W-high (NOT used for ranking)."""
    if dist_high is None or pd.isna(dist_high):
        return "—"
    if dist_high <= 5:
        return "🟢 Near Breakout"
    if dist_high <= 15:
        return "🟡 Building"
    return "⚪ Far"


@st.cache_data(ttl=120)
def price_metrics_map() -> pd.DataFrame:
    """One row of price metrics per symbol, preferring deal-flow then institutional."""
    frames = []
    dd = latest_date("daily_watchlist", "trade_date")
    if dd:
        d = deal_watchlist(dd)
        if not d.empty:
            frames.append(d[["symbol"] + [c for c in PRICE_METRIC_COLS if c in d.columns]])
    idate = latest_date("institutional_watchlist", "trade_date")
    if idate:
        i = institutional_watchlist(idate)
        if not i.empty:
            frames.append(i[["symbol"] + [c for c in PRICE_METRIC_COLS if c in i.columns]])
    if not frames:
        return pd.DataFrame(columns=["symbol"] + PRICE_METRIC_COLS)
    return pd.concat(frames, ignore_index=True).drop_duplicates("symbol", keep="first")


@st.cache_data(ttl=120)
def data_freshness() -> list[dict]:
    """Per-source latest date + freshness flag for badge display."""
    today = dt.date.today()
    out = []
    specs = [
        ("Deal Flow", "daily_watchlist", "trade_date", False),
        ("Institutional", "institutional_watchlist", "trade_date", False),
        ("Corp Actions", "corporate_actions", "announcement_date", False),
        ("Results", "results_tracker", "period_end", True),
        ("Signals", "signals", "signal_date", False),
    ]
    for label, table, col, is_quarter in specs:
        d = latest_date(table, col)
        if d is None:
            out.append({"label": label, "value": "no data", "kind": "gray"})
            continue
        days = (today - d).days
        if is_quarter:
            kind, value = "blue", f"{label}: {d.strftime('%b %Y')}"
        elif days < 0:  # future-dated (e.g. corporate-action ex-dates)
            kind, value = "blue", f"{label}: {d.strftime('%d %b')} (upcoming)"
        else:
            kind = "green" if days <= 4 else ("amber" if days <= 10 else "red")
            ago = "today" if days == 0 else f"{days}d ago"
            value = f"{label}: {d.strftime('%d %b')} ({ago})"
        out.append({"label": label, "value": value, "kind": kind})
    return out


def _ca_by_symbol() -> dict:
    """Highest-priority corporate action per symbol (event_type, impact, priority)."""
    ca = corporate_actions()
    if ca.empty:
        return {}
    pr = {"High": 0, "Medium": 1, "Low": 2}
    im = {"Bullish": 0, "Neutral": 1, "Bearish": 2}
    ca = ca.assign(_p=ca["priority"].map(pr).fillna(9),
                   _i=ca["impact_tag"].map(im).fillna(9))
    ca = ca.sort_values(["symbol", "_p", "_i"]).groupby("symbol", as_index=False).first()
    return {r["symbol"]: (r["event_type"], r["impact_tag"], r["priority"])
            for _, r in ca.iterrows()}


@st.cache_data(ttl=120)
def opportunity_hub() -> pd.DataFrame:
    """Unified, prioritized decision table built from the existing engine tables."""
    cdate = latest_date("combined_watchlist", "trade_date")
    if cdate is None:
        return pd.DataFrame()
    base = combined_watchlist(cdate)
    if base.empty:
        return pd.DataFrame()

    # Enrich: shared price metrics (available for ALL stocks), sector trend,
    # results classification, corporate-action status.
    metrics = price_metrics_map()
    rperiod = latest_date("results_tracker", "period_end")
    res = results(rperiod)[["symbol", "result_classification"]] if rperiod \
        else pd.DataFrame(columns=["symbol", "result_classification"])
    ca_map = _ca_by_symbol()

    df = base.merge(metrics, on="symbol", how="left")

    # Sector trend (Strong/Improving/...) from the institutional watchlist.
    idate = latest_date("institutional_watchlist", "trade_date")
    if idate:
        inst_tr = institutional_watchlist(idate)[["symbol", "sector_trend"]]
        df = df.merge(inst_tr, on="symbol", how="left")
    else:
        df["sector_trend"] = None

    df = df.merge(res.rename(columns={"result_classification": "results_status"}),
                  on="symbol", how="left")
    df["results_status"] = df["results_status"].fillna("—")
    df["_ca_event"] = df["symbol"].map(lambda s: ca_map.get(s, (None,))[0])
    df["_ca_impact"] = df["symbol"].map(
        lambda s: ca_map[s][1] if s in ca_map else None)
    df["_ca_priority"] = df["symbol"].map(
        lambda s: ca_map[s][2] if s in ca_map else None)

    def _ca_status(r) -> str:
        ev = r["_ca_event"]
        if ev is None or pd.isna(ev):  # NaN is truthy in Python — guard explicitly
            return "—"
        return f"{ev} {_ARROW.get(r['_ca_impact'], '')}".strip()

    df["corp_action_status"] = df.apply(_ca_status, axis=1)

    # Deterministic derivation — one pass of the transparent conditions.
    conds = df.apply(_conditions, axis=1)
    df["priority"] = conds.map(_priority)
    df["action"] = conds.map(_action)
    df["next_step"] = conds.map(_next_step)
    df["action_cue"] = conds.map(_action_cue)
    df["chart_check"] = conds.map(_chart_check)
    df["why_not"] = conds.map(_why_not)
    setup = conds.map(_setup)
    df["setup_stars"] = setup.map(lambda t: t[0])
    df["setup_quality"] = setup.map(lambda t: t[1])
    df["setup_reason"] = setup.map(lambda t: t[2])
    # Display-only breakout classification (NOT used in priority/action).
    df["near_breakout"] = df["dist_52w_high_pct"].map(near_breakout_label)

    # Sort: Priority A->B->C, Action Ready->Research->Watch->Avoid, Strong RS first.
    # (setup_stars is NOT a sort key — the star checklist never affects ranking.)
    p_rank = {"A": 0, "B": 1, "C": 2}
    a_rank = {"Ready": 0, "Research": 1, "Watch": 2, "Avoid": 3}
    rs_rank = {"Strong": 0, "Neutral": 1, "Improving": 1, "Weak": 2}
    df["_p"] = df["priority"].map(p_rank)
    df["_a"] = df["action"].map(a_rank)
    df["_r"] = df["relative_strength"].map(rs_rank).fillna(3)
    df = df.sort_values(["_p", "_a", "_r", "symbol"]).reset_index(drop=True)
    return df


@st.cache_data(ttl=120)
def strong_sectors_summary() -> dict:
    """Today's Strong / Improving sectors from existing sector-rotation data only."""
    d = latest_date("sector_rotation", "trade_date")
    if d is None:
        return {"trade_date": None, "strong": [], "improving": []}
    rot = sector_rotation(d)
    if rot.empty:
        return {"trade_date": d, "strong": [], "improving": []}
    rot = rot.sort_values("rs_vs_nifty", ascending=False)
    return {
        "trade_date": d,
        "strong": rot[rot["trend_status"] == "Strong"]["sector"].tolist(),
        "improving": rot[rot["trend_status"] == "Improving"]["sector"].tolist(),
    }


def todays_focus(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Top 3–5 research candidates: Priority A first, topped up with Ready
    Priority-B names. Fully deterministic — uses the existing sort order."""
    if df.empty:
        return df
    focus = df[df["priority"] == "A"]
    if len(focus) < 3:
        topup = df[(df["priority"] == "B") & (df["action"] == "Ready")]
        focus = pd.concat([focus, topup])
    return focus.drop_duplicates("symbol").head(n)


def db_available() -> bool:
    """True if the backend DB has at least one populated watchlist table."""
    df = _read("SELECT name FROM sqlite_master WHERE type='table' "
               "AND name='daily_watchlist'")
    return not df.empty


@st.cache_data(ttl=60)
def recent_job_runs(limit: int = 10) -> pd.DataFrame:
    """Most recent pipeline runs from the `job_runs` audit trail — powers the
    Settings page's scheduler/last-refresh status. Read-only, same as every
    other getter in this module."""
    df = _read(
        "SELECT job_name, source, started_at, finished_at, duration_s, "
        "status, rows_in, rows_out, error FROM job_runs "
        "ORDER BY started_at DESC LIMIT :limit", {"limit": limit})
    return df
