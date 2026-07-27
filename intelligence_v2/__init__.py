"""
TradePilot AI — V2 Market Intelligence Platform (foundation package).

This package is entirely independent of V1 (`core/`, `data/`, `pages/`):
  * Its own database file (data_store/market_v2.db) — never opens V1's market.db
    for writing.
  * Its own config, logging, and connectors — nothing here imports `core.*`.
  * V1 data is reachable ONLY through `intelligence_v2.database.v1_reference`,
    which opens V1's database in strict, OS-enforced read-only mode.

Phase 0 (this phase) builds ONLY the foundation: package structure, the V2
database, the read-only V1 bridge, shared config, logging, schema versioning,
and health checks. No business logic, no calculations, no dashboard pages.
See docs/V2_IMPLEMENTATION_PLAN.md for the full phase sequence.
"""
