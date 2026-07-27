"""
V2 ORM models — SQLAlchemy declarative Base shared by every V2 table.

Phase 0 defines only foundation-level infrastructure: the shared `Base` class
and a `SchemaVersion` bookkeeping table (see `intelligence_v2.models.base`).
Every future module (Sector Intelligence, Market Cycle, etc.) adds its own
table(s) as a new file in this package, subclassing the same `Base` — this is
what lets `intelligence_v2.database.engine.init_db()` create every V2 table
in one place without any table depending on business logic that doesn't
exist yet.
"""

from intelligence_v2.models.base import Base, SchemaVersion  # noqa: F401
from intelligence_v2.models.market_cycle import (  # noqa: F401
    MarketCycleDaily,
    MarketCycleTransition,
)
from intelligence_v2.models.sector_intelligence import SectorIntelligenceDaily  # noqa: F401
