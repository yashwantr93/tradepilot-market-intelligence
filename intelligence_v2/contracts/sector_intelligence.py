"""
Sector Intelligence dashboard contract — the ONLY bridge the new Streamlit
page is allowed to use. Read-only over `market_v2.db` (via the service/
repository layer); never touches V1, never computes anything itself.

Mirrors V1's `data/contracts.py` caching convention (`st.cache_data`) for
consistency, but is a fully independent file.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from intelligence_v2.config.sectors import CONSISTENCY_LOOKBACK_DAYS, SECTOR_BASKETS
from intelligence_v2.database import sector_repository as repo

STATE_ORDER = ["Strong Leader", "Early Momentum", "Improving", "Sideways",
              "Weakening", "Downtrend", "Recovery"]


@st.cache_data(ttl=120)
def get_sector_list() -> list[str]:
    return sorted(SECTOR_BASKETS.keys())


@st.cache_data(ttl=120)
def get_overview() -> pd.DataFrame:
    """Latest snapshot, all sectors — the Overview tab's source."""
    df = repo.get_latest_all_sectors()
    if df.empty:
        return df
    df["_order"] = df["state"].map({s: i for i, s in enumerate(STATE_ORDER)}).fillna(99)
    return df.sort_values(["_order", "sector"]).drop(columns="_order").reset_index(drop=True)


@st.cache_data(ttl=120)
def get_performance_table() -> pd.DataFrame:
    """Multi-horizon performance/RS table, latest date — the Performance tab's source."""
    return get_overview()


@st.cache_data(ttl=120)
def get_sector_history(sector: str) -> pd.DataFrame:
    """Full stored history for one sector, oldest first — the History tab's source."""
    return repo.get_history(sector)


@st.cache_data(ttl=120)
def get_state_distribution() -> pd.DataFrame:
    df = get_overview()
    if df.empty:
        return pd.DataFrame(columns=["state", "count"])
    counts = df["state"].value_counts().reindex(STATE_ORDER).fillna(0).astype(int)
    return counts.rename_axis("state").reset_index(name="count")


@st.cache_data(ttl=120)
def get_freshness() -> dict:
    """How much classification history has accumulated (honesty, not a metric
    to game) — mirrors V1's freshness-badge convention."""
    dates = repo.get_distinct_dates()
    if not dates:
        return {"latest_date": None, "days_of_history": 0,
               "consistency_lookback_days": CONSISTENCY_LOOKBACK_DAYS}
    return {
        "latest_date": dates[-1],
        "days_of_history": len(dates),
        "consistency_lookback_days": CONSISTENCY_LOOKBACK_DAYS,
    }


def is_data_available() -> bool:
    return bool(repo.get_distinct_dates())
