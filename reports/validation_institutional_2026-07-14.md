# FII/DII + Sector Rotation — Validation Report (2026-07-14)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | OK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 9 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **29**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Neutral | 6 |
| Improving | 4 |
| Strong | 2 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | 0.46 | -0.37 | N | Y | Neutral | index |
| Financial Services | 2.29 | 1.46 | N | Y | Improving | index |
| IT | 2.34 | 1.51 | Y | Y | Improving | index |
| Auto | 0.96 | 0.13 | N | Y | Improving | index |
| Pharma | 6.97 | 6.13 | Y | Y | Strong | index |
| FMCG | -0.62 | -1.45 | N | N | Neutral | index |
| Capital Goods | 1.23 | 0.4 | N | N | Improving | proxy |
| Defence | 0.24 | -0.6 | N | N | Neutral | basket |
| Realty | 19.37 | 18.54 | Y | Y | Strong | index |
| PSU | 0.26 | -0.57 | N | N | Neutral | index |
| Energy | -0.11 | -0.94 | N | N | Neutral | index |
| Metals | -1.38 | -2.21 | N | N | Neutral | index |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **29 stocks** across **6 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.