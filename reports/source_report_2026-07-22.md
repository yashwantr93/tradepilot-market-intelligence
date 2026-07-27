# Source Success/Failure Report — 2026-07-22

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

| Source | Method | Status | Rows |
| --- | --- | --- | --- |
| NSE bulk-deals archive CSV | archive_csv | OK | 128 |
| NSE block-deals archive CSV | archive_csv | EMPTY | 0 |
| yfinance prices/technicals | yfinance | OK | 22 |
| yfinance sectors | yfinance .info | OK | 19/28 |
| BSE deals | stub | SKIPPED | 0 |


_status: OK = live data fetched · FALLBACK = seed used · EMPTY = reachable but no records · FAIL = unreachable_