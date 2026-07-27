# Signal Validation — Engine Performance (2026-07-24)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Measurement & feedback only · real forward returns · no scoring / no ranking / no prediction_

## Coverage

- Signals tracked: **1269**
- Fully evaluated (1/5/20d all available): **333**
- Partially evaluated: **813**
- Pending (forward window not elapsed): **51**
- No price data: **72**

> Win rate / averages are computed only over signals whose horizon has elapsed. Recently-generated signals stay pending until enough trading days pass.

## 1-Day Forward Return — by Engine (1146 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 475 | 429 | 49% | 0.09 | -0.02 | 19.14 | -13.37 |
| Corporate Actions | 154 | 131 | 44% | 0.11 | -0.02 | 9.91 | -6.95 |
| Deal Flow | 206 | 178 | 47% | 0.26 | -0.16 | 19.14 | -13.37 |
| Institutional Flow | 344 | 320 | 53% | 0.15 | 0.12 | 5.08 | -5.89 |
| Results | 90 | 88 | 40% | -1.38 | -0.34 | 8.22 | -64.9 |

## 5-Day Forward Return — by Engine (1099 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 475 | 421 | 49% | -0.0 | -0.07 | 46.49 | -17.32 |
| Corporate Actions | 154 | 119 | 51% | -0.33 | 0.08 | 13.04 | -13.8 |
| Deal Flow | 206 | 161 | 50% | 0.55 | -0.09 | 46.49 | -17.32 |
| Institutional Flow | 344 | 320 | 49% | 0.03 | -0.01 | 9.59 | -8.87 |
| Results | 90 | 78 | 49% | -0.24 | -0.24 | 15.24 | -59.1 |

## 20-Day Forward Return — by Engine (333 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 475 | 116 | 53% | 0.43 | 1.08 | 21.17 | -16.29 |
| Corporate Actions | 154 | 18 | 50% | 0.49 | -0.01 | 22.18 | -23.05 |
| Deal Flow | 206 | 40 | 38% | -1.99 | -2.07 | 21.17 | -16.29 |
| Institutional Flow | 344 | 85 | 60% | 1.47 | 2.24 | 17.78 | -10.6 |
| Results | 90 | 74 | 49% | 0.02 | -0.06 | 39.93 | -54.15 |

## Results Engine — by Classification (best available horizon)

_Horizon shown: 20D_

| Classification | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Neutral | 35 | 27 | 33% | -2.23 | -2.33 | 9.02 | -16.6 |
| Strong | 24 | 20 | 60% | 2.08 | 0.64 | 39.93 | -54.15 |
| Weak | 31 | 27 | 56% | 0.74 | 0.6 | 16.04 | -11.36 |

## Confluence Engine — by Tier (best available horizon)

_Horizon shown: 20D_

| Tier | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tier 1 | 9 | 9 | 44% | -0.54 | -0.15 | 7.66 | -10.48 |
| Tier 2 | 310 | 76 | 62% | 1.71 | 2.28 | 17.78 | -10.6 |
| Tier 3 | 156 | 31 | 35% | -2.41 | -3.84 | 21.17 | -16.29 |

## Notes

- **Win** = positive absolute forward return. Returns are price-only (close-to-close), not benchmark-excess.
- **Results** signals are dated at the actual earnings announcement date (yfinance), so the window reflects the post-results reaction.
- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day windows fill in as the system runs daily.
- This layer only measures — it does not rank or weight engines.