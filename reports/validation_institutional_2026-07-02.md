# FII/DII + Sector Rotation — Validation Report (2026-07-02)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | OK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 4 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **44**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Improving | 7 |
| Weak | 3 |
| Strong | 2 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | 6.53 | 2.64 | Y | Y | Improving | index |
| Financial Services | 6.17 | 2.28 | Y | Y | Improving | index |
| IT | -5.8 | -9.69 | N | N | Weak | index |
| Auto | 2.78 | -1.1 | Y | Y | Improving | index |
| Pharma | 6.8 | 2.91 | Y | Y | Improving | index |
| FMCG | 1.48 | -2.41 | Y | Y | Improving | index |
| Capital Goods | 1.32 | -2.57 | Y | Y | Improving | proxy |
| Defence | 7.11 | 3.23 | Y | Y | Strong | basket |
| Realty | 13.35 | 9.46 | Y | Y | Strong | index |
| PSU | -1.62 | -5.51 | Y | N | Improving | index |
| Energy | -3.96 | -7.85 | N | N | Weak | index |
| Metals | -5.96 | -9.85 | N | N | Weak | index |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **44 stocks** across **9 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.