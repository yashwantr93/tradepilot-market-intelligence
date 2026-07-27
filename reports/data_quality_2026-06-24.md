# Data Quality Report — 2026-06-24

## Coverage

- Deal symbols discovered: **45**
- Symbols with price history (yfinance): **38**
- Symbols missing price data: **7**
- Sectors resolved: **36** / 45

## Validation

- Bulk deal rows ingested: **104**
- Block deal rows ingested: **35**
- Rows quarantined (dead-letter): **0**

## Watchlist field completeness

- Rows with missing current price: **1**
- Rows with Unknown sector: **1**
- Rows with missing 52W-high distance: **1**

## Notes

- Price/technicals source: yfinance (NSE `.NS` tickers). Small-cap / SME / newly-listed symbols may lack history → blank technicals (expected).
- Deal source: NSE public archive CSV (latest trading day).