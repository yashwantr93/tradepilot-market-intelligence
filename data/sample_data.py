"""
Sample / dummy data provider for the Indian Market Intelligence Dashboard.

This module is the single source of truth for all placeholder data used across
the dashboard. When real APIs are integrated later, only the functions in this
module need to change - the UI layer consumes these functions and is agnostic
to where the data comes from.

Each function returns plain pandas DataFrames or simple dicts so the UI stays
decoupled from the data source.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

# Seed for reproducible dummy data so the dashboard looks consistent on reloads.
_RNG = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Tab 1: Market Overview
# ---------------------------------------------------------------------------
def get_index_snapshot() -> pd.DataFrame:
    """Top-level index KPIs (price, change, % change)."""
    rows = [
        ("Nifty 50", 23_245.90, 142.35),
        ("Bank Nifty", 50_115.40, -218.65),
        ("Nifty Midcap 100", 53_890.25, 415.10),
        ("Nifty Smallcap 100", 17_420.80, 122.45),
        ("India VIX", 13.42, -0.58),
    ]
    data = []
    for name, last, change in rows:
        prev = last - change
        pct = (change / prev) * 100 if prev else 0.0
        data.append(
            {
                "Index": name,
                "Last": last,
                "Change": change,
                "% Change": round(pct, 2),
            }
        )
    return pd.DataFrame(data)


def get_market_breadth() -> dict:
    """Advance / Decline / Unchanged counts plus a derived sentiment score."""
    advances = 1_142
    declines = 728
    unchanged = 130
    total = advances + declines + unchanged
    breadth_pct = round((advances / (advances + declines)) * 100, 1)
    return {
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "total": total,
        "breadth_pct": breadth_pct,
    }


def get_market_sentiment() -> dict:
    """Composite market sentiment indicator (0-100 'fear/greed' style score)."""
    score = 64  # 0 = Extreme Fear, 100 = Extreme Greed
    if score >= 75:
        label, color = "Extreme Greed", "#16a34a"
    elif score >= 55:
        label, color = "Greed", "#65a30d"
    elif score >= 45:
        label, color = "Neutral", "#ca8a04"
    elif score >= 25:
        label, color = "Fear", "#ea580c"
    else:
        label, color = "Extreme Fear", "#dc2626"
    return {"score": score, "label": label, "color": color}


def get_advance_decline_history(days: int = 15) -> pd.DataFrame:
    """Daily advance vs decline history for a stacked/bar chart."""
    end = dt.date.today()
    dates = [end - dt.timedelta(days=i) for i in range(days)][::-1]
    advances = _RNG.integers(700, 1300, size=days)
    declines = 2000 - advances - _RNG.integers(80, 200, size=days)
    return pd.DataFrame(
        {
            "Date": dates,
            "Advances": advances,
            "Declines": declines,
        }
    )


def get_sector_performance() -> pd.DataFrame:
    """Sector-level % change used for the heatmap."""
    sectors = [
        "Nifty IT",
        "Nifty Bank",
        "Nifty Auto",
        "Nifty Pharma",
        "Nifty FMCG",
        "Nifty Metal",
        "Nifty Realty",
        "Nifty Energy",
        "Nifty PSU Bank",
        "Nifty Media",
        "Nifty Fin Services",
        "Nifty Consumer Durables",
    ]
    changes = _RNG.uniform(-2.5, 2.8, size=len(sectors)).round(2)
    return pd.DataFrame({"Sector": sectors, "% Change": changes})


def get_support_resistance() -> pd.DataFrame:
    """Key support and resistance levels for the headline indices."""
    return pd.DataFrame(
        [
            {"Index": "Nifty 50", "S2": 22_850, "S1": 23_050, "R1": 23_400, "R2": 23_620},
            {"Index": "Bank Nifty", "S2": 49_400, "S1": 49_800, "R1": 50_500, "R2": 50_950},
            {"Index": "Nifty Midcap", "S2": 53_100, "S1": 53_500, "R1": 54_200, "R2": 54_700},
        ]
    )


# ---------------------------------------------------------------------------
# Tab 2: Corporate Actions
# ---------------------------------------------------------------------------
def get_corporate_actions() -> pd.DataFrame:
    """Sample corporate action announcements across all action types."""
    records = [
        ("Tata Consultancy Services", "Buyback", "2026-06-18",
         "Buyback of 4.1 Cr shares at ₹4,500 (tender route)", "Positive", "Short Term"),
        ("Infosys Ltd", "Bonus Issue", "2026-06-15",
         "1:1 bonus issue announced for eligible shareholders", "Positive", "Medium Term"),
        ("Avenue Supermarts", "Stock Split", "2026-06-12",
         "Stock split from ₹10 to ₹2 face value", "Neutral", "Short Term"),
        ("ITC Ltd", "Dividend", "2026-06-10",
         "Final dividend of ₹7.50 per share declared", "Positive", "Short Term"),
        ("Vodafone Idea", "Rights Issue", "2026-06-08",
         "Rights issue of ₹18,000 Cr at ₹11 per share", "Negative", "Medium Term"),
        ("Adani Green Energy", "QIP", "2026-06-05",
         "QIP to raise ₹9,350 Cr from institutional investors", "Neutral", "Medium Term"),
        ("Yes Bank", "Fund Raising", "2026-06-03",
         "Board approves fund raising up to ₹7,500 Cr via debt", "Neutral", "Long Term"),
        ("Larsen & Toubro", "Large Order Win", "2026-06-02",
         "Bagged ₹15,000 Cr order for Middle East infra project", "Positive", "Long Term"),
        ("HDFC Bank", "Merger & Acquisition", "2026-05-29",
         "Acquires fintech NBFC for ₹3,200 Cr to expand lending", "Positive", "Long Term"),
        ("Reliance Industries", "Dividend", "2026-05-27",
         "Interim dividend of ₹10 per share approved", "Positive", "Short Term"),
        ("Wipro Ltd", "Buyback", "2026-05-25",
         "Buyback of ₹12,000 Cr at ₹600 per share", "Positive", "Short Term"),
        ("Zomato Ltd", "Large Order Win", "2026-05-22",
         "Strategic enterprise tie-up expanding B2B supply", "Positive", "Medium Term"),
        ("Bajaj Finserv", "Bonus Issue", "2026-05-20",
         "2:1 bonus issue recommended by the board", "Positive", "Medium Term"),
        ("IDFC First Bank", "QIP", "2026-05-18",
         "₹3,000 Cr QIP to strengthen capital adequacy", "Neutral", "Medium Term"),
        ("Suzlon Energy", "Stock Split", "2026-05-15",
         "Stock split from ₹2 to ₹1 face value", "Neutral", "Short Term"),
    ]
    df = pd.DataFrame(
        records,
        columns=[
            "Company Name",
            "Announcement Type",
            "Announcement Date",
            "Key Details",
            "Impact",
            "Time Horizon",
        ],
    )
    df["Announcement Date"] = pd.to_datetime(df["Announcement Date"])
    return df


# ---------------------------------------------------------------------------
# Tab 3: Results Tracker
# ---------------------------------------------------------------------------
def get_results_tracker() -> pd.DataFrame:
    """Sample quarterly results with growth metrics and a derived result score."""
    records = [
        ("Reliance Industries", 12.4, 18.6, 1.8, "Raised FY guidance", "Beat"),
        ("HDFC Bank", 9.1, 11.2, 0.6, "Maintained guidance", "In-Line"),
        ("Infosys Ltd", 6.3, 4.1, -0.4, "Lowered guidance", "Missed"),
        ("Tata Consultancy Services", 8.8, 10.5, 1.1, "Maintained guidance", "In-Line"),
        ("ICICI Bank", 14.2, 21.3, 1.4, "Raised guidance", "Beat"),
        ("Bharti Airtel", 11.5, 26.8, 2.2, "Raised guidance", "Beat"),
        ("Asian Paints", 3.2, -2.5, -1.1, "Cautious outlook", "Missed"),
        ("Maruti Suzuki", 10.1, 13.4, 0.9, "Maintained guidance", "In-Line"),
        ("Larsen & Toubro", 15.6, 19.2, 1.3, "Strong order book", "Beat"),
        ("Hindustan Unilever", 4.5, 5.0, 0.3, "Maintained guidance", "In-Line"),
        ("Tata Motors", 7.8, -8.4, -2.0, "Demand pressure flagged", "Missed"),
        ("Sun Pharma", 9.9, 12.1, 1.0, "Maintained guidance", "In-Line"),
    ]
    df = pd.DataFrame(
        records,
        columns=[
            "Company Name",
            "Revenue Growth %",
            "Profit Growth %",
            "Margin Change %",
            "Management Guidance",
            "Result Verdict",
        ],
    )
    # Derive a simple composite "Result Score" (0-100) from the metrics.
    score = (
        df["Revenue Growth %"] * 2.0
        + df["Profit Growth %"] * 2.5
        + df["Margin Change %"] * 6.0
        + 45
    ).clip(0, 100)
    df["Result Score"] = score.round(0).astype(int)
    return df
