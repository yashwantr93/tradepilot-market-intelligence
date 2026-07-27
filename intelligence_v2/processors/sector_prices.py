"""
Builds sector and benchmark price series from V1's `price_history` table via
the read-only bridge — the "use existing V1 sector data" data path for Phase 1.

Method: each basket member's close series is individually rebased to 100 at
its own first available date, then averaged (skipping members without data on
a given day) — the exact same equal-weighted-basket technique V1's own
`core/processing/market_data.py::get_basket_series` uses, reimplemented here
as independent V2 code reading from V1's stored table instead of calling
yfinance fresh. No new external connector was needed for this phase.
"""

from __future__ import annotations

import pandas as pd

from intelligence_v2.config.sectors import (
    MIN_BASKET_MEMBERS,
    NIFTY_BENCHMARK_SYMBOL,
    SECTOR_BASKETS,
)
from intelligence_v2.database.v1_reference import read_v1
from intelligence_v2.utils.logging_v2 import get_v2_logger

log = get_v2_logger("processors.sector_prices")


def _get_closes(symbols: list[str]) -> dict[str, pd.Series]:
    """Bulk-fetch close series for multiple symbols in one V1 read."""
    if not symbols:
        return {}
    placeholders = {f"s{i}": sym for i, sym in enumerate(symbols)}
    in_clause = ", ".join(f":{k}" for k in placeholders)
    sql = (f"SELECT symbol, trade_date, close FROM price_history "
          f"WHERE symbol IN ({in_clause}) ORDER BY trade_date")
    df = read_v1(sql, placeholders)
    if df.empty:
        return {}
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    out = {}
    for sym, g in df.groupby("symbol"):
        s = g.set_index("trade_date")["close"].sort_index()
        out[sym] = s
    return out


def build_basket_series(sector: str) -> tuple[pd.Series, int, int]:
    """Rebased, equal-weighted basket-average series for a sector.

    Returns (series, members_used, members_total). `series` is empty if fewer
    than MIN_BASKET_MEMBERS members have any data at all.
    """
    symbols = SECTOR_BASKETS[sector]
    closes = _get_closes(symbols)
    members_total = len(symbols)
    members_used = len(closes)

    if members_used < MIN_BASKET_MEMBERS:
        log.warning("Sector %s: only %d/%d basket members have price history — "
                   "skipping (below MIN_BASKET_MEMBERS)", sector, members_used, members_total)
        return pd.Series(dtype=float), members_used, members_total

    if members_used < members_total:
        log.info("Sector %s: basket average using %d/%d members (missing: %s)",
                 sector, members_used, members_total,
                 sorted(set(symbols) - set(closes.keys())))

    rebased = []
    for sym, s in closes.items():
        s = s.dropna()
        if s.empty:
            continue
        rebased.append((s / s.iloc[0]) * 100.0)

    if not rebased:
        return pd.Series(dtype=float), 0, members_total

    # NOTE: pd.concat(axis=1) does NOT guarantee a sorted result index when the
    # input series have differing date sets (common here — basket members have
    # staggered listing/gap dates) — it were previously silently producing an
    # unsorted index, which corrupted every position-based lookup downstream.
    # Explicit sort_index() is required and load-bearing, not cosmetic.
    combined = pd.concat(rebased, axis=1).sort_index()
    series = combined.mean(axis=1, skipna=True).dropna()
    assert series.index.is_monotonic_increasing, (
        f"{sector}: basket series index is not sorted after sort_index() — "
        "investigate before trusting any horizon calculation."
    )
    return series, members_used, members_total


def get_benchmark_series() -> pd.Series:
    """Nifty 50 close series (raw levels — not rebased, used only for its own
    pct-change horizons, which are scale-independent)."""
    closes = _get_closes([NIFTY_BENCHMARK_SYMBOL])
    series = closes.get(NIFTY_BENCHMARK_SYMBOL, pd.Series(dtype=float))
    if not series.empty:
        series = series.sort_index()
        assert series.index.is_monotonic_increasing, "Benchmark series index is not sorted"
    return series
