# Signal Validation — Engine Performance (2026-06-25)

_Measurement & feedback only · real forward returns · no scoring / no ranking / no prediction_

## Coverage

- Signals tracked: **327**
- Fully evaluated (1/5/20d all available): **59**
- Partially evaluated: **259**
- Pending (forward window not elapsed): **7**
- No price data: **2**

> Win rate / averages are computed only over signals whose horizon has elapsed. Recently-generated signals stay pending until enough trading days pass.

## 1-Day Forward Return — by Engine (318 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 117 | 116 | 55% | 0.14 | 0.24 | 9.18 | -6.98 |
| Corporate Actions | 24 | 17 | 59% | 0.72 | 0.24 | 4.97 | -1.8 |
| Deal Flow | 41 | 40 | 57% | 0.27 | 0.35 | 9.18 | -6.98 |
| Institutional Flow | 85 | 85 | 58% | 0.17 | 0.27 | 4.36 | -3.28 |
| Results | 60 | 60 | 32% | -2.05 | -1.0 | 8.22 | -64.9 |

## 5-Day Forward Return — by Engine (60 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 117 | 0 | - | - | - | - | - |
| Corporate Actions | 24 | 0 | - | - | - | - | - |
| Deal Flow | 41 | 0 | - | - | - | - | - |
| Institutional Flow | 85 | 0 | - | - | - | - | - |
| Results | 60 | 60 | 40% | -1.51 | -1.16 | 11.61 | -59.1 |

## 20-Day Forward Return — by Engine (59 evaluated)

| Engine | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Confluence | 117 | 0 | - | - | - | - | - |
| Corporate Actions | 24 | 0 | - | - | - | - | - |
| Deal Flow | 41 | 0 | - | - | - | - | - |
| Institutional Flow | 85 | 0 | - | - | - | - | - |
| Results | 60 | 59 | 37% | -1.81 | -1.3 | 39.93 | -54.15 |

## Results Engine — by Classification (best available horizon)

_Horizon shown: 20D_

| Classification | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Neutral | 21 | 21 | 19% | -4.23 | -4.79 | 9.02 | -16.6 |
| Strong | 18 | 17 | 53% | -0.04 | 0.12 | 39.93 | -54.15 |
| Weak | 21 | 21 | 43% | -0.83 | -0.22 | 16.04 | -11.36 |

## Confluence Engine — by Tier (best available horizon)

_Horizon shown: 1D_

| Tier | Signals | Evaluated | Win Rate | Avg % | Median % | Best % | Worst % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tier 1 | 9 | 9 | 89% | 0.95 | 0.79 | 3.57 | -0.59 |
| Tier 2 | 76 | 76 | 54% | 0.08 | 0.14 | 4.36 | -3.28 |
| Tier 3 | 32 | 31 | 48% | 0.07 | -0.08 | 9.18 | -6.98 |

## Notes

- **Win** = positive absolute forward return. Returns are price-only (close-to-close), not benchmark-excess.
- **Results** signals are dated at the actual earnings announcement date (yfinance), so the window reflects the post-results reaction.
- **Deal Flow / Institutional / Confluence** signals are recent; their 5/20-day windows fill in as the system runs daily.
- This layer only measures — it does not rank or weight engines.