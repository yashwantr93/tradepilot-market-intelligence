# FII/DII + Sector Rotation — Validation Report (2026-07-01)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | OK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 3 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **39**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Improving | 6 |
| Weak | 4 |
| Strong | 2 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | 7.13 | 3.84 | Y | Y | Strong | index |
| Financial Services | 5.96 | 2.68 | Y | Y | Improving | index |
| IT | -8.33 | -11.62 | N | N | Weak | index |
| Auto | 2.81 | -0.48 | Y | Y | Improving | index |
| Pharma | 5.16 | 1.88 | Y | Y | Improving | index |
| FMCG | 1.44 | -1.84 | Y | Y | Improving | index |
| Capital Goods | 1.12 | -2.17 | Y | Y | Improving | proxy |
| Defence | 5.68 | 2.39 | Y | Y | Improving | basket |
| Realty | 11.41 | 8.12 | Y | Y | Strong | index |
| PSU | -1.8 | -5.09 | N | N | Weak | index |
| Energy | -2.85 | -6.14 | N | N | Weak | index |
| Metals | -6.99 | -10.28 | N | N | Weak | index |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **39 stocks** across **8 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.