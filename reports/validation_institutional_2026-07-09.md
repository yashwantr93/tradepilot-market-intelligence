# FII/DII + Sector Rotation — Validation Report (2026-07-09)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | OK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 8 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **25**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Improving | 4 |
| Neutral | 4 |
| Weak | 3 |
| Strong | 1 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | 5.35 | 0.82 | Y | Y | Improving | index |
| Financial Services | 7.1 | 2.56 | Y | Y | Improving | index |
| IT | 0.64 | -3.89 | Y | N | Improving | index |
| Auto | 2.75 | -1.79 | Y | Y | Neutral | index |
| Pharma | 5.3 | 0.76 | Y | Y | Improving | index |
| FMCG | 2.06 | -2.48 | Y | N | Neutral | index |
| Capital Goods | 2.6 | -1.93 | Y | Y | Neutral | proxy |
| Defence | 4.34 | -0.2 | N | N | Neutral | basket |
| Realty | 21.63 | 17.1 | Y | Y | Strong | index |
| PSU | -1.68 | -6.22 | N | N | Weak | index |
| Energy | -2.78 | -7.32 | N | N | Weak | index |
| Metals | -4.01 | -8.54 | N | N | Weak | index |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **25 stocks** across **5 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.