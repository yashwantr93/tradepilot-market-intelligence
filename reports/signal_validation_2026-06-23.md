# Signal Validation — Engine Performance (2026-06-23)

_Measurement & feedback only · real forward returns · no scoring / no ranking / no prediction_

## Coverage

- Signals tracked: **200**
- Fully evaluated (1/5/20d all available): **53**
- Partially evaluated: **123**
- Pending (forward window not elapsed): **12**
- No price data: **12**

> Win rate / averages are computed only over signals whose horizon has elapsed. Recently-generated signals stay pending until enough trading days pass.

## 1-Day Forward Return — by Engine (176 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 60 | 60 | 67% | 0.47 | 0.4 | 5.72 | -4.34 |
| Corporate Actions | 24 | 0 | - | - | - | - | - |
| Deal Flow | 14 | 14 | 57% | 0.55 | 0.94 | 5.72 | -4.34 |
| Institutional Flow | 46 | 46 | 70% | 0.44 | 0.4 | 3.9 | -1.77 |
| Results | 56 | 56 | 30% | -2.22 | -1.23 | 8.22 | -64.9 |

## 5-Day Forward Return — by Engine (56 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 60 | 0 | - | - | - | - | - |
| Corporate Actions | 24 | 0 | - | - | - | - | - |
| Deal Flow | 14 | 0 | - | - | - | - | - |
| Institutional Flow | 46 | 0 | - | - | - | - | - |
| Results | 56 | 56 | 38% | -2.03 | -1.43 | 10.07 | -59.1 |

## 20-Day Forward Return — by Engine (53 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 60 | 0 | - | - | - | - | - |
| Corporate Actions | 24 | 0 | - | - | - | - | - |
| Deal Flow | 14 | 0 | - | - | - | - | - |
| Institutional Flow | 46 | 0 | - | - | - | - | - |
| Results | 56 | 53 | 32% | -2.67 | -1.91 | 39.93 | -54.15 |

## Results Engine — by Classification (best available horizon)

_Horizon shown: 20D_

| Classification | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Neutral | 21 | 21 | 19% | -4.22 | -4.79 | 9.02 | -16.6 |
| Strong | 16 | 15 | 47% | -0.99 | -0.36 | 39.93 | -54.15 |
| Weak | 19 | 17 | 35% | -2.24 | -0.34 | 13.18 | -11.36 |

## Confluence Engine — by Tier (best available horizon)

_Horizon shown: 1D_

| Tier | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tier 2 | 46 | 46 | 70% | 0.44 | 0.4 | 3.9 | -1.77 |
| Tier 3 | 14 | 14 | 57% | 0.55 | 0.94 | 5.72 | -4.34 |

## Notes

- **Win** = positive absolute forward return. Returns are price-only (close-to-close), not benchmark-excess.
- **Results** signals are dated at the actual earnings announcement date (yfinance), so the window reflects the post-results reaction.
- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day windows fill in as the system runs daily.
- This layer only measures — it does not rank or weight engines.