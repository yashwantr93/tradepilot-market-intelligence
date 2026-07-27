"""
Daily watchlist rule engine.

Reduces the universe to a research list using ONLY deterministic rules on real,
stored data. No score, no prediction, no ML. Each entry records exactly which
rules fired (its catalysts) plus descriptive technical fields.

Catalyst rules (BUY-side qualify a symbol; NET_SELL is a caution tag only):
  BIG_BULK_BUY · BIG_BLOCK_BUY · MARQUEE_BUYER · REPEAT_BUYING · TOP_SECTOR
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from core.config import MARQUEE_BUYERS, WATCHLIST as W
from core.db import repository as repo
from core.processing import technicals
from core.utils.logging import get_logger

log = get_logger(__name__)

CR = 10_000_000  # 1 crore in rupees

# Catalyst priority — first match becomes the headline catalyst_tag.
_CATALYST_PRIORITY = [
    "BIG_BLOCK_BUY", "BIG_BULK_BUY", "MARQUEE_BUYER", "REPEAT_BUYING", "TOP_SECTOR",
]


def _deal_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """Per-symbol gross BUY value, net value and net qty.

    Bulk/block deals report both sides of crossed trades, so *net* value often
    cancels to ~0. The actionable buy-side signal is therefore GROSS BUY value
    (total ₹ bought); *net* is retained to flag accumulation vs churn vs selling.
    """
    if df.empty:
        return pd.DataFrame(columns=["symbol", "gross_buy", "net_value", "net_qty"])
    sign = df["txn_type"].map({"BUY": 1, "SELL": -1}).fillna(0)
    buy_only = df["value"].where(df["txn_type"] == "BUY", 0.0)
    tmp = df.assign(_v=df["value"] * sign, _q=df["quantity"] * sign, _b=buy_only)
    return (tmp.groupby("symbol")
            .agg(gross_buy=("_b", "sum"), net_value=("_v", "sum"), net_qty=("_q", "sum"))
            .reset_index())


def _top_sectors(symbol_map: dict[str, dict], n: int) -> set[str]:
    """Top-N sectors by average constituent 1-day return (from price_history)."""
    rows = []
    for sym, meta in symbol_map.items():
        hist = repo.get_price_history(sym, lookback=2)
        if len(hist) >= 2:
            chg = (hist["close"].iloc[-1] / hist["close"].iloc[-2] - 1) * 100
            rows.append({"sector": meta.get("sector"), "chg": chg})
    if not rows:
        return set()
    perf = (pd.DataFrame(rows).dropna(subset=["sector"])
            .groupby("sector")["chg"].mean().sort_values(ascending=False))
    return set(perf.head(n).index)


def _is_marquee(client: str) -> bool:
    c = (client or "").upper()
    return any(m.upper() in c for m in MARQUEE_BUYERS)


def generate_watchlist(trade_date: dt.date) -> int:
    """Build and persist the watchlist for a trade date. Returns row count."""
    job_id = repo.start_job("watchlist_generation", source="rules")
    try:
        symbol_map = repo.get_symbol_map()
        lookback_start = trade_date - dt.timedelta(days=W["repeat_lookback_days"] * 2)

        bulk = repo.get_deals("bulk", since=lookback_start)
        block = repo.get_deals("block", since=lookback_start)
        bulk_today = bulk[bulk["trade_date"] == trade_date] if not bulk.empty else bulk
        block_today = block[block["trade_date"] == trade_date] if not block.empty else block

        bulk_agg = _deal_aggregates(bulk_today)
        block_agg = _deal_aggregates(block_today)
        top_sectors = _top_sectors(symbol_map, W["top_sector_count"])
        bench_ret = technicals.benchmark_return()

        # Collect candidates + their fired rules.
        candidates: dict[str, dict] = {}

        def _ensure(sym: str) -> dict:
            return candidates.setdefault(
                sym, {"reasons": [], "deal_value": 0.0, "net_qty": 0, "caution": []}
            )

        # Rule: BIG_BULK_BUY — gross buy-side value (net cancels for crossed deals)
        for _, r in bulk_agg.iterrows():
            if r["gross_buy"] >= W["big_bulk_buy_cr"] * CR:
                c = _ensure(r["symbol"])
                c["reasons"].append("BIG_BULK_BUY")
                c["deal_value"] += r["gross_buy"]
                c["net_qty"] += int(r["net_qty"])
            if r["net_value"] <= -W["net_sell_caution_cr"] * CR:
                _ensure(r["symbol"])["caution"].append("NET_SELL")

        # Rule: BIG_BLOCK_BUY
        for _, r in block_agg.iterrows():
            if r["gross_buy"] >= W["big_block_buy_cr"] * CR:
                c = _ensure(r["symbol"])
                c["reasons"].append("BIG_BLOCK_BUY")
                c["deal_value"] += r["gross_buy"]
                c["net_qty"] += int(r["net_qty"])
            if r["net_value"] <= -W["net_sell_caution_cr"] * CR:
                _ensure(r["symbol"])["caution"].append("NET_SELL")

        # Rule: MARQUEE_BUYER (any BUY by a marquee name today)
        all_today = pd.concat([d for d in (bulk_today, block_today) if not d.empty],
                              ignore_index=True) if (not bulk_today.empty or not block_today.empty) \
            else pd.DataFrame()
        if not all_today.empty:
            buys = all_today[all_today["txn_type"] == "BUY"]
            for sym in buys[buys["client_name"].map(_is_marquee)]["symbol"].unique():
                _ensure(sym)["reasons"].append("MARQUEE_BUYER")

        # Rule: REPEAT_BUYING (net BUY on >= min_sessions of last lookback sessions)
        for sym in symbol_map:
            sessions = _buy_sessions(bulk, block, sym, trade_date)
            if sessions >= W["repeat_min_sessions"]:
                _ensure(sym)["reasons"].append("REPEAT_BUYING")

        # Rule: TOP_SECTOR (only for symbols already flagged by a deal rule —
        # sector strength is a confirming catalyst, not a standalone trigger)
        for sym, c in list(candidates.items()):
            sector = symbol_map.get(sym, {}).get("sector")
            if sector in top_sectors and c["reasons"]:
                c["reasons"].append("TOP_SECTOR")

        # Materialize rows with technicals.
        rows = []
        for sym, c in candidates.items():
            buy_reasons = [r for r in c["reasons"] if r != "NET_SELL"]
            if not buy_reasons:
                continue  # caution-only symbols don't make the list
            reasons = sorted(set(buy_reasons)) + sorted(set(c["caution"]))
            meta = symbol_map.get(sym, {})
            tech = technicals.compute_technicals(sym, bench_ret)
            rows.append({
                "trade_date": trade_date, "symbol": sym,
                "isin": meta.get("isin"), "company_name": meta.get("company_name"),
                "sector": meta.get("sector"),
                "current_price": tech["current_price"],
                "catalyst_tag": _pick_catalyst(reasons),
                "reasons": reasons,
                "above_20_sma": tech["above_20_sma"],
                "relative_strength": tech["relative_strength"],
                "volume_expansion": tech["volume_expansion"],
                "sma_20": tech["sma_20"],
                "high_52w": tech["high_52w"],
                "low_52w": tech["low_52w"],
                "dist_52w_high_pct": tech["dist_52w_high_pct"],
                "dist_52w_low_pct": tech["dist_52w_low_pct"],
                "technical_status": tech["technical_status"],
                "deal_value": round(c["deal_value"], 2),
                "net_qty": int(c["net_qty"]),
                "rule_count": len(set(buy_reasons)),
            })

        rows.sort(key=lambda x: (x["rule_count"], x["deal_value"] or 0), reverse=True)
        n = repo.replace_watchlist(trade_date, rows)
        repo.finish_job(job_id, "ok", rows_in=len(candidates), rows_out=n)
        log.info("Watchlist for %s: %d names from %d candidates",
                 trade_date, n, len(candidates))
        return n
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("Watchlist generation failed")
        raise


def _buy_sessions(bulk: pd.DataFrame, block: pd.DataFrame, symbol: str,
                  trade_date: dt.date) -> int:
    """Count distinct sessions in the lookback window with a net BUY for symbol."""
    start = trade_date - dt.timedelta(days=W["repeat_lookback_days"] * 2)
    frames = [d for d in (bulk, block) if not d.empty]
    if not frames:
        return 0
    df = pd.concat(frames, ignore_index=True)
    df = df[(df["symbol"] == symbol) & (df["trade_date"] >= start)
            & (df["trade_date"] <= trade_date)]
    if df.empty:
        return 0
    sign = df["txn_type"].map({"BUY": 1, "SELL": -1}).fillna(0)
    df = df.assign(_v=df["value"] * sign)
    per_day = df.groupby("trade_date")["_v"].sum()
    return int((per_day > 0).sum())


def _pick_catalyst(reasons: list[str]) -> str:
    for tag in _CATALYST_PRIORITY:
        if tag in reasons:
            return tag
    return reasons[0] if reasons else "—"
