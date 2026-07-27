# FII/DII + Sector Rotation — Validation Report (2026-07-21)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | FALLBACK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 10 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **0**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Neutral | 12 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | None | None | None | None | Neutral | none |
| Financial Services | None | None | None | None | Neutral | none |
| IT | None | None | None | None | Neutral | none |
| Auto | None | None | None | None | Neutral | none |
| Pharma | None | None | None | None | Neutral | none |
| FMCG | None | None | None | None | Neutral | none |
| Capital Goods | None | None | None | None | Neutral | none |
| Defence | None | None | None | None | Neutral | none |
| Realty | None | None | None | None | Neutral | none |
| PSU | None | None | None | None | Neutral | none |
| Energy | None | None | None | None | Neutral | none |
| Metals | None | None | None | None | Neutral | none |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **0 stocks** across **0 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.