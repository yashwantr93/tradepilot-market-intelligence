# FII/DII + Sector Rotation — Validation Report (2026-06-22)

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Sources used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE FII/DII JSON | nse_json | OK | 1 |
| yfinance sector indices/baskets | yfinance | OK | 12 |

## 2. Counts

- FII/DII rows stored: **1** (history depth: 1 session(s))
- Sectors classified: **12**
- Institutional watchlist stocks: **46**

## 3. Sector classification distribution

| Trend | Count |
| --- | --- |
| Improving | 7 |
| Strong | 3 |
| Weak | 2 |

## 4. Sector detail (with data method)

| Sector | 20D % | RS | >20SMA | >50SMA | Trend | Method |
| --- | --- | --- | --- | --- | --- | --- |
| Banking | 4.68 | 4.41 | Y | Y | Strong | index |
| Financial Services | 4.33 | 4.06 | Y | Y | Strong | index |
| IT | -6.51 | -6.77 | N | N | Weak | index |
| Auto | 2.43 | 2.17 | Y | Y | Improving | index |
| Pharma | 1.96 | 1.7 | Y | Y | Improving | index |
| FMCG | -1.79 | -2.05 | Y | N | Improving | index |
| Capital Goods | 2.01 | 1.74 | Y | Y | Improving | proxy |
| Defence | 2.3 | 2.03 | Y | Y | Improving | basket |
| Realty | 7.11 | 6.84 | Y | Y | Strong | index |
| PSU | -1.5 | -1.77 | Y | N | Improving | index |
| Energy | 0.98 | 0.71 | Y | Y | Improving | index |
| Metals | -3.1 | -3.36 | N | N | Weak | index |

## 5. Data-quality notes & limitations

- **FII/DII history:** NSE's public endpoint exposes only the latest trading day, so the 5-day trend builds forward as the pipeline runs daily. No reliable free historical backfill was available.
- **Defence:** no usable NSE index series on the data source → sector performance computed from an equal-weighted constituent **basket** (see Method column).
- **Capital Goods:** uses the Infrastructure index as a documented **proxy** (NSE has no standalone Capital Goods index on the source).
- **Independence:** this watchlist is generated entirely from sector trend + stock RS — fully independent of the bulk/block-deal watchlist, so the two sources can corroborate each other.

## 6. Verdict

Module produces a clean, actionable institutional watchlist of **46 stocks** across **10 Strong/Improving sectors**, with real FII/DII flow context. Ready to serve as a second watchlist candidate source.