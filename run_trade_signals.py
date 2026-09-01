"""
Trade Signal runner — Phase 5 (event_intelligence/).

Produces explainable LONG / SHORT / NO_TRADE decision-support signals for
every stored corporate action, from already-computed materiality (Phase 2),
market reaction (Phase 3), and V2 technical confirmation. Run AFTER
`run_market_reaction.py` (which itself should run after `run_corp_actions.py`
and `run_live.py`/`run_daily.py`) so the evidence it reads is current.

These are decision-support signals, not automatic trading instructions —
every signal_strength is explicitly HEURISTIC and every signal carries
predictive_status="EXPLORATORY" (Phase 4 found no evidence dimension here
empirically predicts forward returns yet on the current sample size).

Usage:  python run_trade_signals.py
"""

from __future__ import annotations

from core.db.engine import init_db
from core.utils.logging import get_logger
from event_intelligence.signal_pipeline import run_trade_signals

log = get_logger("run_trade_signals")


def main() -> None:
    log.info("=== Trade Signal run ===")
    init_db()

    report = run_trade_signals(action_ids=None)

    print("\n".join([
        "",
        f"Events processed   : {report['processed']}",
        f"Signals stored     : {report['stored']}",
        f"By direction       : {report['by_direction']}",
        f"By strength        : {report['by_strength']}",
        "",
        "NOTE: signal_strength is HEURISTIC and predictive_status is EXPLORATORY",
        "for every signal — see docs/PRODUCT_VISION.md and the Phase 4/5 reports.",
    ]))


if __name__ == "__main__":
    main()
