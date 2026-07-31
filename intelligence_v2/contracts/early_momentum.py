"""
Early Momentum dashboard contract — read-only bridge for the Early Momentum page.

Reads only from market_v2.db via the service/repository layer; performs no
calculation of its own.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from intelligence_v2.config.early_momentum import (
    CATEGORIES,
    CATEGORY_MEANING,
    CATEGORY_RULES_DOC,
    RANKING_KEYS_DOC,
    SIGNAL_DEFINITIONS,
)
from intelligence_v2.database import momentum_repository as repo
from intelligence_v2.services import early_momentum as svc


@st.cache_data(ttl=120)
def is_data_available() -> bool:
    return bool(repo.get_distinct_dates())


@st.cache_data(ttl=120)
def get_category(category: str) -> pd.DataFrame:
    df = svc.get_latest(category)
    if df.empty:
        return df
    return df.sort_values("rank_in_category").reset_index(drop=True)


@st.cache_data(ttl=120)
def get_category_counts() -> dict[str, int]:
    return svc.get_category_counts()


@st.cache_data(ttl=120)
def get_symbol_history(symbol: str) -> pd.DataFrame:
    return svc.get_symbol_history(symbol)


@st.cache_data(ttl=120)
def get_category_history() -> pd.DataFrame:
    return svc.get_category_history()


@st.cache_data(ttl=120)
def get_all_symbols() -> list[str]:
    df = svc.get_latest()
    return sorted(df["symbol"].unique()) if not df.empty else []


@st.cache_data(ttl=120)
def get_meta() -> dict:
    dates = repo.get_distinct_dates()
    latest = svc.get_latest()
    mapped = int(latest["sector"].notna().sum()) if not latest.empty else 0
    return {
        "latest_date": dates[-1] if dates else None,
        "days_of_history": len(dates),
        "universe_size": len(latest) if not latest.empty else 0,
        "sector_mapped": mapped,
        "categories": list(CATEGORIES),
    }


def get_signal_definitions() -> list[dict]:
    return SIGNAL_DEFINITIONS


def get_category_rules() -> list[dict]:
    return CATEGORY_RULES_DOC


def get_ranking_doc() -> str:
    return RANKING_KEYS_DOC


def get_category_meaning(category: str) -> str:
    return CATEGORY_MEANING.get(category, "")
