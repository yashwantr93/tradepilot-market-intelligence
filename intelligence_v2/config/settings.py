"""
V2 foundation settings — paths, identity, schema version, health-check config.

Everything here is self-contained: no imports from `core.*` (V1). Brand
identity strings are a deliberate duplicate of `core/branding.py`'s values,
not an import, to keep V2 fully decoupled per the isolation principle.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
V2_PACKAGE_ROOT = Path(__file__).resolve().parent.parent

# Same MID_DATA_DIR / MID_LOGS_DIR env vars core/config.py (V1) respects, so
# one setting relocates both market.db and market_v2.db together — e.g. to a
# Render persistent disk. Unset, defaults are unchanged from before.
DATA_STORE_DIR = Path(os.environ.get("MID_DATA_DIR", str(PROJECT_ROOT / "data_store")))
LOGS_DIR = Path(os.environ.get("MID_LOGS_DIR", str(PROJECT_ROOT / "logs")))

# V1's database — referenced ONLY by intelligence_v2.database.v1_reference,
# and ONLY ever opened read-only. V2 never creates or writes this file.
V1_DB_PATH = DATA_STORE_DIR / "market.db"

# V2's own, physically separate database.
V2_DB_PATH = DATA_STORE_DIR / "market_v2.db"

# V2's own log file — never interleaved with V1's logs/backend.log.
V2_LOG_FILE = LOGS_DIR / "v2_backend.log"

# Folders that must exist for the platform to be considered healthy.
# (Sub-packages are expected to exist as part of the checked-in package tree;
# this list is the *runtime* directories that can be missing on a fresh clone.)
REQUIRED_DIRS: list[Path] = [
    DATA_STORE_DIR,
    LOGS_DIR,
    V2_PACKAGE_ROOT / "config",
    V2_PACKAGE_ROOT / "contracts",
    V2_PACKAGE_ROOT / "connectors",
    V2_PACKAGE_ROOT / "database",
    V2_PACKAGE_ROOT / "models",
    V2_PACKAGE_ROOT / "processors",
    V2_PACKAGE_ROOT / "services",
    V2_PACKAGE_ROOT / "pages",
    V2_PACKAGE_ROOT / "tests",
    V2_PACKAGE_ROOT / "utils",
]

# ---------------------------------------------------------------------------
# Identity (duplicated from core/branding.py — not imported; see module docstring)
# ---------------------------------------------------------------------------
APP_NAME = "TradePilot AI"
APP_SUBTITLE = "Market Intelligence Platform"
APP_FULL_NAME = f"{APP_NAME} — {APP_SUBTITLE}"
V2_COMPONENT_NAME = "V2 Foundation"

# ---------------------------------------------------------------------------
# Schema versioning (see intelligence_v2/database/migrations.py)
# ---------------------------------------------------------------------------
CURRENT_SCHEMA_VERSION = 6

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
# A harmless, always-available V1 table used to prove the read-only bridge can
# actually read real V1 data (not just open the file).
V1_HEALTH_CHECK_TABLE = "symbol_master"
