# FII/DII + Sector Rotation — Validation Report (2026-07-07)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | OK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 6 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **34**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Improving | 6 |
| Weak | 3 |
| Neutral | 2 |
| Strong | 1 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | 5.12 | 0.68 | Y | Y | Improving | index |
| Financial Services | 7.28 | 2.84 | Y | Y | Improving | index |
| IT | -2.56 | -6.99 | Y | N | Improving | index |
| Auto | 3.75 | -0.68 | Y | Y | Improving | index |
| Pharma | 6.17 | 1.73 | Y | Y | Improving | index |
| FMCG | 2.54 | -1.9 | Y | N | Neutral | index |
| Capital Goods | 2.36 | -2.07 | Y | Y | Neutral | proxy |
| Defence | 5.85 | 1.42 | Y | N | Improving | basket |
| Realty | 17.02 | 12.59 | Y | Y | Strong | index |
| PSU | -1.88 | -6.31 | N | N | Weak | index |
| Energy | -3.27 | -7.7 | N | N | Weak | index |
| Metals | -4.38 | -8.82 | N | N | Weak | index |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **34 stocks** across **7 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.