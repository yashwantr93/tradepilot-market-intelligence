"""
event_intelligence — Phase 3, Market Reaction (and future cross-cutting
event-driven layers).

A NEW, THIRD top-level package, sibling to `core/` (V1) and `intelligence_v2/`
(V2) — deliberately not placed inside either.

Why this package exists, precisely: `CLAUDE.md`'s V1/V2 isolation rule is
explicit and load-bearing — "Nothing in intelligence_v2/ imports from
core.*, and nothing in core/ imports from intelligence_v2/." Market Reaction
genuinely needs BOTH sides — V1's event data (`core.db.repository`:
corporate_actions, price_history) AND V2's calendar-aligned RS primitives
(`intelligence_v2.processors.shared_relative_strength` — reusing
`position_at_or_before`/`position_at_or_after`/`performance_between_dates`
rather than re-deriving date-alignment logic a third time, which the
Architecture Freeze's own invariant ("no duplicated RS logic") forbids).

Importing V2 from inside `core/`, or V1 from inside `intelligence_v2/`,
would violate that rule directly. A new, bridging package that imports from
both — while `core/` and `intelligence_v2/` still never import each other —
does not. This is exactly what the earlier Architecture Freeze Proposal
anticipated for Layers 5-6 (Materiality/Market Reaction): "a new top-level
package... reads from both, imports V2's RS primitives directly rather than
duplicating them."

Storage lives in V1's `market.db` (via `core.db.repository`), alongside the
other event-intelligence tables (`corporate_action_materiality`,
`event_expectations`) — one connected set of derived event tables, not a
third database. `core/` itself still never imports this package or
`intelligence_v2/`; only `event_intelligence/` reaches into both.
"""
