"""
Report generators for live-data validation.

Produces four artifacts under reports/:
  1. Watchlist CSV
  2. Daily Watchlist Report (markdown)
  3. Data Quality Report (markdown)
  4. Source Success/Failure Report (markdown)

No scoring, no prediction — reports describe only what the rule-based pipeline
produced from real data.
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from core.branding import APP_NAME, TAGLINE
from core.config import PROJECT_ROOT
from core.db import repository as repo

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Branding banner inserted under every generated report title.
_REPORT_SUB = f"_{APP_NAME} — {TAGLINE}_"

# Human-readable column order for the watchlist exports.
_WL_COLUMNS = [
    "symbol", "sector", "catalyst_tag", "current_price", "above_20_sma",
    "relative_strength", "volume_expansion", "dist_52w_high_pct",
    "technical_status",
]
_RENAME = {
    "symbol": "Symbol", "sector": "Sector", "catalyst_tag": "Catalyst Tag",
    "current_price": "Current Price", "above_20_sma": "Above 20 SMA",
    "relative_strength": "Relative Strength", "volume_expansion": "Volume Expansion",
    "dist_52w_high_pct": "Distance from 52W High (%)", "technical_status": "Technical Status",
}


def export_watchlist_csv(trade_date: dt.date) -> tuple[str, int]:
    """Write the watchlist CSV. Returns (path, row_count)."""
    df = repo.get_watchlist(trade_date)
    path = REPORTS_DIR / f"watchlist_{trade_date.isoformat()}.csv"
    if df.empty:
        pd.DataFrame(columns=list(_RENAME.values())).to_csv(path, index=False)
        return str(path), 0
    out = df[_WL_COLUMNS].rename(columns=_RENAME)
    out.to_csv(path, index=False)
    return str(path), len(out)


def _md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(none)_\n"
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |\n"
    sep = "| " + " | ".join("---" for _ in cols) + " |\n"
    body = "".join(
        "| " + " | ".join(str(v) for v in row) + " |\n"
        for row in df.itertuples(index=False)
    )
    return head + sep + body


def generate_daily_report(trade_date: dt.date, stats: dict) -> str:
    """Daily Watchlist Report (markdown)."""
    df = repo.get_watchlist(trade_date)
    path = REPORTS_DIR / f"daily_report_{trade_date.isoformat()}.md"

    lines = [
        f"# Daily Watchlist Report — {trade_date.isoformat()}",
        "",
        _REPORT_SUB,
        "",
        f"_Generated {dt.datetime.now():%Y-%m-%d %H:%M} · rule-based, real market data · "
        "no scoring / no ML / no prediction_",
        "",
        "## Pipeline summary",
        "",
        f"- **Stocks processed (deal universe):** {stats.get('stocks_processed', 0)}",
        f"- **Bulk-deal candidate symbols:** {stats.get('bulk_candidates', 0)}",
        f"- **Block-deal candidate symbols:** {stats.get('block_candidates', 0)}",
        f"- **Final watchlist stocks:** {len(df)}",
        "",
        "## Watchlist",
        "",
    ]
    if df.empty:
        lines.append("_No stocks qualified under the rules today._\n")
    else:
        view = df[_WL_COLUMNS].rename(columns=_RENAME)
        lines.append(_md_table(view))
        lines += [
            "## Technical status breakdown",
            "",
            _md_table(
                df["technical_status"].value_counts().rename_axis("Status")
                .reset_index(name="Count")
            ),
            "## Catalyst breakdown",
            "",
            _md_table(
                df["catalyst_tag"].value_counts().rename_axis("Catalyst")
                .reset_index(name="Count")
            ),
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def generate_data_quality_report(trade_date: dt.date, stats: dict) -> str:
    """Data Quality Report (markdown)."""
    path = REPORTS_DIR / f"data_quality_{trade_date.isoformat()}.md"
    df = repo.get_watchlist(trade_date)

    price_missing = int(df["current_price"].isna().sum()) if not df.empty else 0
    sector_unknown = int((df["sector"] == "Unknown").sum()) if not df.empty else 0
    dist_missing = int(df["dist_52w_high_pct"].isna().sum()) if not df.empty else 0

    lines = [
        f"# Data Quality Report — {trade_date.isoformat()}",
        "",
        _REPORT_SUB,
        "",
        "## Coverage",
        "",
        f"- Deal symbols discovered: **{stats.get('stocks_processed', 0)}**",
        f"- Symbols with price history (yfinance): **{stats.get('priced_symbols', 0)}**",
        f"- Symbols missing price data: **{stats.get('missing_price_symbols', 0)}**",
        f"- Sectors resolved: **{stats.get('sectors_resolved', 0)}** / "
        f"{stats.get('stocks_processed', 0)}",
        "",
        "## Validation",
        "",
        f"- Bulk deal rows ingested: **{stats.get('bulk_rows', 0)}**",
        f"- Block deal rows ingested: **{stats.get('block_rows', 0)}**",
        f"- Rows quarantined (dead-letter): **{stats.get('dead_letter', 0)}**",
        "",
        "## Watchlist field completeness",
        "",
        f"- Rows with missing current price: **{price_missing}**",
        f"- Rows with Unknown sector: **{sector_unknown}**",
        f"- Rows with missing 52W-high distance: **{dist_missing}**",
        "",
        "## Notes",
        "",
        "- Price/technicals source: yfinance (NSE `.NS` tickers). Small-cap / SME / "
        "newly-listed symbols may lack history → blank technicals (expected).",
        "- Deal source: NSE public archive CSV (latest trading day).",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def generate_institutional_report(trade_date: dt.date) -> str:
    """Daily Institutional Report: flow summary, top/bottom sectors, watchlist."""
    path = REPORTS_DIR / f"institutional_report_{trade_date.isoformat()}.md"
    flows = repo.get_fii_dii(limit=10)
    rotation = repo.get_sector_rotation(trade_date)
    inst = repo.get_institutional_watchlist(trade_date)

    lines = [
        f"# Daily Institutional Report — {trade_date.isoformat()}",
        "",
        _REPORT_SUB,
        "",
        "_Rule-based · real market data · no scoring / no ML / no prediction_",
        "",
        "## Market Flow Summary",
        "",
    ]
    if flows.empty:
        lines.append("_No FII/DII data available._\n")
    else:
        latest = flows.iloc[-1]
        lines += [
            f"- **FII Net:** ₹{latest['fii_net']:,.2f} Cr "
            f"(Buy {latest['fii_buy']:,.0f} / Sell {latest['fii_sell']:,.0f})",
            f"- **DII Net:** ₹{latest['dii_net']:,.2f} Cr "
            f"(Buy {latest['dii_buy']:,.0f} / Sell {latest['dii_sell']:,.0f})",
        ]
        if len(flows) >= 5:
            f5 = flows.tail(5)
            lines.append(
                f"- **5-Day Trend:** FII ₹{f5['fii_net'].sum():,.0f} Cr · "
                f"DII ₹{f5['dii_net'].sum():,.0f} Cr (cumulative net, last 5 sessions)"
            )
        else:
            lines.append(
                f"- **5-Day Trend:** building — only {len(flows)} session(s) of history "
                "(NSE exposes one day per call; accumulates daily)"
            )
        lines.append("")

    # Sectors
    if not rotation.empty:
        ranked = rotation.dropna(subset=["rs_vs_nifty"]).sort_values(
            "rs_vs_nifty", ascending=False)
        strong = ranked.head(5)[["sector", "perf_20d", "rs_vs_nifty", "trend_status"]]
        weak = ranked.tail(5)[["sector", "perf_20d", "rs_vs_nifty", "trend_status"]]
        weak = weak.iloc[::-1]
        lines += ["## Strongest Sectors (Top 5)", "", _md_table(
            strong.rename(columns={"sector": "Sector", "perf_20d": "20D %",
                                   "rs_vs_nifty": "RS vs Nifty", "trend_status": "Trend"})),
            "## Weakest Sectors (Bottom 5)", "", _md_table(
            weak.rename(columns={"sector": "Sector", "perf_20d": "20D %",
                                 "rs_vs_nifty": "RS vs Nifty", "trend_status": "Trend"}))]

    # Institutional watchlist
    lines += ["## Institutional Watchlist (Strong / Improving sectors)", ""]
    if inst.empty:
        lines.append("_No stocks — no Strong/Improving sectors today._\n")
    else:
        view = inst[["symbol", "sector", "sector_trend", "relative_strength",
                     "above_20_sma", "current_price"]].rename(columns={
            "symbol": "Symbol", "sector": "Sector", "sector_trend": "Sector Trend",
            "relative_strength": "Relative Strength", "above_20_sma": "Above 20 SMA",
            "current_price": "Current Price"})
        lines.append(_md_table(view))

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def export_institutional_csv(trade_date: dt.date) -> tuple[str, int]:
    """Write the institutional watchlist CSV. Returns (path, rows)."""
    df = repo.get_institutional_watchlist(trade_date)
    path = REPORTS_DIR / f"institutional_watchlist_{trade_date.isoformat()}.csv"
    cols = {"symbol": "Symbol", "sector": "Sector", "sector_trend": "Sector Trend",
            "relative_strength": "Relative Strength", "above_20_sma": "Above 20 SMA",
            "current_price": "Current Price"}
    if df.empty:
        pd.DataFrame(columns=list(cols.values())).to_csv(path, index=False)
        return str(path), 0
    df[list(cols.keys())].rename(columns=cols).to_csv(path, index=False)
    return str(path), len(df)


_COMBINED_COLUMNS = [
    "symbol", "sector", "catalyst", "relative_strength", "above_20_sma",
    "volume_expansion", "technical_status", "tier",
]
_COMBINED_RENAME = {
    "symbol": "Symbol", "sector": "Sector", "catalyst": "Catalyst",
    "relative_strength": "Relative Strength", "above_20_sma": "Above 20 SMA",
    "volume_expansion": "Volume Expansion", "technical_status": "Technical Status",
    "tier": "Tier",
}
_TIER_REASON = {
    1: "Catalyst + Sector Strength alignment",
    2: "Strong sector leadership",
    3: "Event-driven opportunity requiring further validation",
}


def export_combined_csv(trade_date: dt.date) -> tuple[str, int]:
    """Write the combined watchlist CSV (sorted Tier 1 -> 2 -> 3)."""
    df = repo.get_combined_watchlist(trade_date)
    path = REPORTS_DIR / f"combined_watchlist_{trade_date.isoformat()}.csv"
    if df.empty:
        pd.DataFrame(columns=list(_COMBINED_RENAME.values())).to_csv(path, index=False)
        return str(path), 0
    out = df[_COMBINED_COLUMNS].rename(columns=_COMBINED_RENAME)
    out.to_csv(path, index=False)
    return str(path), len(out)


def generate_combined_report(trade_date: dt.date) -> str:
    """Combined Daily Report: one tiered table per tier, with reasons."""
    df = repo.get_combined_watchlist(trade_date)
    path = REPORTS_DIR / f"combined_report_{trade_date.isoformat()}.md"
    lines = [
        f"# Combined Watchlist — Daily Report ({trade_date.isoformat()})",
        "",
        _REPORT_SUB,
        "",
        "_Confluence of Deal + Institutional watchlists · rule-based · "
        "no scoring / no weighting / no prediction_",
        "",
    ]
    if df.empty:
        lines.append("_No stocks in either source today._\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    for tier in (1, 2, 3):
        sub = df[df["tier"] == tier]
        lines += [
            f"## Tier {tier} — {_TIER_REASON[tier]} ({len(sub)})",
            "",
        ]
        if sub.empty:
            lines.append("_(none)_\n")
            continue
        view = sub[_COMBINED_COLUMNS[:-1]].rename(columns=_COMBINED_RENAME)
        lines.append(_md_table(view))
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def generate_tier_summary(trade_date: dt.date) -> str:
    """Tier Summary Report: counts + how each source contributed."""
    df = repo.get_combined_watchlist(trade_date)
    path = REPORTS_DIR / f"tier_summary_{trade_date.isoformat()}.md"
    lines = [
        f"# Tier Summary Report ({trade_date.isoformat()})",
        "",
        _REPORT_SUB,
        "",
        "_Rule-based confluence. No score, no ranking weight._",
        "",
    ]
    if df.empty:
        lines.append("_No data._\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    counts = pd.DataFrame([
        {"Tier": f"Tier {t}", "Reason": _TIER_REASON[t],
         "Count": int((df["tier"] == t).sum())}
        for t in (1, 2, 3)
    ])
    counts.loc[len(counts)] = ["Total", "", int(len(df))]
    lines += [_md_table(counts), ""]

    # Source contribution.
    both = int(((df["in_deal"] == "Y") & (df["in_institutional"] == "Y")).sum())
    deal_only = int(((df["in_deal"] == "Y") & (df["in_institutional"] == "N")).sum())
    inst_only = int(((df["in_deal"] == "N") & (df["in_institutional"] == "Y")).sum())
    lines += [
        "## Source contribution",
        "",
        _md_table(pd.DataFrame([
            {"Confluence": "In BOTH sources (Tier 1)", "Count": both},
            {"Confluence": "Institutional only (Tier 2)", "Count": inst_only},
            {"Confluence": "Deal only (Tier 3)", "Count": deal_only},
        ])),
        "## How to use this list",
        "",
        "- **Tier 1** — start here: a corporate/deal catalyst *and* sector strength agree.",
        "- **Tier 2** — sector leaders; position-trade candidates riding rotation.",
        "- **Tier 3** — event-driven; confirm the catalyst and technicals before acting.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def generate_institutional_validation_report(trade_date: dt.date, stats: dict,
                                             sources: list[dict]) -> str:
    """Validation report for the FII/DII + sector-rotation module."""
    path = REPORTS_DIR / f"validation_institutional_{trade_date.isoformat()}.md"
    rotation = repo.get_sector_rotation(trade_date)
    inst = repo.get_institutional_watchlist(trade_date)

    lines = [
        f"# FII/DII + Sector Rotation — Validation Report ({trade_date.isoformat()})",
        "",
        _REPORT_SUB,
        "",
        "_Deterministic, rule-based. No scoring · no ML · no prediction._",
        "",
        "## 1. Sources used (real data)",
        "",
        _md_table(pd.DataFrame(sources)),
        "## 2. Counts",
        "",
        f"- FII/DII rows stored: **{stats.get('fii_rows', 0)}** "
        f"(history depth: {stats.get('history_days', 0)} session(s))",
        f"- Sectors classified: **{len(rotation)}**",
        f"- Institutional watchlist stocks: **{len(inst)}**",
        "",
        "## 3. Sector classification distribution",
        "",
    ]
    if not rotation.empty:
        lines.append(_md_table(
            rotation["trend_status"].value_counts().rename_axis("Trend")
            .reset_index(name="Count")))
        lines += ["## 4. Sector detail (with data method)", "",
                  _md_table(rotation[["sector", "perf_20d", "rs_vs_nifty",
                                      "above_20_sma", "above_50_sma", "trend_status",
                                      "data_method"]].rename(columns={
                      "sector": "Sector", "perf_20d": "20D %", "rs_vs_nifty": "RS",
                      "above_20_sma": ">20SMA", "above_50_sma": ">50SMA",
                      "trend_status": "Trend", "data_method": "Method"}))]

    lines += [
        "## 5. Data-quality notes & limitations",
        "",
        "- **FII/DII history:** NSE's public endpoint exposes only the latest "
        "trading day, so the 5-day trend builds forward as the pipeline runs daily. "
        "No reliable free historical backfill was available.",
        "- **Defence:** no usable NSE index series on the data source → sector "
        "performance computed from an equal-weighted constituent **basket** (see Method column).",
        "- **Capital Goods:** uses the Infrastructure index as a documented **proxy** "
        "(NSE has no standalone Capital Goods index on the source).",
        "- **Independence:** this watchlist is generated entirely from sector trend + "
        "stock RS — fully independent of the bulk/block-deal watchlist, so the two "
        "sources can corroborate each other.",
        "",
        "## 6. Verdict",
        "",
        f"Module produces a clean, actionable institutional watchlist of "
        f"**{len(inst)} stocks** across "
        f"**{stats.get('strong_improving', 0)} Strong/Improving sectors**, with real "
        "FII/DII flow context. Ready to serve as a second watchlist candidate source.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


_CA_COLUMNS = ["announcement_date", "symbol", "company_name", "event_type",
               "impact_tag", "priority", "event_summary", "source"]
_CA_RENAME = {
    "announcement_date": "Date", "symbol": "Symbol", "company_name": "Company",
    "event_type": "Event Type", "impact_tag": "Impact", "priority": "Priority",
    "event_summary": "Summary", "source": "Source",
}
_CA_PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def _ca_sorted(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["_p"] = d["priority"].map(_CA_PRIORITY_ORDER).fillna(9)
    return d.sort_values(["_p", "announcement_date"], ascending=[True, False]).drop(columns="_p")


def export_corp_actions_csv(trade_date: dt.date, df: pd.DataFrame) -> tuple[str, int]:
    """Corporate Action Watchlist CSV (sorted High -> Medium -> Low)."""
    path = REPORTS_DIR / f"corp_actions_watchlist_{trade_date.isoformat()}.csv"
    if df.empty:
        pd.DataFrame(columns=list(_CA_RENAME.values())).to_csv(path, index=False)
        return str(path), 0
    out = _ca_sorted(df)[_CA_COLUMNS].rename(columns=_CA_RENAME)
    out.to_csv(path, index=False)
    return str(path), len(out)


def generate_corp_actions_report(trade_date: dt.date, df: pd.DataFrame) -> str:
    """Daily Corporate Actions Report grouped by priority."""
    path = REPORTS_DIR / f"corp_actions_report_{trade_date.isoformat()}.md"
    lines = [
        f"# Daily Corporate Actions Report ({trade_date.isoformat()})",
        "",
        _REPORT_SUB,
        "",
        "_Rule-based classification · no scoring / no ML / no prediction_",
        "",
    ]
    if df.empty:
        lines.append("_No tracked corporate actions._\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    cols = ["symbol", "company_name", "event_type", "impact_tag", "event_summary"]
    rename = {"symbol": "Symbol", "company_name": "Company", "event_type": "Event Type",
              "impact_tag": "Impact", "event_summary": "Summary"}
    for prio in ("High", "Medium", "Low"):
        sub = df[df["priority"] == prio]
        lines += [f"## {prio} Priority ({len(sub)})", ""]
        if sub.empty:
            lines.append("_(none)_\n")
            continue
        view = sub[cols].copy()
        view["event_summary"] = view["event_summary"].str.slice(0, 90)
        lines.append(_md_table(view.rename(columns=rename)))
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def generate_corp_actions_validation(trade_date: dt.date, df: pd.DataFrame,
                                     stats: dict, sources: list[dict]) -> str:
    """Validation report for the corporate-actions module."""
    path = REPORTS_DIR / f"validation_corp_actions_{trade_date.isoformat()}.md"
    lines = [
        f"# Corporate Actions — Validation Report ({trade_date.isoformat()})",
        "",
        _REPORT_SUB,
        "",
        "_Deterministic, rule-based. No scoring · no ML · no prediction._",
        "",
        "## 1. Sources used (real data)",
        "",
        _md_table(pd.DataFrame(sources)),
        "## 2. Counts",
        "",
        f"- Raw announcements + actions fetched: **{stats.get('raw', 0)}**",
        f"- Tracked events classified & stored: **{stats.get('stored', 0)}**",
        f"- Untracked (filtered as noise): **{stats.get('raw', 0) - stats.get('classified', 0)}**",
        "",
        "## 3. Event-type distribution",
        "",
    ]
    if not df.empty:
        lines.append(_md_table(df["event_type"].value_counts()
                               .rename_axis("Event Type").reset_index(name="Count")))
        lines += ["## 4. Priority distribution", "",
                  _md_table(df["priority"].value_counts()
                            .rename_axis("Priority").reset_index(name="Count")),
                  "## 5. Impact distribution", "",
                  _md_table(df["impact_tag"].value_counts()
                            .rename_axis("Impact").reset_index(name="Count"))]
    lines += [
        "## 6. Notes & limitations",
        "",
        "- Sources: NSE corporate-announcements (free-text) + corporate-actions "
        "(structured). Both expose the latest batch; history accumulates forward.",
        "- Event type is classified by transparent keyword rules; untracked "
        "announcements (board-meeting outcomes, newspaper publications, trading-window "
        "notices) are filtered out by design.",
        "- Impact/priority are fixed rule-based mappings per event type — no scores.",
        "- **Independence:** built only from announcements — fully independent of the "
        "deal-flow and institutional watchlists; can be cross-referenced with them.",
        "",
        "## 7. Verdict",
        "",
        f"Module produced **{stats.get('stored', 0)} tracked corporate-action events** "
        "across High/Medium/Low priorities from real NSE feeds. Ready as a third "
        "independent watchlist candidate source.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


_RES_COLUMNS = ["symbol", "company_name", "quarter", "revenue_growth_pct",
                "profit_growth_pct", "margin_change_pct", "result_classification"]
_RES_RENAME = {
    "symbol": "Symbol", "company_name": "Company", "quarter": "Quarter",
    "revenue_growth_pct": "Revenue Growth %", "profit_growth_pct": "Profit Growth %",
    "margin_change_pct": "Margin Change %", "result_classification": "Result Classification",
}
_RES_ORDER = {"Strong": 0, "Neutral": 1, "Weak": 2}


def _res_sorted(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["_c"] = d["result_classification"].map(_RES_ORDER).fillna(9)
    d["_p"] = d["profit_growth_pct"].fillna(-9999)
    return d.sort_values(["_c", "_p"], ascending=[True, False]).drop(columns=["_c", "_p"])


def export_results_csv(period_end: dt.date, df: pd.DataFrame) -> tuple[str, int]:
    """Results Watchlist CSV (sorted Strong -> Neutral -> Weak)."""
    path = REPORTS_DIR / f"results_watchlist_{period_end.isoformat()}.csv"
    if df.empty:
        pd.DataFrame(columns=list(_RES_RENAME.values())).to_csv(path, index=False)
        return str(path), 0
    out = _res_sorted(df)[_RES_COLUMNS].rename(columns=_RES_RENAME)
    out.to_csv(path, index=False)
    return str(path), len(out)


def generate_results_report(period_end: dt.date, df: pd.DataFrame) -> str:
    """Daily Results Report grouped by classification."""
    path = REPORTS_DIR / f"results_report_{period_end.isoformat()}.md"
    lines = [
        f"# Daily Results Report — {period_end.isoformat()}",
        "",
        _REPORT_SUB,
        "",
        "_Rule-based classification · YoY growth · no scoring / no ML / no prediction_",
        "",
    ]
    if df.empty:
        lines.append("_No results available._\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    quarter = df["quarter"].mode().iloc[0] if not df["quarter"].mode().empty else ""
    lines.append(f"_Reporting period: **{quarter}** (period end {period_end.isoformat()})_\n")
    for cls in ("Strong", "Neutral", "Weak"):
        sub = _res_sorted(df[df["result_classification"] == cls])
        lines += [f"## {cls} Results ({len(sub)})", ""]
        if sub.empty:
            lines.append("_(none)_\n")
            continue
        view = sub[["symbol", "revenue_growth_pct", "profit_growth_pct",
                    "margin_change_pct"]].rename(columns={
            "symbol": "Symbol", "revenue_growth_pct": "Revenue Growth %",
            "profit_growth_pct": "Profit Growth %", "margin_change_pct": "Margin Change %"})
        lines.append(_md_table(view))
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def generate_results_validation(period_end: dt.date, df: pd.DataFrame,
                                stats: dict, sources: list[dict]) -> str:
    """Validation report for the results-tracker module."""
    path = REPORTS_DIR / f"validation_results_{period_end.isoformat()}.md"
    lines = [
        f"# Results Tracker — Validation Report ({period_end.isoformat()})",
        "",
        _REPORT_SUB,
        "",
        "_Deterministic, rule-based. No scoring · no ML · no prediction._",
        "",
        "## 1. Source used (real data)",
        "",
        _md_table(pd.DataFrame(sources)),
        "## 2. Counts",
        "",
        f"- Universe processed: **{stats.get('processed', 0)}**",
        f"- Symbols with usable financials: **{stats.get('with_data', 0)}**",
        f"- Results stored: **{stats.get('stored', 0)}**",
        "",
        "## 3. Classification distribution",
        "",
    ]
    if not df.empty:
        lines.append(_md_table(df["result_classification"].value_counts()
                               .rename_axis("Classification").reset_index(name="Count")))
        lines += ["## 4. Growth-basis distribution", "",
                  _md_table(df["basis"].value_counts()
                            .rename_axis("Basis").reset_index(name="Count"))]
    lines += [
        "## 5. Notes & limitations",
        "",
        "- Source: yfinance quarterly income statements (Total Revenue, Net Income). "
        "Growth is **YoY** (latest quarter vs the same quarter a year ago); QoQ is a "
        "fallback when fewer than 5 quarters are available.",
        "- **Margin** = net profit margin (Net Income / Revenue); margin change is in "
        "percentage points.",
        "- Growth off a **loss-making base** is not meaningful and is shown as '-' "
        "(classification then leans Neutral).",
        "- **Management guidance** is not available from this source → not captured "
        "(would require earnings-call transcripts / a paid feed).",
        "- **Beat/Miss vs estimates** is intentionally NOT computed — it needs analyst "
        "consensus (paid). This module classifies on absolute YoY growth only.",
        "- **Independence:** derived purely from financial statements — independent of "
        "deal-flow, institutional and corporate-action sources.",
        "",
        "## 6. Verdict",
        "",
        f"Module produced **{stats.get('stored', 0)} classified quarterly results** "
        "from real financial statements. Ready as a fourth independent watchlist "
        "candidate source.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def _perf_agg(df: pd.DataFrame, group_col: str, ret_col: str) -> pd.DataFrame:
    """Aggregate forward-return performance by a grouping column."""
    rows = []
    for key, g in df.groupby(group_col):
        evaluated = g[g[ret_col].notna()]
        n_eval = len(evaluated)
        if n_eval == 0:
            rows.append({group_col: key, "Signals": len(g), "Evaluated": 0,
                         "Win Rate": "-", "Avg %": "-", "Median %": "-",
                         "Best %": "-", "Worst %": "-"})
            continue
        wins = (evaluated[ret_col] > 0).sum()
        rows.append({
            group_col: key, "Signals": len(g), "Evaluated": n_eval,
            "Win Rate": f"{wins / n_eval * 100:.0f}%",
            "Avg %": round(evaluated[ret_col].mean(), 2),
            "Median %": round(evaluated[ret_col].median(), 2),
            "Best %": round(evaluated[ret_col].max(), 2),
            "Worst %": round(evaluated[ret_col].min(), 2),
        })
    return pd.DataFrame(rows)


def generate_signal_validation_report(run_date: dt.date, stats: dict) -> str:
    """Engine Performance report from the signals table (measurement only)."""
    path = REPORTS_DIR / f"signal_validation_{run_date.isoformat()}.md"
    sig = repo.get_signals()
    lines = [
        f"# Signal Validation — Engine Performance ({run_date.isoformat()})",
        "",
        _REPORT_SUB,
        "",
        "_Measurement & feedback only · real forward returns · "
        "no scoring / no ranking / no prediction_",
        "",
        "## Coverage",
        "",
        f"- Signals tracked: **{stats.get('signals', 0)}**",
        f"- Fully evaluated (1/5/20d all available): **{stats.get('evaluated', 0)}**",
        f"- Partially evaluated: **{stats.get('partial', 0)}**",
        f"- Pending (forward window not elapsed): "
        f"**{stats.get('signals', 0) - stats.get('evaluated', 0) - stats.get('partial', 0) - stats.get('no_price', 0)}**",
        f"- No price data: **{stats.get('no_price', 0)}**",
        "",
        "> Win rate / averages are computed only over signals whose horizon has "
        "elapsed. Recently-generated signals stay pending until enough trading days pass.",
        "",
    ]
    if sig.empty:
        lines.append("_No signals captured._\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)

    # Headline summary per horizon.
    for col, label in (("ret_1d", "1-Day"), ("ret_5d", "5-Day"), ("ret_20d", "20-Day")):
        agg = _perf_agg(sig, "source_engine", col)
        agg = agg.rename(columns={"source_engine": "Engine"})
        total_eval = int((sig[col].notna()).sum())
        lines += [f"## {label} Forward Return — by Engine "
                  f"({total_eval} evaluated)", "", _md_table(agg)]

    # Results breakdown by classification.
    res = sig[sig["source_engine"] == "Results"]
    if not res.empty:
        lines += ["## Results Engine — by Classification (best available horizon)", ""]
        col = _best_horizon(res)
        agg = _perf_agg(res, "signal_type", col).rename(columns={"signal_type": "Classification"})
        lines += [f"_Horizon shown: {col.replace('ret_', '').upper()}_", "", _md_table(agg)]

    # Confluence breakdown by tier.
    conf = sig[sig["source_engine"] == "Confluence"]
    if not conf.empty:
        lines += ["## Confluence Engine — by Tier (best available horizon)", ""]
        col = _best_horizon(conf)
        agg = _perf_agg(conf, "signal_type", col).rename(columns={"signal_type": "Tier"})
        lines += [f"_Horizon shown: {col.replace('ret_', '').upper()}_", "", _md_table(agg)]

    lines += [
        "## Notes",
        "",
        "- **Win** = positive absolute forward return. Returns are price-only "
        "(close-to-close), not benchmark-excess.",
        "- **Results** signals are dated at the actual earnings announcement date "
        "(yfinance), so the window reflects the post-results reaction.",
        "- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day "
        "windows fill in as the system runs daily.",
        "- This layer only measures — it does not rank or weight engines.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def export_signals_csv(run_date: dt.date) -> tuple[str, int]:
    """Raw signals + forward returns CSV."""
    sig = repo.get_signals()
    path = REPORTS_DIR / f"signals_{run_date.isoformat()}.csv"
    cols = {"signal_date": "Signal Date", "symbol": "Symbol",
            "source_engine": "Source Engine", "signal_type": "Signal Type",
            "entry_price": "Entry Price", "ret_1d": "1D %", "ret_5d": "5D %",
            "ret_20d": "20D %", "status": "Status"}
    if sig.empty:
        pd.DataFrame(columns=list(cols.values())).to_csv(path, index=False)
        return str(path), 0
    sig[list(cols.keys())].rename(columns=cols).to_csv(path, index=False)
    return str(path), len(sig)


def _best_horizon(df: pd.DataFrame) -> str:
    """Pick the longest horizon with the most evaluated rows."""
    for col in ("ret_20d", "ret_5d", "ret_1d"):
        if df[col].notna().any():
            return col
    return "ret_1d"


def generate_source_report(trade_date: dt.date, sources: list[dict]) -> str:
    """Source Success/Failure Report (markdown)."""
    path = REPORTS_DIR / f"source_report_{trade_date.isoformat()}.md"
    df = pd.DataFrame(sources)
    lines = [
        f"# Source Success/Failure Report — {trade_date.isoformat()}",
        "",
        _REPORT_SUB,
        "",
        _md_table(df),
        "",
        "_status: OK = live data fetched · FALLBACK = seed used · "
        "EMPTY = reachable but no records · FAIL = unreachable_",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
