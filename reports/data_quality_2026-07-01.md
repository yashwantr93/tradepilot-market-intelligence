# Data Quality Report — 2026-07-01

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

## Coverage

- Deal symbols discovered: **27**
- Symbols with price history (yfinance): **22**
- Symbols missing price data: **5**
- Sectors resolved: **20** / 27

## Validation

- Bulk deal rows ingested: **110**
- Block deal rows ingested: **0**
- Rows quarantined (dead-letter): **0**

## Watchlist field completeness

- Rows with missing current price: **1**
- Rows with Unknown sector: **1**
- Rows with missing 52W-high distance: **1**

## Notes

- Price/technicals source: yfinance (NSE `.NS` tickers). Small-cap / SME / newly-listed symbols may lack history → blank technicals (expected).
- Deal source: NSE public archive CSV (latest trading day).