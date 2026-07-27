# Signal Validation — Engine Performance (2026-07-14)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Measurement & feedback only · real forward returns · no scoring / no ranking / no prediction_

## Coverage

- Signals tracked: **1108**
- Fully evaluated (1/5/20d all available): **0**
- Partially evaluated: **0**
- Pending (forward window not elapsed): **0**
- No price data: **1108**

> Win rate / averages are computed only over signals whose horizon has elapsed. Recently-generated signals stay pending until enough trading days pass.

## 1-Day Forward Return — by Engine (626 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 427 | 352 | 49% | 0.03 | -0.03 | 19.14 | -13.37 |
| Corporate Actions | 121 | 0 | - | - | - | - | - |
| Deal Flow | 168 | 0 | - | - | - | - | - |
| Institutional Flow | 320 | 259 | 49% | -0.03 | -0.02 | 3.84 | -4.91 |
| Results | 72 | 15 | 47% | -0.37 | 0.0 | 2.37 | -4.48 |

## 5-Day Forward Return — by Engine (374 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 427 | 203 | 38% | -0.85 | -0.86 | 18.03 | -17.32 |
| Corporate Actions | 121 | 0 | - | - | - | - | - |
| Deal Flow | 168 | 0 | - | - | - | - | - |
| Institutional Flow | 320 | 156 | 40% | -0.5 | -0.5 | 8.66 | -8.73 |
| Results | 72 | 15 | 67% | 1.72 | 0.78 | 11.61 | -3.8 |

## 20-Day Forward Return — by Engine (15 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 427 | 0 | - | - | - | - | - |
| Corporate Actions | 121 | 0 | - | - | - | - | - |
| Deal Flow | 168 | 0 | - | - | - | - | - |
| Institutional Flow | 320 | 0 | - | - | - | - | - |
| Results | 72 | 15 | 67% | 4.16 | 3.54 | 16.04 | -7.75 |

## Results Engine — by Classification (best available horizon)

_Horizon shown: 20D_

| Classification | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Neutral | 27 | 5 | 40% | -1.23 | -0.98 | 3.54 | -7.75 |
| Strong | 20 | 4 | 100% | 9.06 | 11.16 | 13.78 | 0.12 |
| Weak | 25 | 6 | 67% | 5.38 | 4.72 | 16.04 | -2.35 |

## Confluence Engine — by Tier (best available horizon)

_Horizon shown: 5D_

| Tier | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tier 1 | 9 | 9 | 67% | 0.45 | 0.45 | 3.05 | -2.13 |
| Tier 2 | 286 | 147 | 39% | -0.56 | -0.69 | 8.66 | -8.73 |
| Tier 3 | 132 | 47 | 32% | -2.0 | -1.99 | 18.03 | -17.32 |

## Notes

- **Win** = positive absolute forward return. Returns are price-only (close-to-close), not benchmark-excess.
- **Results** signals are dated at the actual earnings announcement date (yfinance), so the window reflects the post-results reaction.
- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day windows fill in as the system runs daily.
- This layer only measures — it does not rank or weight engines.