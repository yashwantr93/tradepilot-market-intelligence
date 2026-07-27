"""Transform helpers: normalization, ISIN mapping, dedupe hashing."""

from __future__ import annotations

import hashlib

import pandas as pd


def build_dedupe_hash(row: pd.Series) -> str:
    """Stable hash of a deal's natural key — prevents double-counting."""
    key = "|".join(str(row[c]) for c in [
        "exchange", "trade_date", "symbol", "client_name",
        "txn_type", "quantity", "price",
    ])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def enrich_deals(df: pd.DataFrame, symbol_map: dict[str, dict]) -> pd.DataFrame:
    """Add value, isin and dedupe_hash; normalize txn_type/symbol casing."""
    if df.empty:
        return df
    out = df.copy()
    out["symbol"] = out["symbol"].astype(str).str.strip().str.upper()
    out["txn_type"] = out["txn_type"].astype(str).str.strip().str.upper()
    out["value"] = out["quantity"].astype(float) * out["price"].astype(float)
    out["isin"] = out["symbol"].map(lambda s: symbol_map.get(s, {}).get("isin"))
    out["dedupe_hash"] = out.apply(build_dedupe_hash, axis=1)
    return out
