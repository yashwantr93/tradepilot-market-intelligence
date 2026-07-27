# Corporate Actions — Validation Report (2026-07-10)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status |
| --- | --- | --- |
| NSE corporate-announcements | nse_json | OK |
| NSE corporate-actions | nse_json | OK |

## 2. Counts

- Raw announcements + actions fetched: **40**
- Tracked events classified & stored: **74**
- Untracked (filtered as noise): **19**

## 3. Event-type distribution

| Event Type | Count |
| --- | --- |
| Dividend | 56 |
| Mergers & Acquisitions | 8 |
| Large Order Win | 2 |
| Stock Split | 2 |
| Preferential Allotment | 2 |
| Management Change | 1 |
| Bonus Issue | 1 |
| Buyback | 1 |
| Regulatory Approval | 1 |

## 4. Priority distribution

| Priority | Count |
| --- | --- |
| Low | 56 |
| High | 15 |
| Medium | 3 |

## 5. Impact distribution

| Impact | Count |
| --- | --- |
| Neutral | 61 |
| Bullish | 13 |

## 6. Notes & limitations

- Sources: NSE corporate-announcements (free-text) + corporate-actions (structured). Both expose the latest batch; history accumulates forward.
- Event type is classified by transparent keyword rules; untracked announcements (board-meeting outcomes, newspaper publications, trading-window notices) are filtered out by design.
- Impact/priority are fixed rule-based mappings per event type — no scores.
- **Independence:** built only from announcements — fully independent of the deal-flow and institutional watchlists; can be cross-referenced with them.

## 7. Verdict

Module produced **74 tracked corporate-action events** across High/Medium/Low priorities from real NSE feeds. Ready as a third independent watchlist candidate source.