# Signal Validation — Engine Performance (2026-07-09)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Measurement & feedback only · real forward returns · no scoring / no ranking / no prediction_

## Coverage

- Signals tracked: **918**
- Fully evaluated (1/5/20d all available): **62**
- Partially evaluated: **781**
- Pending (forward window not elapsed): **48**
- No price data: **27**

> Win rate / averages are computed only over signals whose horizon has elapsed. Recently-generated signals stay pending until enough trading days pass.

## 1-Day Forward Return — by Engine (843 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 377 | 352 | 49% | 0.03 | -0.03 | 19.14 | -13.37 |
| Corporate Actions | 93 | 68 | 44% | 0.37 | 0.0 | 9.91 | -5.0 |
| Deal Flow | 120 | 102 | 49% | 0.2 | -0.05 | 19.14 | -13.37 |
| Institutional Flow | 266 | 259 | 49% | -0.03 | -0.02 | 3.84 | -4.91 |
| Results | 62 | 62 | 32% | -2.0 | -1.0 | 8.22 | -64.9 |

## 5-Day Forward Return — by Engine (503 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 377 | 203 | 38% | -0.85 | -0.86 | 18.03 | -17.32 |
| Corporate Actions | 93 | 26 | 50% | -0.53 | 0.04 | 5.75 | -9.93 |
| Deal Flow | 120 | 56 | 38% | -1.6 | -1.1 | 18.03 | -17.32 |
| Institutional Flow | 266 | 156 | 40% | -0.5 | -0.5 | 8.66 | -8.73 |
| Results | 62 | 62 | 40% | -1.51 | -1.16 | 11.61 | -59.1 |

## 20-Day Forward Return — by Engine (62 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 377 | 0 | - | - | - | - | - |
| Corporate Actions | 93 | 0 | - | - | - | - | - |
| Deal Flow | 120 | 0 | - | - | - | - | - |
| Institutional Flow | 266 | 0 | - | - | - | - | - |
| Results | 62 | 62 | 40% | -1.47 | -1.06 | 39.93 | -54.15 |

## Results Engine — by Classification (best available horizon)

_Horizon shown: 20D_

| Classification | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Neutral | 21 | 21 | 19% | -4.23 | -4.79 | 9.02 | -16.6 |
| Strong | 18 | 18 | 56% | 0.19 | 0.29 | 39.93 | -54.15 |
| Weak | 23 | 23 | 48% | -0.24 | -0.12 | 16.04 | -11.36 |

## Confluence Engine — by Tier (best available horizon)

_Horizon shown: 5D_

| Tier | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tier 1 | 9 | 9 | 67% | 0.45 | 0.45 | 3.05 | -2.13 |
| Tier 2 | 257 | 147 | 39% | -0.56 | -0.69 | 8.66 | -8.73 |
| Tier 3 | 111 | 47 | 32% | -2.0 | -1.99 | 18.03 | -17.32 |

## Notes

- **Win** = positive absolute forward return. Returns are price-only (close-to-close), not benchmark-excess.
- **Results** signals are dated at the actual earnings announcement date (yfinance), so the window reflects the post-results reaction.
- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day windows fill in as the system runs daily.
- This layer only measures — it does not rank or weight engines.