# V2 Implementation Plan (One Page)
### Execution sequence only — no production code in this document.

## Document Review — Consistency Check
Reviewed: `V2_PRODUCT_REQUIREMENTS.md`, `V2_ADVANCED_INTELLIGENCE_ROADMAP.md`, `BRAND_GUIDELINES.md`.

**1 inconsistency found → resolved:** Roadmap §7.3 lists Early Momentum as its own dashboard page; PRD §4.4/§5 folds it into **Swing Opportunities** as a feeder sub-section. **Resolution: PRD wins** — no standalone Early Momentum page.

**3 previously-open Roadmap decisions (§8) → resolved by the PRD, carried forward here:**
| Roadmap open decision | Resolved by PRD as |
|---|---|
| Separate `app_v2.py` vs. one touch to `app.py`'s `PAGES` dict | **Unified single app** — PRD §5 is one nav tree |
| Sector Intelligence / Market Cycle: one page or two | **Merged** — Market Cycle is a tab inside Sector Intelligence |
| Position Engine: delay until fundamentals connector exists, or ship with fallback | **Ship now** with "Not Available" fallback (§4.5) |

No other contradictions found. All three docs agree on: V1 physical isolation (`market_v2.db` + `intelligence_v2/`), no scoring/ML anywhere, and the module list/order.

---

## Phased Execution

| # | Phase / Module | Deliverable | Effort | Depends on | Top Risk |
|---|---|---|---|---|---|
| 0 | **Foundation** | `intelligence_v2/` skeleton, `market_v2.db`, `v1_reference.py` (read-only bridge), `config.py` | 1–2d | — | Low — mechanical, mirrors proven V1 patterns |
| 1 | **Sector Intelligence** (Roadmap M1) | Multi-horizon calc, 7-state classifier, append-only table, page | 3–4d | Phase 0 | **Medium** — hysteresis logic; every later module leans on this being right |
| 2 | **Market Cycle** (M2) | 7-stage state machine, tab inside Sector Intelligence page | 2–3d | Phase 1 validated | Low-Medium — same state-machine risk, smaller surface |
| 3 | **Early Momentum** (M3) | New Nifty-500 connector, feeder list inside Swing Opportunities | 3–4d | Phase 0 | **Medium** — first new external connector; confirm URL live before coding |
| 4 | **Bearish Engine** (M5) | New F&O-list connector, Priority Short A/B/Watchlist/Avoid Shorts | 3–4d | Phase 1 + new connector | Medium — new connector; short-side logic needs extra review given trading-risk framing |
| 5 | **Position Engine** (M4) — last, per Roadmap's own recommendation | Weekly/monthly calc, fundamentals join (fallback-safe), new tiering, new page | 4–5d | Phase 1 + V1 `results_tracker` (read-only) | **Medium-High** — only module with an acknowledged real data gap (promoter/debt/ROCE) |
| 6 | **Validation_v2** | Capture hooks added *per module as it ships* (1,2,4,5); full cross-engine report after Phase 5 | 2–3d (incremental) | Each module's output table existing | Low — mirrors V1's already-proven capture→evaluate→report pattern |
| 7 | **Historical Replay** | Date-picker reconstruction over existing dated tables | 2d | Phases 1–2 minimum (more modules = more depth, not a blocker) | Low — no new source, no new rule engine (lowest-risk feature) |
| 8 | **Portfolio Insights** | Manual holdings table + read-only joins | 2–3d | Any live modules (can ship minimal, expand later) | Low — **guardrail check required**: manual/CSV entry only, never a broker API, before merge |
| 9 | **UX/Theme + Nav unification** | Real light/dark CSS rework, all pages wired into one `PAGES` dict, Reports/Settings(view-only)/About | 3–4d | All prior phases substantially done | Low — presentation-only, same pass V1 already went through |

**Total estimate: ~28–35 developer-days.** Planning estimate, not a deadline commitment.

---

## Testing Strategy
- **Every new connector** (Nifty-500 list, F&O list): live-probe and confirm schema *before* writing pipeline code against it — same discipline used for every V1 connector.
- **Every state machine** (7-state sector, 7-stage cycle): unit-test threshold/hysteresis functions against synthetic input series first — this is the highest-risk correctness surface in the whole plan.
- **Every module**: one real-data dry run + manual spot-check before considering the phase done.
- **After every phase**: re-run V1's existing pipelines + dashboard once, confirm zero behavior change (cheap regression guard against accidental coupling).

## Rollback Strategy
- Physical isolation (`market_v2.db` + `intelligence_v2/`) means **any V2 module can be deleted wholesale with zero impact on V1** — this is the core safety property the Roadmap was designed around.
- One phase = one commit/checkpoint; a broken phase reverts independently of completed ones.
- The single shared touchpoint (`app.py`'s `PAGES` dict) makes removing one V2 page a one-line edit, not surgery.
- Worst case for V2 itself: delete `data_store/market_v2.db` and re-run its pipelines — V1's `market.db` is never reachable for writes, so it is never at risk.

---
**Status: awaiting approval.** Implementation begins module-by-module, starting at Phase 0, on sign-off.
