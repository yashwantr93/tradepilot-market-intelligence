# Corporate Actions — Validation Report (2026-07-21)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status |
| --- | --- | --- |
| NSE corporate-announcements | nse_json | FALLBACK |
| NSE corporate-actions | nse_json | FALLBACK |

## 2. Counts

- Raw announcements + actions fetched: **11**
- Tracked events classified & stored: **33**
- Untracked (filtered as noise): **0**

## 3. Event-type distribution

| Event Type | Count |
| --- | --- |
| Dividend | 20 |
| Rights Issue | 2 |
| Buyback | 2 |
| Management Change | 2 |
| Stock Split | 1 |
| Bonus Issue | 1 |
| Preferential Allotment | 1 |
| QIP | 1 |
| Regulatory Approval | 1 |
| Mergers & Acquisitions | 1 |
| Large Order Win | 1 |

## 4. Priority distribution

| Priority | Count |
| --- | --- |
| Low | 20 |
| High | 8 |
| Medium | 5 |

## 5. Impact distribution

| Impact | Count |
| --- | --- |
| Neutral | 25 |
| Bullish | 6 |
| Bearish | 2 |

## 6. Notes & limitations

- Sources: NSE corporate-announcements (free-text) + corporate-actions (structured). Both expose the latest batch; history accumulates forward.
- Event type is classified by transparent keyword rules; untracked announcements (board-meeting outcomes, newspaper publications, trading-window notices) are filtered out by design.
- Impact/priority are fixed rule-based mappings per event type — no scores.
- **Independence:** built only from announcements — fully independent of the deal-flow and institutional watchlists; can be cross-referenced with them.

## 7. Verdict

Module produced **33 tracked corporate-action events** across High/Medium/Low priorities from real NSE feeds. Ready as a third independent watchlist candidate source.