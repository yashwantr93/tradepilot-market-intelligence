# Corporate Actions — Validation Report (2026-07-03)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status |
| --- | --- | --- |
| NSE corporate-announcements | nse_json | OK |
| NSE corporate-actions | nse_json | OK |

## 2. Counts

- Raw announcements + actions fetched: **40**
- Tracked events classified & stored: **34**
- Untracked (filtered as noise): **11**

## 3. Event-type distribution

| Event Type | Count |
| --- | --- |
| Dividend | 21 |
| Mergers & Acquisitions | 6 |
| Stock Split | 2 |
| Preferential Allotment | 2 |
| Buyback | 1 |
| Regulatory Approval | 1 |
| Management Change | 1 |

## 4. Priority distribution

| Priority | Count |
| --- | --- |
| Low | 21 |
| High | 10 |
| Medium | 3 |

## 5. Impact distribution

| Impact | Count |
| --- | --- |
| Neutral | 26 |
| Bullish | 8 |

## 6. Notes & limitations

- Sources: NSE corporate-announcements (free-text) + corporate-actions (structured). Both expose the latest batch; history accumulates forward.
- Event type is classified by transparent keyword rules; untracked announcements (board-meeting outcomes, newspaper publications, trading-window notices) are filtered out by design.
- Impact/priority are fixed rule-based mappings per event type — no scores.
- **Independence:** built only from announcements — fully independent of the deal-flow and institutional watchlists; can be cross-referenced with them.

## 7. Verdict

Module produced **34 tracked corporate-action events** across High/Medium/Low priorities from real NSE feeds. Ready as a third independent watchlist candidate source.