"""
Deterministic seed data so the entire backend runs offline, end-to-end.

This provides:
  * a realistic NSE symbol universe (symbol master),
  * synthetic-but-plausible daily OHLCV history (for technical fields),
  * sample bulk/block deals for the latest trading day.

When OFFLINE_MODE is False, connectors attempt live fetches and only fall back
to these generators if the network call fails. Nothing here claims to be real
market data - it exists to exercise the pipeline.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

# (nse_symbol, company_name, sector, isin, base_price, trend)
# trend > 0 = uptrend, < 0 = downtrend, ~0 = sideways. Drives synthetic prices.
SYMBOL_UNIVERSE = [
    ("RELIANCE", "Reliance Industries Ltd", "Energy", "INE002A01018", 2900, 0.04),
    ("TCS", "Tata Consultancy Services", "IT", "INE467B01029", 3850, 0.02),
    ("HDFCBANK", "HDFC Bank Ltd", "Bank", "INE040A01034", 1650, 0.03),
    ("INFY", "Infosys Ltd", "IT", "INE009A01021", 1550, -0.02),
    ("ICICIBANK", "ICICI Bank Ltd", "Bank", "INE090A01021", 1180, 0.06),
    ("BHARTIARTL", "Bharti Airtel Ltd", "Telecom", "INE397D01024", 1480, 0.07),
    ("LT", "Larsen & Toubro Ltd", "Infra", "INE018A01030", 3600, 0.05),
    ("MARUTI", "Maruti Suzuki India", "Auto", "INE585B01010", 12500, 0.03),
    ("TATAMOTORS", "Tata Motors Ltd", "Auto", "INE155A01022", 985, 0.08),
    ("SUNPHARMA", "Sun Pharmaceutical", "Pharma", "INE044A01036", 1620, 0.04),
    ("ITC", "ITC Ltd", "FMCG", "INE154A01025", 445, 0.01),
    ("AXISBANK", "Axis Bank Ltd", "Bank", "INE238A01034", 1120, 0.02),
    ("ADANIENT", "Adani Enterprises", "Infra", "INE423A01024", 3100, -0.03),
    ("TATASTEEL", "Tata Steel Ltd", "Metal", "INE081A01020", 165, 0.05),
    ("HINDUNILVR", "Hindustan Unilever", "FMCG", "INE030A01027", 2380, -0.01),
    ("WIPRO", "Wipro Ltd", "IT", "INE075A01022", 540, 0.02),
    ("ZOMATO", "Zomato Ltd", "Consumer", "INE758T01015", 245, 0.10),
    ("SUZLON", "Suzlon Energy Ltd", "Energy", "INE040H01021", 68, 0.12),
    ("YESBANK", "Yes Bank Ltd", "Bank", "INE528G01035", 24, -0.04),
    ("VEDL", "Vedanta Ltd", "Metal", "INE205A01025", 460, 0.06),
    ("BAJFINANCE", "Bajaj Finance Ltd", "Finance", "INE296A01024", 7200, 0.03),
    ("DLF", "DLF Ltd", "Realty", "INE271C01023", 820, 0.07),
    ("IRFC", "Indian Railway Finance", "Finance", "INE053F01010", 165, 0.09),
    ("BEL", "Bharat Electronics", "Defence", "INE263A01024", 295, 0.11),
    ("PFC", "Power Finance Corp", "Finance", "INE134E01011", 480, 0.08),
    ("COALINDIA", "Coal India Ltd", "Energy", "INE522F01014", 480, 0.02),
    ("ONGC", "Oil & Natural Gas Corp", "Energy", "INE213A01029", 275, 0.01),
    ("NTPC", "NTPC Ltd", "Power", "INE733E01010", 365, 0.05),
    ("POWERGRID", "Power Grid Corp", "Power", "INE752E01010", 320, 0.03),
    ("HAL", "Hindustan Aeronautics", "Defence", "INE066F01020", 4600, 0.10),
]

# Sectoral index proxy used by the benchmark (NIFTY 50) row.
BENCHMARK = ("NIFTY 50", "Nifty 50 Index", "Index", "INDEX_NIFTY50", 23200, 0.03)


def get_symbols() -> list[dict]:
    """Symbol-master rows."""
    rows = []
    for token, (sym, name, sector, isin, _price, _trend) in enumerate(SYMBOL_UNIVERSE, 1):
        rows.append({
            "isin": isin, "nse_symbol": sym, "bse_code": None,
            "company_name": name, "sector": sector,
            "instrument_token": token, "is_active": True,
        })
    return rows


def _generate_ohlc(symbol: str, base_price: float, trend: float,
                   days: int, end: dt.date) -> pd.DataFrame:
    """Deterministic random-walk OHLCV with a per-symbol trend."""
    rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
    dates = pd.bdate_range(end=end, periods=days).date
    daily_drift = trend / days
    rets = rng.normal(daily_drift, 0.018, size=days)
    close = base_price * np.cumprod(1 + rets)
    # Build OHLC around close.
    high = close * (1 + np.abs(rng.normal(0.006, 0.004, size=days)))
    low = close * (1 - np.abs(rng.normal(0.006, 0.004, size=days)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    base_vol = rng.integers(500_000, 5_000_000)
    volume = (base_vol * (1 + np.abs(rng.normal(0, 0.4, size=days)))).astype(int)
    # Inject a volume spike on the final day for some names (exercise the rule).
    if trend > 0.05:
        volume[-1] = int(volume[-1] * rng.uniform(1.6, 2.4))
    return pd.DataFrame({
        "symbol": symbol, "trade_date": dates,
        "open": open_.round(2), "high": high.round(2),
        "low": low.round(2), "close": close.round(2), "volume": volume,
    })


def get_price_history(days: int = 280, end: dt.date | None = None) -> pd.DataFrame:
    """Generate OHLCV for every symbol plus the benchmark."""
    end = end or dt.date.today()
    frames = []
    for sym, _name, _sector, _isin, price, trend in SYMBOL_UNIVERSE:
        frames.append(_generate_ohlc(sym, price, trend, days, end))
    bsym, _bn, _bs, _bi, bprice, btrend = BENCHMARK
    frames.append(_generate_ohlc(bsym, bprice, btrend, days, end))
    return pd.concat(frames, ignore_index=True)


def get_sample_deals(trade_date: dt.date, kind: str) -> pd.DataFrame:
    """Sample bulk/block deals for one day.

    Designed so several rules fire: large BUYs in trending names, a marquee-ish
    buyer, a net SELL caution case, and repeat names.
    """
    rng = np.random.default_rng(int(trade_date.strftime("%Y%m%d")) + (0 if kind == "bulk" else 1))
    # (symbol, client, txn, qty)
    if kind == "bulk":
        specs = [
            ("TATAMOTORS", "Plutus Wealth Management LLP", "BUY", 1_500_000),
            ("SUZLON", "Ashish Kacholia", "BUY", 9_000_000),
            ("ZOMATO", "Nomura India Investment Fund", "BUY", 4_000_000),
            ("BEL", "SBI Mutual Fund", "BUY", 2_000_000),
            ("YESBANK", "Morgan Stanley Asia", "SELL", 12_000_000),
            ("IRFC", "Government Pension Fund Global", "BUY", 6_000_000),
            ("HAL", "ICICI Prudential MF", "BUY", 250_000),
        ]
    else:  # block
        specs = [
            ("DLF", "Goldman Sachs Funds", "BUY", 3_000_000),
            ("VEDL", "Societe Generale", "BUY", 5_000_000),
            ("PFC", "HDFC Mutual Fund", "BUY", 4_500_000),
            ("ADANIENT", "Promoter Group Entity", "SELL", 1_200_000),
            ("BHARTIARTL", "Singtel Group", "BUY", 2_500_000),
        ]
    price_map = {s[0]: s[4] for s in SYMBOL_UNIVERSE}
    rows = []
    for sym, client, txn, qty in specs:
        px = round(price_map.get(sym, 100) * rng.uniform(0.98, 1.02), 2)
        rows.append({
            "trade_date": trade_date, "exchange": "NSE", "symbol": sym,
            "client_name": client, "txn_type": txn,
            "quantity": qty, "price": px,
        })
    return pd.DataFrame(rows)
