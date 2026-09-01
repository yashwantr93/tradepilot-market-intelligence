# TradePilot — Product Vision (North Star)

**Status**: Living document. Establishes product intent so future architecture, data,
and UI decisions stay aligned with the trading objective — not a spec for any single
feature. Read this before starting new implementation work; flag conflicts rather than
silently resolving them (see "Claude's Role" below).

---

## 1. What TradePilot Is

**An Event-Driven Swing & Position Trading Intelligence System** for NSE/BSE equities.

It identifies situations where a material company- or sector/theme-level event may cause
a meaningful repricing, and helps the trader judge whether the developing move is a
LONG or SHORT swing candidate — and, if momentum and thesis persist, whether that swing
can become a position trade.

**The core question**: *What materially changed, why does it matter, how is the market
reacting, and is there a tradeable move developing?*

**The unique question that differentiates it from every other tool the user already
owns (a Chartink-style scanner, an F&O scanner, a crypto dashboard)**: ***WHY NOW?***

### The target intelligence chain

```
EVENT → IMPACT → EXPECTATION → ACTUAL → SURPRISE → MATERIALITY
      → MARKET REACTION → PRICE/VOLUME CONFIRMATION → TRADE THESIS
      → LONG / SHORT / NO TRADE → SWING → POSSIBLE POSITION
```

Not all of this chain is built yet — see §7 (Current State) for exactly what exists.

---

## 2. Two Primary Discovery Paths

**Path A — Company Event.** A company receives a material event (result, order,
guidance change, regulatory action, promoter/institutional activity, corporate action,
M&A, capacity change, credit event, product approval/failure, governance event, etc.).
The system asks: what happened → is it material → direction → what was expected → what
happened → surprise → business/risk implication → price reaction → volume confirmation →
is it sustaining → LONG/SHORT opportunity?

