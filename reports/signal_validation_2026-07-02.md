# Signal Validation — Engine Performance (2026-07-02)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Measurement & feedback only · real forward returns · no scoring / no ranking / no prediction_

## Coverage

- Signals tracked: **453**
- Fully evaluated (1/5/20d all available): **61**
- Partially evaluated: **367**
- Pending (forward window not elapsed): **5**
- No price data: **20**

> Win rate / averages are computed only over signals whose horizon has elapsed. Recently-generated signals stay pending until enough trading days pass.

## 1-Day Forward Return — by Engine (428 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 169 | 167 | 44% | -0.14 | -0.12 | 9.18 | -13.37 |
| Corporate Actions | 45 | 24 | 50% | 0.47 | 0.1 | 6.89 | -4.07 |
| Deal Flow | 54 | 52 | 40% | -0.53 | -0.65 | 9.18 | -13.37 |
| Institutional Flow | 124 | 124 | 47% | 0.07 | -0.04 | 3.84 | -3.28 |
| Results | 61 | 61 | 33% | -2.01 | -0.87 | 8.22 | -64.9 |

## 5-Day Forward Return — by Engine (321 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 169 | 116 | 47% | -0.38 | -0.16 | 18.03 | -17.32 |
| Corporate Actions | 45 | 19 | 47% | -0.79 | 0.0 | 5.75 | -14.43 |
| Deal Flow | 54 | 40 | 40% | -1.74 | -1.14 | 18.03 | -17.32 |
| Institutional Flow | 124 | 85 | 52% | 0.35 | 0.45 | 8.81 | -5.72 |
| Results | 61 | 61 | 41% | -1.49 | -1.12 | 11.61 | -59.1 |

## 20-Day Forward Return — by Engine (61 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 169 | 0 | - | - | - | - | - |
| Corporate Actions | 45 | 0 | - | - | - | - | - |
| Deal Flow | 54 | 0 | - | - | - | - | - |
| Institutional Flow | 124 | 0 | - | - | - | - | - |
| Results | 61 | 61 | 39% | -1.57 | -1.13 | 39.93 | -54.15 |

## Results Engine — by Classification (best available horizon)

_Horizon shown: 20D_

| Classification | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Neutral | 21 | 21 | 19% | -4.23 | -4.79 | 9.02 | -16.6 |
| Strong | 18 | 18 | 56% | 0.19 | 0.29 | 39.93 | -54.15 |
| Weak | 22 | 22 | 45% | -0.45 | -0.17 | 16.04 | -11.36 |

## Confluence Engine — by Tier (best available horizon)

_Horizon shown: 5D_

| Tier | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tier 1 | 9 | 9 | 67% | 0.45 | 0.45 | 3.05 | -2.13 |
| Tier 2 | 115 | 76 | 50% | 0.34 | 0.26 | 8.81 | -5.72 |
| Tier 3 | 45 | 31 | 32% | -2.38 | -3.12 | 18.03 | -17.32 |

## Notes

- **Win** = positive absolute forward return. Returns are price-only (close-to-close), not benchmark-excess.
- **Results** signals are dated at the actual earnings announcement date (yfinance), so the window reflects the post-results reaction.
- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day windows fill in as the system runs daily.
- This layer only measures — it does not rank or weight engines.