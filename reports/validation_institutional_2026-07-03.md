# FII/DII + Sector Rotation — Validation Report (2026-07-03)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | OK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 5 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **39**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Improving | 7 |
| Weak | 4 |
| Strong | 1 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | 6.69 | 3.04 | Y | Y | Strong | index |
| Financial Services | 3.95 | 0.31 | Y | Y | Improving | index |
| IT | -6.35 | -10.0 | N | N | Weak | index |
| Auto | 0.42 | -3.23 | Y | Y | Improving | index |
| Pharma | 6.48 | 2.83 | Y | Y | Improving | index |
| FMCG | 4.66 | 1.02 | Y | Y | Improving | basket |
| Capital Goods | -0.41 | -4.05 | Y | Y | Improving | proxy |
| Defence | 6.6 | 2.95 | Y | Y | Improving | basket |
| Realty | 5.32 | 1.67 | Y | Y | Improving | index |
| PSU | -4.98 | -8.62 | N | N | Weak | index |
| Energy | -4.57 | -8.22 | N | N | Weak | index |
| Metals | -9.28 | -12.93 | N | N | Weak | index |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **39 stocks** across **8 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.