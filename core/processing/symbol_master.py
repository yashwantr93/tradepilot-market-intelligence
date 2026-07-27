"""
Symbol master builder.

The symbol master is the join key for everything (deals → prices → sectors).
In OFFLINE_MODE it loads the seed universe. Later, KiteConnector's instrument
dump replaces the seed source without changing this interface.
"""

from __future__ import annotations

from core.config import BENCHMARK_SYMBOL, OFFLINE_MODE
from core.db import repository as repo
from core.utils.logging import get_logger
from seed import seed_data

log = get_logger(__name__)


def build_symbol_master_from_symbols(symbols: list[str],
                                     sectors: dict[str, str]) -> int:
    """Build symbol_master from a live deal-driven universe (no seed).

    Used by the live runner: symbols come from real deals, sectors from yfinance.
    ISIN is unknown here (deals archive omits it) so we key on the NSE symbol.
    """
    rows = []
    for i, sym in enumerate(sorted(set(symbols)), 1):
        rows.append({
            "isin": f"SYM_{sym}",  # placeholder key until a real ISIN map is added
            "nse_symbol": sym, "bse_code": None,
            "company_name": sym, "sector": sectors.get(sym, "Unknown"),
            "instrument_token": i, "is_active": True,
        })
    log.info("Symbol master (live): %d symbols from deal universe", len(rows))
    return repo.upsert_symbols(rows)


def build_symbol_master() -> int:
    """Populate/refresh symbol_master. Returns number of symbols upserted."""
    if OFFLINE_MODE:
        rows = seed_data.get_symbols()
        log.info("Symbol master: loading %d symbols from seed universe", len(rows))
    else:
        # Live path (Phase 1 follow-up): KiteConnector.fetch('instruments').
        # Until wired, fall back to the seed universe so the system still runs.
        rows = seed_data.get_symbols()
        log.warning("Live symbol source not wired yet; using seed universe")
    return repo.upsert_symbols(rows)
