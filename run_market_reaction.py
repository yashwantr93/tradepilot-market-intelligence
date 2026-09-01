"""
Market Reaction runner — Phase 3 (event_intelligence/).

Measures event-relative price/volume behavior for every stored corporate
action, using already-collected `price_history` (no new data source, no
network call of its own). Run AFTER `run_corp_actions.py` and `run_live.py`
(or `run_daily.py`, which already sequences V1 before V2) so both the event
data and the price data it measures against are current.

Deliberately a standalone top-level script rather than something V1's
corp_actions_pipeline calls directly — see event_intelligence/__init__.py
and core/pipelines/corp_actions_pipeline.py's note on why: this is the one
place allowed to import both `core.db` (V1) and `intelligence_v2.processors`
(V2), and keeping that bridging at the top level (not inside core/ or
intelligence_v2/ themselves) is what keeps CLAUDE.md's V1/V2 isolation rule
intact.

NO scoring · NO ML · NO prediction · reuses V2's existing calendar-aligned
RS primitives rather than re-deriving date logic.

Usage:  python run_market_reaction.py
"""

from __future__ import annotations

from core.db.engine import init_db
from core.utils.logging import get_logger
from event_intelligence.pipeline import run_market_reaction

log = get_logger("run_market_reaction")


def main() -> None:
    log.info("=== Market Reaction run ===")
    init_db()

    report = run_market_reaction(action_ids=None)

    print("\n".join([
        "",
        f"Corporate actions processed : {report['processed']}",
        f"Reaction rows stored        : {report['stored']}",
        f"Coverage (any 1d/5d/10d/20d): {report['coverage']['1d_pct']}% / "
        f"{report['coverage']['5d_pct']}% / {report['coverage']['10d_pct']}% / "
        f"{report['coverage']['20d_pct']}%",
        f"Reaction states              : {report['by_state']}",
    ]))


if __name__ == "__main__":
    main()
