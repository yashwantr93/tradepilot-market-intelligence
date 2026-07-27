"""
V2 shared configuration — the single place every V2 constant lives.

Deliberately does NOT import from `core.config` (V1). Where a V1 constant is
conceptually reused (e.g. the sector universe), it is a duplicated, frozen
copy here — per the isolation principle in docs/V2_ADVANCED_INTELLIGENCE_ROADMAP.md §0.3.

Phase 0 only defines foundation-level settings (paths, app identity, schema
version, health-check thresholds). Module-specific thresholds (sector-state
rules, cycle dwell times, etc.) are added when each module is implemented.
"""

from intelligence_v2.config.settings import *  # noqa: F401,F403
from intelligence_v2.config.sectors import *  # noqa: F401,F403
