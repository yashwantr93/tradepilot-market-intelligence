# FII/DII + Sector Rotation — Validation Report (2026-06-24)

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | OK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 2 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **39**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Strong | 4 |
| Improving | 4 |
| Weak | 3 |
| Neutral | 1 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | 6.48 | 5.3 | Y | Y | Strong | index |
| Financial Services | 5.53 | 4.35 | Y | Y | Strong | index |
| IT | -4.44 | -5.62 | N | N | Weak | index |
| Auto | 4.22 | 3.04 | Y | Y | Strong | index |
| Pharma | 1.7 | 0.52 | Y | Y | Improving | index |
| FMCG | -1.47 | -2.65 | Y | N | Improving | index |
| Capital Goods | 1.74 | 0.56 | Y | Y | Improving | proxy |
| Defence | 1.18 | 0.0 | Y | N | Improving | basket |
| Realty | 7.59 | 6.41 | Y | Y | Strong | index |
| PSU | -3.12 | -4.3 | N | N | Weak | index |
| Energy | -0.93 | -2.11 | N | N | Neutral | index |
| Metals | -5.69 | -6.87 | N | N | Weak | index |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **39 stocks** across **8 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.