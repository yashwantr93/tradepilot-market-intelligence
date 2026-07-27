"""
BaseConnector — common interface every source connector honours.

A connector's only job is to fetch raw data and return a normalized DataFrame
(documented columns) or raise ConnectorError. Retry/backoff and logging live
here so individual connectors stay small.
"""

from __future__ import annotations

import abc
import time

import pandas as pd

from core.utils.logging import get_logger


class ConnectorError(Exception):
    """Raised when a connector cannot return usable data."""


class BaseConnector(abc.ABC):
    name: str = "base"
    source_type: str = "abstract"

    def __init__(self, max_retries: int = 3, backoff_s: float = 1.5):
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self.log = get_logger(f"connector.{self.name}")

    @abc.abstractmethod
    def fetch(self, resource: str, **params) -> pd.DataFrame:
        """Fetch a resource and return a normalized DataFrame."""

    def _with_retries(self, fn, *args, **kwargs):
        """Run fn with exponential backoff; raise ConnectorError on exhaustion."""
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001 - connectors surface all failures
                last_err = e
                self.log.warning("%s attempt %d/%d failed: %s",
                                 self.name, attempt, self.max_retries, e)
                if attempt < self.max_retries:
                    time.sleep(self.backoff_s * attempt)
        raise ConnectorError(f"{self.name} failed after {self.max_retries} attempts: {last_err}")
