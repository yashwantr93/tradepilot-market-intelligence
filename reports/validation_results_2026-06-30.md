# Results Tracker — Validation Report (2026-06-30)

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

_Deterministic, rule-based. No scoring · no ML · no prediction._

## 1. Source used (real data)

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| yfinance quarterly income statements | yfinance | OK | 56 |

## 2. Counts

- Universe processed: **57**
- Symbols with usable financials: **56**
- Results stored: **56**

## 3. Classification distribution

| Classification | Count |
| --- | --- |
| Neutral | 8 |
| Strong | 4 |
| Weak | 4 |

## 4. Growth-basis distribution

| Basis | Count |
| --- | --- |
| YoY | 16 |

## 5. Notes & limitations

- Source: yfinance quarterly income statements (Total Revenue, Net Income). Growth is **YoY** (latest quarter vs the same quarter a year ago); QoQ is a fallback when fewer than 5 quarters are available.
- **Margin** = net profit margin (Net Income / Revenue); margin change is in percentage points.
- Growth off a **loss-making base** is not meaningful and is shown as '-' (classification then leans Neutral).
- **Management guidance** is not available from this source → not captured (would require earnings-call transcripts / a paid feed).
- **Beat/Miss vs estimates** is intentionally NOT computed — it needs analyst consensus (paid). This module classifies on absolute YoY growth only.
- **Independence:** derived purely from financial statements — independent of deal-flow, institutional and corporate-action sources.

## 6. Verdict

Module produced **56 classified quarterly results** from real financial statements. Ready as a fourth independent watchlist candidate source.