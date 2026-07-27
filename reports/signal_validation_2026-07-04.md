# Signal Validation — Engine Performance (2026-07-04)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Measurement & feedback only · real forward returns · no scoring / no ranking / no prediction_

## Coverage

- Signals tracked: **708**
- Fully evaluated (1/5/20d all available): **58**
- Partially evaluated: **458**
- Pending (forward window not elapsed): **116**
- No price data: **76**

> Win rate / averages are computed only over signals whose horizon has elapsed. Recently-generated signals stay pending until enough trading days pass.

## 1-Day Forward Return — by Engine (541 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 280 | 226 | 48% | 0.13 | -0.04 | 19.14 | -13.37 |
| Corporate Actions | 77 | 27 | 56% | 0.92 | 0.24 | 6.89 | -4.07 |
| Deal Flow | 82 | 61 | 44% | 0.22 | -0.43 | 19.14 | -13.37 |
| Institutional Flow | 207 | 168 | 50% | 0.13 | 0.0 | 3.84 | -4.57 |
| Results | 62 | 59 | 32% | -2.08 | -0.87 | 8.22 | -64.9 |

## 5-Day Forward Return — by Engine (319 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 280 | 116 | 46% | -0.44 | -0.16 | 18.03 | -17.32 |
| Corporate Actions | 77 | 23 | 48% | -0.35 | 0.0 | 5.75 | -9.93 |
| Deal Flow | 82 | 36 | 42% | -1.69 | -1.14 | 18.03 | -17.32 |
| Institutional Flow | 207 | 85 | 51% | 0.22 | 0.37 | 8.66 | -5.72 |
| Results | 62 | 59 | 42% | -1.39 | -0.67 | 11.61 | -59.1 |

## 20-Day Forward Return — by Engine (59 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 280 | 0 | - | - | - | - | - |
| Corporate Actions | 77 | 0 | - | - | - | - | - |
| Deal Flow | 82 | 0 | - | - | - | - | - |
| Institutional Flow | 207 | 0 | - | - | - | - | - |
| Results | 62 | 59 | 41% | -1.34 | -0.98 | 39.93 | -54.15 |

## Results Engine — by Classification (best available horizon)

_Horizon shown: 20D_

| Classification | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Neutral | 21 | 21 | 19% | -4.23 | -4.79 | 9.02 | -16.6 |
| Strong | 18 | 18 | 56% | 0.19 | 0.29 | 39.93 | -54.15 |
| Weak | 23 | 20 | 50% | 0.33 | 0.06 | 16.04 | -11.36 |

## Confluence Engine — by Tier (best available horizon)

_Horizon shown: 5D_

| Tier | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tier 1 | 9 | 9 | 67% | 0.45 | 0.45 | 3.05 | -2.13 |
| Tier 2 | 198 | 76 | 49% | 0.19 | -0.02 | 8.66 | -5.72 |
| Tier 3 | 73 | 31 | 32% | -2.26 | -2.9 | 18.03 | -17.32 |

## Notes

- **Win** = positive absolute forward return. Returns are price-only (close-to-close), not benchmark-excess.
- **Results** signals are dated at the actual earnings announcement date (yfinance), so the window reflects the post-results reaction.
- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day windows fill in as the system runs daily.
- This layer only measures — it does not rank or weight engines.