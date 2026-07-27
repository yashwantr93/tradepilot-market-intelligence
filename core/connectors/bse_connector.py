"""
BSEConnector — cross-source bulk/block deals.

Stub for Phase 1: honours the connector interface and returns an empty frame in
OFFLINE_MODE (NSE is the primary deal source). The live BSE deal API can be
wired here later to corroborate / supplement NSE without touching the pipeline.

Resources: 'bulk_deals', 'block_deals'.
"""

from __future__ import annotations

import pandas as pd

from core.connectors.base import BaseConnector, ConnectorError

_COLUMNS = ["trade_date", "exchange", "symbol", "client_name",
            "txn_type", "quantity", "price"]


class BSEConnector(BaseConnector):
    name = "bse"
    source_type = "csv"

    def fetch(self, resource: str, **params) -> pd.DataFrame:
        if resource not in ("bulk_deals", "block_deals"):
            raise ConnectorError(f"BSEConnector: unknown resource '{resource}'")
        # Phase 1: BSE not yet wired; return empty so the union with NSE is a no-op.
        self.log.info("BSEConnector stub: returning empty %s (NSE is primary)", resource)
        return pd.DataFrame(columns=_COLUMNS)
