# Signal Validation — Engine Performance (2026-07-08)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Measurement & feedback only · real forward returns · no scoring / no ranking / no prediction_

## Coverage

- Signals tracked: **818**
- Fully evaluated (1/5/20d all available): **62**
- Partially evaluated: **688**
- Pending (forward window not elapsed): **40**
- No price data: **28**

> Win rate / averages are computed only over signals whose horizon has elapsed. Recently-generated signals stay pending until enough trading days pass.

## 1-Day Forward Return — by Engine (752 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 329 | 310 | 51% | 0.14 | 0.03 | 19.14 | -13.37 |
| Corporate Actions | 89 | 63 | 43% | 0.36 | 0.0 | 9.91 | -5.0 |
| Deal Flow | 97 | 83 | 45% | -0.04 | -0.49 | 19.14 | -13.37 |
| Institutional Flow | 241 | 234 | 53% | 0.21 | 0.09 | 3.84 | -4.57 |
| Results | 62 | 62 | 32% | -2.0 | -1.0 | 8.22 | -64.9 |

## 5-Day Forward Return — by Engine (387 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 329 | 147 | 47% | -0.29 | -0.1 | 18.03 | -17.32 |
| Corporate Actions | 89 | 24 | 50% | -0.62 | 0.04 | 5.75 | -9.93 |
| Deal Flow | 97 | 42 | 36% | -1.86 | -1.57 | 18.03 | -17.32 |
| Institutional Flow | 241 | 112 | 52% | 0.32 | 0.42 | 8.66 | -8.81 |
| Results | 62 | 62 | 40% | -1.51 | -1.16 | 11.61 | -59.1 |

## 20-Day Forward Return — by Engine (62 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 329 | 0 | - | - | - | - | - |
| Corporate Actions | 89 | 0 | - | - | - | - | - |
| Deal Flow | 97 | 0 | - | - | - | - | - |
| Institutional Flow | 241 | 0 | - | - | - | - | - |
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
| Tier 2 | 232 | 103 | 50% | 0.31 | 0.38 | 8.66 | -8.81 |
| Tier 3 | 88 | 35 | 31% | -2.26 | -2.84 | 18.03 | -17.32 |

## Notes

- **Win** = positive absolute forward return. Returns are price-only (close-to-close), not benchmark-excess.
- **Results** signals are dated at the actual earnings announcement date (yfinance), so the window reflects the post-results reaction.
- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day windows fill in as the system runs daily.
- This layer only measures — it does not rank or weight engines.