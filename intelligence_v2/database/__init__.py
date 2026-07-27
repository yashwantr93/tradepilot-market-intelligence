"""
V2 database layer.

- `engine.py`        — V2's own read-write engine (market_v2.db) + init_db().
- `migrations.py`     — schema-version bookkeeping for future upgrades.
- `v1_reference.py`   — the ONLY module allowed to open V1's market.db, and it
                        opens it in OS-enforced read-only mode. No other V2
                        code may import sqlite3/SQLAlchemy against V1's file.
"""
