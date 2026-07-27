# Data Quality Report — 2026-07-21

_Swing Trading Intelligence System — Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls_

## Coverage

- Deal symbols discovered: **12**
- Symbols with price history (yfinance): **12**
- Symbols missing price data: **0**
- Sectors resolved: **0** / 12

## Validation

- Bulk deal rows ingested: **7**
- Block deal rows ingested: **5**
- Rows quarantined (dead-letter): **0**

## Watchlist field completeness

- Rows with missing current price: **0**
- Rows with Unknown sector: **10**
- Rows with missing 52W-high distance: **0**

## Notes

- Price/technicals source: yfinance (NSE `.NS` tickers). Small-cap / SME / newly-listed symbols may lack history → blank technicals (expected).
- Deal source: NSE public archive CSV (latest trading day).