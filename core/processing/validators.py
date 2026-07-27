"""
Data-quality validation for deals.

Splits a frame into (valid, rejected). Rejected rows are written to the
dead_letter table by the caller. Rules implement the Phase 1 spec §G.
"""

from __future__ import annotations

import pandas as pd


def validate_deals(df: pd.DataFrame, symbol_map: dict[str, dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Return (valid_df, rejected_rows_with_reason)."""
    if df.empty:
        return df, []

    rejected: list[dict] = []
    keep_mask = []
    known_symbols = set(symbol_map.keys())

    for _, r in df.iterrows():
        reason = None
        if r["txn_type"] not in ("BUY", "SELL"):
            reason = f"invalid txn_type '{r['txn_type']}'"
        elif float(r["quantity"]) <= 0:
            reason = "quantity <= 0"
        elif float(r["price"]) <= 0:
            reason = "price <= 0"
        elif r["symbol"] not in known_symbols:
            reason = f"unknown symbol '{r['symbol']}'"
        keep_mask.append(reason is None)
        if reason is not None:
            row = r.to_dict()
            row["_reason"] = reason
            rejected.append(row)

    valid = df[pd.Series(keep_mask, index=df.index)].copy()
    return valid, rejected
