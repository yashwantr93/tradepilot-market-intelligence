# Signal Validation — Engine Performance (2026-07-21)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Measurement & feedback only · real forward returns · no scoring / no ranking / no prediction_

## Coverage

- Signals tracked: **1140**
- Fully evaluated (1/5/20d all available): **204**
- Partially evaluated: **892**
- Pending (forward window not elapsed): **26**
- No price data: **18**

> Win rate / averages are computed only over signals whose horizon has elapsed. Recently-generated signals stay pending until enough trading days pass.

## 1-Day Forward Return — by Engine (1096 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 437 | 421 | 50% | 0.11 | 0.0 | 19.14 | -13.37 |
| Corporate Actions | 132 | 121 | 45% | 0.18 | 0.0 | 9.91 | -6.95 |
| Deal Flow | 178 | 161 | 50% | 0.43 | 0.14 | 19.14 | -13.37 |
| Institutional Flow | 320 | 320 | 53% | 0.15 | 0.12 | 5.08 | -5.89 |
| Results | 73 | 73 | 38% | -1.67 | -0.37 | 8.22 | -64.9 |

## 5-Day Forward Return — by Engine (1089 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 437 | 421 | 49% | -0.0 | -0.07 | 46.49 | -17.32 |
| Corporate Actions | 132 | 114 | 53% | -0.23 | 0.1 | 13.04 | -13.8 |
| Deal Flow | 178 | 161 | 50% | 0.55 | -0.09 | 46.49 | -17.32 |
| Institutional Flow | 320 | 320 | 49% | 0.03 | -0.01 | 9.59 | -8.87 |
| Results | 73 | 73 | 48% | -0.26 | -0.29 | 15.24 | -59.1 |

## 20-Day Forward Return — by Engine (204 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 437 | 60 | 50% | 0.03 | 0.21 | 17.78 | -16.29 |
| Corporate Actions | 132 | 12 | 50% | 0.88 | -0.01 | 22.18 | -12.64 |
| Deal Flow | 178 | 14 | 29% | -4.49 | -4.78 | 11.19 | -16.29 |
| Institutional Flow | 320 | 46 | 57% | 1.4 | 1.81 | 17.78 | -10.6 |
| Results | 73 | 72 | 47% | -0.13 | -0.17 | 39.93 | -54.15 |

## Results Engine — by Classification (best available horizon)

_Horizon shown: 20D_

| Classification | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Neutral | 27 | 26 | 31% | -2.49 | -2.43 | 9.02 | -16.6 |
| Strong | 20 | 20 | 60% | 2.08 | 0.64 | 39.93 | -54.15 |
| Weak | 26 | 26 | 54% | 0.52 | 0.42 | 16.04 | -11.36 |

## Confluence Engine — by Tier (best available horizon)

_Horizon shown: 20D_

| Tier | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tier 1 | 9 | 0 | - | - | - | - | - |
| Tier 2 | 286 | 46 | 57% | 1.4 | 1.81 | 17.78 | -10.6 |
| Tier 3 | 142 | 14 | 29% | -4.49 | -4.78 | 11.19 | -16.29 |

## Notes

- **Win** = positive absolute forward return. Returns are price-only (close-to-close), not benchmark-excess.
- **Results** signals are dated at the actual earnings announcement date (yfinance), so the window reflects the post-results reaction.
- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day windows fill in as the system runs daily.
- This layer only measures — it does not rank or weight engines.