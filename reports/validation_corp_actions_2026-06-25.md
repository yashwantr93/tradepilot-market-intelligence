# Corporate Actions — Validation Report (2026-06-25)

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status |
| --- | --- | --- |
| NSE corporate-announcements | nse_json | OK |
| NSE corporate-actions | nse_json | OK |

## 2. Counts

- Raw announcements + actions fetched: **40**
- Tracked events classified & stored: **25**
- Untracked (filtered as noise): **15**

## 3. Event-type distribution

| Event Type | Count |
| --- | --- |
| Dividend | 17 |
| Bonus Issue | 2 |
| Large Order Win | 2 |
| Buyback | 1 |
| Preferential Allotment | 1 |
| Mergers & Acquisitions | 1 |
| Management Change | 1 |

## 4. Priority distribution

| Priority | Count |
| --- | --- |
| Low | 17 |
| High | 7 |
| Medium | 1 |

## 5. Impact distribution

| Impact | Count |
| --- | --- |
| Neutral | 19 |
| Bullish | 6 |

## 6. Notes & limitations

- Sources: NSE corporate-announcements (free-text) + corporate-actions (structured). Both expose the latest batch; history accumulates forward.
- Event type is classified by transparent keyword rules; untracked announcements (board-meeting outcomes, newspaper publications, trading-window notices) are filtered out by design.
- Impact/priority are fixed rule-based mappings per event type — no scores.
- **Independence:** built only from announcements — fully independent of the deal-flow and institutional watchlists; can be cross-referenced with them.

## 7. Verdict

Module produced **25 tracked corporate-action events** across High/Medium/Low priorities from real NSE feeds. Ready as a third independent watchlist candidate source.