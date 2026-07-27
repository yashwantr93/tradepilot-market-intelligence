# Data Quality Report — 2026-07-23

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

## Coverage

- Deal symbols discovered: **22**
- Symbols with price history (yfinance): **21**
- Symbols missing price data: **1**
- Sectors resolved: **19** / 22

## Validation

- Bulk deal rows ingested: **145**
- Block deal rows ingested: **0**
- Rows quarantined (dead-letter): **0**

## Watchlist field completeness

- Rows with missing current price: **0**
- Rows with Unknown sector: **1**
- Rows with missing 52W-high distance: **0**

## Notes

- Price/technicals source: yfinance (NSE `.NS` tickers). Small-cap / SME / newly-listed symbols may lack history → blank technicals (expected).
- Deal source: NSE public archive CSV (latest trading day).