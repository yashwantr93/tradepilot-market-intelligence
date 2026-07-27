"""
Combined Watchlist (Confluence) Engine.

Merges the two existing, independent watchlist sources into one tiered research
list. Pure set logic + field merge — NO scoring, NO weighting, NO prediction.

Tiers
-----
  Tier 1 : in BOTH the deal watchlist AND the institutional watchlist
           -> catalyst + sector-strength alignment (highest priority)
  Tier 2 : institutional watchlist only
           -> strong sector leadership
  Tier 3 : deal watchlist only
           -> event-driven, needs further validation

Field provenance
----------------
  Catalyst / Volume Expansion / Technical Status come from the DEAL pipeline.
  For institutional-only stocks (Tier 2) the catalyst is the sector trend and the
  deal-only technicals are shown as "-" (their RS / 20-SMA / sector trend are the
  relevant signals). Tier 1 prefers the richer deal-pipeline technicals.
"""

from __future__ import annotations

import datetime as dt

from core.db import repository as repo
from core.utils.logging import get_logger

log = get_logger(__name__)

NA = "-"


def build_combined_watchlist(trade_date: dt.date) -> int:
    """Build & persist the tiered combined watchlist. Returns row count."""
    job_id = repo.start_job("combined_watchlist", source="confluence")
    try:
        deal = repo.get_watchlist(trade_date)
        inst = repo.get_institutional_watchlist(trade_date)

        deal_map = {r["symbol"]: r for _, r in deal.iterrows()} if not deal.empty else {}
        inst_map = {r["symbol"]: r for _, r in inst.iterrows()} if not inst.empty else {}
        all_symbols = sorted(set(deal_map) | set(inst_map))

        rows = []
        for sym in all_symbols:
            d = deal_map.get(sym)
            i = inst_map.get(sym)
            in_deal = d is not None
            in_inst = i is not None

            if in_deal and in_inst:
                tier = 1
            elif in_inst:
                tier = 2
            else:
                tier = 3

            rows.append({
                "trade_date": trade_date,
                "symbol": sym,
                "sector": _pick(d, i, "sector"),
                "catalyst": _catalyst(d, i),
                "relative_strength": _pick(d, i, "relative_strength"),
                "above_20_sma": _pick(d, i, "above_20_sma"),
                "volume_expansion": d["volume_expansion"] if in_deal else NA,
                "technical_status": d["technical_status"] if in_deal else NA,
                "in_deal": "Y" if in_deal else "N",
                "in_institutional": "Y" if in_inst else "N",
                "tier": tier,
            })

        # Sort: Tier 1 -> 2 -> 3; within tier, Strong RS first, then symbol.
        rs_rank = {"Strong": 0, "Neutral": 1, "Weak": 2, None: 3, NA: 3}
        rows.sort(key=lambda x: (x["tier"], rs_rank.get(x["relative_strength"], 3),
                                 x["symbol"]))
        n = repo.replace_combined_watchlist(trade_date, rows)

        tiers = {1: 0, 2: 0, 3: 0}
        for r in rows:
            tiers[r["tier"]] += 1
        repo.finish_job(job_id, "ok", rows_in=len(all_symbols), rows_out=n)
        log.info("Combined watchlist %s: Tier1=%d Tier2=%d Tier3=%d (total %d)",
                 trade_date, tiers[1], tiers[2], tiers[3], n)
        return n
    except Exception as e:  # noqa: BLE001
        repo.finish_job(job_id, "error", error=str(e))
        log.exception("Combined watchlist failed")
        raise


def _pick(d, i, field: str):
    """Prefer deal-pipeline value, else institutional value, else '-'."""
    if d is not None and field in d and d[field] not in (None, ""):
        return d[field]
    if i is not None and field in i and i[field] not in (None, ""):
        return i[field]
    return NA


def _catalyst(d, i) -> str:
    """Compose the catalyst string from whichever sources are present."""
    parts = []
    if d is not None and d.get("catalyst_tag"):
        parts.append(str(d["catalyst_tag"]))
    if i is not None and i.get("sector_trend"):
        parts.append(f"{i['sector_trend']} Sector")
    return " + ".join(parts) if parts else NA
