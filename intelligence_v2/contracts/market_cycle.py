"""
Market Cycle dashboard contract — read-only bridge for the Market Cycle page.

Reads only from market_v2.db via the service/repository layer; performs no
calculation of its own and never touches V1.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from intelligence_v2.config.market_cycle import (
    CYCLE_STAGES,
    CYCLE_WHEEL_ORDER,
    MIN_CYCLE_CONFIRMATIONS,
    MIN_CYCLE_DWELL_DAYS,
    STAGE_RULES_DOC,
)
from intelligence_v2.database import cycle_repository as crepo
from intelligence_v2.services import market_cycle as svc


@st.cache_data(ttl=120)
def is_data_available() -> bool:
    return bool(crepo.get_distinct_cycle_dates())


@st.cache_data(ttl=120)
def get_current_market_cycle() -> pd.DataFrame:
    df = svc.get_current_market_cycle()
    if df.empty:
        return df
    df["_order"] = df["stage"].map(CYCLE_WHEEL_ORDER).fillna(99)
    return df.sort_values(["_order", "sector"]).drop(columns="_order").reset_index(drop=True)


@st.cache_data(ttl=120)
def get_stage_distribution() -> pd.DataFrame:
    return svc.get_stage_distribution()


@st.cache_data(ttl=120)
def get_sector_cycle_history(sector: str) -> pd.DataFrame:
    return svc.get_sector_cycle_history(sector)


@st.cache_data(ttl=120)
def get_transition_history(sector: str | None = None) -> pd.DataFrame:
    return svc.get_transition_history(sector=sector)


@st.cache_data(ttl=120)
def get_sector_list() -> list[str]:
    df = svc.get_current_market_cycle()
    return sorted(df["sector"].unique()) if not df.empty else []


@st.cache_data(ttl=120)
def get_cycle_meta() -> dict:
    dates = crepo.get_distinct_cycle_dates()
    return {
        "latest_date": dates[-1] if dates else None,
        "days_of_history": len(dates),
        "stages": list(CYCLE_STAGES),
        "dwell_days": MIN_CYCLE_DWELL_DAYS,
        "confirmations": MIN_CYCLE_CONFIRMATIONS,
    }


def get_rules_doc() -> list[dict]:
    """The documented rule set, for the in-page explainability expander."""
    return STAGE_RULES_DOC
