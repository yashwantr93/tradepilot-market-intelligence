"""
V2 logging — structurally separate from V1's logger.

V1 (`core/utils/logging.py`) writes to logs/backend.log via the root logger.
V2 uses its OWN named logger ("tradepilot.v2") with its own rotating file
handler (logs/v2_backend.log) attached directly to that logger — NOT to the
root logger — so V1 and V2 log configuration can never interfere with each
other even though both currently run in the same process space during
development/testing.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from intelligence_v2.config.settings import V2_LOG_FILE

_V2_LOGGER_NAME = "tradepilot.v2"
_configured = False


def get_v2_logger(name: str | None = None) -> logging.Logger:
    """Return a V2 logger (console + logs/v2_backend.log), configured once."""
    global _configured

    full_name = _V2_LOGGER_NAME if not name else f"{_V2_LOGGER_NAME}.{name}"
    logger = logging.getLogger(full_name)

    if not _configured:
        base = logging.getLogger(_V2_LOGGER_NAME)
        base.setLevel(logging.INFO)
        base.propagate = False  # never bubble into the root logger (keeps V1 log output untouched)

        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console = logging.StreamHandler()
        console.setFormatter(fmt)
        base.addHandler(console)

        V2_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            V2_LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        base.addHandler(file_handler)

        _configured = True

    return logger
