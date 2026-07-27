"""
Lightweight structured logging.

Single helper so every module logs consistently to both console and a rotating
file. No external dependency - stdlib logging only.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from core.config import LOGS_DIR

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger (console + rotating file)."""
    global _CONFIGURED
    logger = logging.getLogger(name)
    if not _CONFIGURED:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        root = logging.getLogger()
        root.setLevel(logging.INFO)

        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)

        file_handler = RotatingFileHandler(
            LOGS_DIR / "backend.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

        _CONFIGURED = True
    return logger