**Path B — Sector/Theme Discovery.** Identify where a larger move may be *developing*,
not merely confirm one that's already obvious. Target lifecycle: `EARLY/EMERGING →
DEVELOPING → EARLY MOMENTUM → CONFIRMED → MATURE/CROWDED → WEAKENING → FADING`. The
question: *where could the next meaningful theme be developing?* — via catalyst
concentration, breadth, leaders vs. emerging leaders, and price/volume confirmation.

Both paths converge on the same downstream evaluation (Fundamental Context → Materiality
→ Reaction → Technical Confirmation → Trade Thesis) once a specific stock is reached —
this must remain **one shared evaluation sequence**, never two parallel engines.

---

## 3. Non-Negotiable Product Principles

1. **Fundamental quality is context, never a hard gate.** A fundamentally strong company
   can become a SHORT after a severe negative surprise. A fundamentally mediocre company
   can produce a legitimate LONG swing on a powerful catalyst. Never hard-code "strong
   fundamentals → BUY" or "weak fundamentals → reject."
2. **Direction ≠ Surprise ≠ Materiality.** These are separate, always-preserved values.
   `Expected +30% / Actual +15%` is headline-positive but a **negative surprise**.
   Headline sentiment must never become the trade thesis by itself.
3. **Event ≠ Trade.** The event creates the thesis; market reaction (price/volume)
   validates or rejects it. An event without confirming reaction is not yet a trade.
4. **Long and Short are symmetric, first-class citizens.** Every layer from Direction
   onward must work equally well for either sign — no layer may assume positive-only
   input.
5. **Technical analysis confirms; it does not originate the thesis.** The existing V2
   technical/RS engines answer "is the market confirming the event-driven thesis?" —
   never "here is an opportunity" on their own.
6. **UNKNOWN is a correct, expected answer** — for direction, expectation, materiality,
   or reaction — whenever evidence is insufficient. Never fabricate to fill a gap.
   "Insufficient evidence" beats "confident but unsupported conclusion."
7. **Explainable over opaque.** Every classification carries a human-readable reason.
   No 0–100 black-box score anywhere.
8. **Swing is the primary horizon; Position is an earned progression**, not a separate
   screener — driven by momentum/thesis persistence across repeated evaluations, not a
   one-day alert.

---

## 4. Role of AI

AI may eventually help with: event classification, impact interpretation, materiality
explanation, expectation/surprise interpretation, sector/theme synthesis, cross-event
reasoning, and trade-thesis narration.

AI must **never** invent expectations, financial facts, materiality, catalysts, sources,
or trading certainty. Every AI-assisted layer must be able to say "insufficient evidence"
rather than guess. (No AI/LLM component exists in the codebase today — see §7.)

---

## 5. What a Trader Should Eventually See

**Market** (developing events/themes) → **Events** (what matters today) → **Impact**
(why) → **Expectation** (what was expected) → **Surprise** (what actually changed) →
**Reaction** (how price is responding) → **Sector/Theme** (where momentum is
developing) → **Stock** (best-positioned names) → **Direction** (Long/Short/No Trade)
→ **Horizon** (Swing/developing Position) → **Risk** (what invalidates the thesis).

The product should reduce information overload, not add another feed to check.

---

## 6. What TradePilot Is NOT

Not a generic news aggregator · not a complete fundamental screener · not a Chartink
replacement · not an F&O scanner · not a pure technical-analysis dashboard · not a
buy/sell prediction machine · not an automated trading system · not a black-box AI
stock picker.

If a proposed feature would duplicate an existing scanner's primary function without
materially improving *event-driven* decision-making, it should be flagged, not built.

---

## 7. Current State (as of Phase 2.5)

Reflects what has actually been inspected, built, and verified — not aspiration.

### Built and production-wired
- **Event classification** (`core/config.py::EVENT_TYPE_RULES`, `core/processing/event_classifier.py`):
  23 corporate-action event types across 12 target categories, with genuine
  positive/negative/**Ambiguous** direction (M&A and generic Management Change are
  explicitly Ambiguous, not forced Bullish/Neutral). Two real misclassification bugs
  found and fixed via full-dataset re-audit (Phase 1/1.5).
- **Event identity & provenance**: dedup identity no longer depends on classification
  (Phase 1.5) — a corrected classification updates the same row instead of duplicating
  it. `original_event_type`/`reclassification_reason` provenance columns preserve what
  changed and why.
- **Results retention**: all fetched quarters are now stored (`results_quarterly`),
  not just the latest comparison — previously silently discarded.
- **Expectation/Surprise** (`core/processing/expectation.py`): internal trailing-average
  baseline (never analyst consensus — that source is explicitly reserved, unused), with
  confidence capped at MEDIUM and UNKNOWN below one prior sample. Correctly returns
  UNKNOWN for essentially all symbols today — **not a bug**: real quarterly cadence
  means no symbol yet has 2+ trustworthy YoY prints (see Phase 2.5 finding below).
- **Materiality**: results-surprise tiers (Phase 1) plus two corporate-action categories
  wired end-to-end (Phase 2) — Dividend (yield vs. price, 98.5% magnitude-extractable)
  and Large Order Win (value vs. trailing revenue, ~35% extractable, denominator
  coverage the current bottleneck). Thresholds are evidence-calibrated where real
  distributions exist, explicitly flagged as a starting point where they aren't.
- **Data integrity discipline**: two dedicated audit-and-remediation phases (1.5, 2.5)
  found and fixed a duplicate-identity bug and a silent offline/live provenance gap that
  had contaminated `results_tracker` for months — both root-caused against real data,
  backed up before mutation, and fully tested.
- **Technical/RS confirmation infrastructure (V2)**: 5 phases (Sector Intelligence,
  Market Cycle, Early Momentum, Bearish Opportunities, Position Opportunities), all
  working, all currently exposed as primary navigation pages rather than confirmation
  services — see Gaps.
- **V1/V2 physical isolation**: hard, OS-enforced read-only boundary — real architectural
  strength, unrelated to product direction but worth preserving as-is.

### Audited, designed, but NOT yet built
Market Reaction (gap/breakout/volume-relative-to-event), Sector/Theme emergence
detection (catalyst-density/breadth-based leading indicators), final Opportunity
Classification/Trade Thesis object, Swing→Position transition logic, negative-vocabulary
parity for non-results categories beyond corporate actions, promoter/pledge tracking,
any AI-assisted interpretation layer.

---

## 8. Gaps (current system vs. this vision)

- **Opportunity ranking still gates on technical confirmation, not materiality.**
  `data/contracts.py::opportunity_hub()`'s Priority-A tier hard-requires
  `above_sma AND strong_rs AND near_breakout` — the exact inversion this vision
  requires (materiality gates, technicals confirm/rank). Not yet inverted.
- **No Market Reaction layer exists.** Nothing anchors price/volume behavior to an
  event date; the only reaction-adjacent signal is a generic, unanchored
  `volume_expansion` flag in `core/processing/technicals.py`.
- **No sector/theme emergence detection.** The existing 7-state Sector Intelligence
  classifier (V2 Phase 1) is confirmed, by direct code audit, to be a lagging/current-
  strength read (`Early Momentum` requires RS to already be strongly positive) — it does
  not detect a theme before broad price confirmation.
- **Corporate-action universe coverage is structurally narrow.** Only ~19% of
  corporate-action symbols overlap `price_history`'s curated ~450-name universe,
  capping any future Market Reaction layer's coverage until a deliberate universe-
  expansion decision is made.
- **Real expectation/surprise output doesn't exist yet** — not because the mechanism is
  wrong (verified correct via unit tests and the task's own worked examples), but
  because no symbol has accumulated 2 trustworthy YoY quarters yet. This will resolve
  naturally as real quarterly cycles pass, provided the Phase 2.5 provenance fix stays
  in place.
- **Negative-event vocabulary exists for corporate actions but not elsewhere** — no
  government/RBI/policy feed, no promoter-pledge source, no credit-rating feed beyond
  keyword matching on whatever text NSE announcements happen to carry.

---

## 9. Conflicts / Risks to Watch

- **The 5 V2 technical engines are still primary sidebar pages.** Nothing about their
  *calculation logic* conflicts with this vision (they should remain unchanged), but
  their *navigational role* does — presenting them as standalone "Opportunities" pages
  invites the product to be read as a technical scanner, which §6 explicitly disclaims.
  Any UI work should demote them to confirmation/backend status, not redesign their math.
- **`opportunity_hub()`'s technical gate is load-bearing today** — inverting it (per §8)
  is a real, visible behavior change to existing rankings, not a cosmetic one. Should be
  done deliberately, with before/after comparison, not silently.
- **Materiality thresholds for Large Order Win are unvalidated** (n=1 real case) — don't
  let a single computed TRANSFORMATIONAL tier be read as a validated signal.
- **`results_tracker`'s thin real history is a hard timing constraint**, not a solvable
  engineering problem — resist the temptation to lower `min_samples_for_expectation` or
  weaken the confidence cap just to produce visible output sooner (Phase 2's explicit
  instruction, still binding).

---

## 10. Recommendations

Ordered by priority; each evaluated for value, complexity, and risk.

1. **Invert `opportunity_hub()`'s gate (materiality gates, technical confirms).**
   *Why*: this is the single architectural change that actually makes the product
   event-driven rather than technical-driven in its highest-visibility output.
   *Value*: high — directly changes what a trader sees first. *Complexity*: medium
   (touches live ranking logic, needs before/after validation). *Priority*: **P0**,
   but sequence after Market Reaction exists (§10.2) so the new gate has real inputs
   to gate on, not just materiality alone.
2. **Build the Market Reaction layer**, reusing `shared_relative_strength.py`'s
   already-built, calendar-aware primitives (`performance_between_dates`,
   `position_at_or_before`) anchored to event dates, scoped to the ~19%-overlap
   subset (Option C from the earlier architecture freeze: classify the full catalyst
   universe, compute reaction only where price data exists, UNKNOWN elsewhere).
   *Why*: without it, "Event ≠ Trade" (§3.3) has no mechanism. *Value*: high — the
   missing link in the core chain. *Complexity*: medium, no new data source needed.
   *Priority*: **P0**.
3. **Sector/theme emergence via catalyst density + breadth**, built symmetrically for
   emerging (long) and weakening (short) from the start, reusing the now-working
   corporate-action classification. *Why*: Path B is currently unimplementable — the
   existing Sector Intelligence engine cannot do this by design (confirmed by audit).
   *Value*: high, but slower to bear fruit than P0 items since catalyst density needs
   time to accumulate. *Complexity*: medium. *Priority*: **P1**.
4. **Wire ratio-based materiality into 1–2 more corporate-action categories** (Buyback,
   Bonus Issue — both have a clean value/market-cap ratio and decent magnitude clarity)
   before attempting harder categories. *Why*: incremental, reuses the exact pattern
   already proven for Dividend. *Value*: medium. *Complexity*: low. *Priority*: **P1**.
5. **Do not build a promoter-identity or FX-conversion feature yet.** Both were
   investigated (Phase 1/2) and found to require a new data source or an invented
   exchange rate — flagging per this document's own "flag, don't silently implement"
   rule rather than recommending a workaround. *Priority*: **P3 / hold** pending a
   deliberate source decision.
6. **When UI work begins, demote (not redesign) the 5 V2 pages** to a supporting/
   confirmation section per the risk in §9, and introduce a single Event-led primary
   view — but this is UI scope, explicitly out of bounds for this document.

---

## 11. Engineering Principles (binding for future work)

`INSPECT → UNDERSTAND → DIAGNOSE → DECIDE → IMPLEMENT → VERIFY`. Preserve working
functionality unless there's a strong reason to change it. Avoid unnecessary rewrites
and duplicate systems. Prefer explainable intelligence over opaque scores, evidence
over assumption, and UNKNOWN over fabrication. Optimize for signal *quality and
decision usefulness*, not signal quantity.

**If a later implementation reveals this vision's assumption was technically or
empirically wrong, report the discovery and the trade-off — do not silently adapt the
product direction.** The product owner decides whether the North Star changes.
