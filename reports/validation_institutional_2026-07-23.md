# FII/DII + Sector Rotation — Validation Report (2026-07-23)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | OK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 10 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **24**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Neutral | 6 |
| Strong | 3 |
| Improving | 2 |
| Weak | 1 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | -2.68 | -2.05 | N | Y | Neutral | index |
| Financial Services | 1.21 | 1.84 | Y | Y | Improving | index |
| IT | 3.51 | 4.14 | Y | Y | Strong | index |
| Auto | 1.32 | 1.95 | Y | Y | Improving | index |
| Pharma | 2.54 | 3.17 | Y | Y | Strong | index |
| FMCG | -1.82 | -1.19 | N | N | Neutral | index |
| Capital Goods | -1.29 | -0.65 | N | Y | Neutral | proxy |
| Defence | -3.19 | -2.56 | N | N | Neutral | basket |
| Realty | 12.01 | 12.64 | Y | Y | Strong | index |
| PSU | -2.44 | -1.81 | N | N | Neutral | index |
| Energy | -2.92 | -2.28 | N | N | Neutral | index |
| Metals | -4.41 | -3.77 | N | N | Weak | index |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **24 stocks** across **5 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.