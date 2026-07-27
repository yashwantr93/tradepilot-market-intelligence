# Data Quality Report — 2026-06-22

## Coverage

- Deal symbols discovered: **37**
- Symbols with price history (yfinance): **29**
- Symbols missing price data: **8**
- Sectors resolved: **25** / 37

## Validation

- Bulk deal rows ingested: **118**
- Block deal rows ingested: **0**
- Rows quarantined (dead-letter): **0**

## Watchlist field completeness

- Rows with missing current price: **0**
- Rows with Unknown sector: **0**
- Rows with missing 52W-high distance: **0**

## Notes

- Price/technicals source: yfinance (NSE `.NS` tickers). Small-cap / SME / newly-listed symbols may lack history → blank technicals (expected).
- Deal source: NSE public archive CSV (latest trading day).