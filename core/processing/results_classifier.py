"""
Rule-based quarterly-results classifier.

From a quarterly income statement it computes YoY revenue growth, profit growth
and net-margin change, then classifies Strong / Neutral / Weak by transparent
thresholds. No scoring, no ML, no prediction.

Classification rules
--------------------
  STRONG  : revenue growth >= 15%  AND profit growth >= 15%
  WEAK    : revenue growth < 0%    OR  profit growth < 0%   (any contraction)
  NEUTRAL : everything in between
(Margin change is reported alongside as supporting context.)
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from core.config import RESULTS as R


def quarter_label(period_end: dt.date) -> str:
    """Map an Indian fiscal quarter-end to a label, e.g. 2026-03-31 -> 'Q4 FY26'."""
    m, y = period_end.month, period_end.year
    if m == 3:
        return f"Q4 FY{str(y)[-2:]}"
    if m == 6:
        return f"Q1 FY{str(y + 1)[-2:]}"
    if m == 9:
        return f"Q2 FY{str(y + 1)[-2:]}"
    if m == 12:
        return f"Q3 FY{str(y + 1)[-2:]}"
    return f"{period_end.isoformat()}"


def _growth(latest: float, prior: float) -> float | None:
    """YoY growth %. Returns None when the prior base is a loss/zero (a % growth
    off a negative base is not meaningful — flagged as None and shown as '-')."""
    if prior is None or latest is None or prior <= 0:
        return None
    return round((latest / prior - 1) * 100, 2)


def compute_metrics(income_stmt: pd.DataFrame) -> dict | None:
    """Compute growth/margin metrics from a yfinance quarterly income statement.

    Columns are period-end dates (newest first). Needs 'Total Revenue' and
    'Net Income' and at least (yoy_quarters_back + 1) quarters for YoY.
    """
    if income_stmt is None or income_stmt.empty:
        return None
    if "Total Revenue" not in income_stmt.index or "Net Income" not in income_stmt.index:
        return None

    cols = list(income_stmt.columns)
    n_back = R["yoy_quarters_back"]
    if len(cols) > n_back:
        latest_i, prior_i, basis = 0, n_back, "YoY"
    elif len(cols) >= 2:
        latest_i, prior_i, basis = 0, 1, "QoQ"  # fallback when <5 quarters
    else:
        return None

    def val(row, i):
        v = income_stmt.loc[row, cols[i]]
        return float(v) if pd.notna(v) else None

    rev_l, rev_p = val("Total Revenue", latest_i), val("Total Revenue", prior_i)
    np_l, np_p = val("Net Income", latest_i), val("Net Income", prior_i)
    if None in (rev_l, rev_p, np_l, np_p) or rev_l == 0 or rev_p == 0:
        return None

    rev_g = _growth(rev_l, rev_p)
    prof_g = _growth(np_l, np_p)
    margin_l = np_l / rev_l * 100
    margin_p = np_p / rev_p * 100
    margin_change = round(margin_l - margin_p, 2)

    period_end = pd.to_datetime(cols[latest_i]).date()
    return {
        "period_end": period_end,
        "quarter": quarter_label(period_end),
        "revenue_growth_pct": rev_g,
        "profit_growth_pct": prof_g,
        "margin_change_pct": margin_change,
        "basis": basis,
    }


def compute_all_metrics(income_stmt: pd.DataFrame) -> list[dict]:
    """Phase 1 — retain the FULL fetched history, not just the latest quarter.

    `compute_metrics()` above (unchanged, still used nowhere in this module's
    own logic) only ever looks at column 0 (latest) vs column `n_back`
    (same-quarter-prior-year). Every other column yfinance returns was being
    fetched and then silently discarded. This function walks every column and
    returns one dict per quarter:
      - raw revenue_actual / profit_actual / margin_pct for ALL quarters
        (basis="Raw" when no same-fetch YoY comparator exists for that
        column), so nothing fetched is thrown away, and
      - the full YoY growth/margin-change metrics (basis="YoY") for any
        column that DOES have a same-fetch comparator `n_back` columns later.

    Newest quarter first (mirrors the income statement's own column order).
    """
    if income_stmt is None or income_stmt.empty:
        return []
    if "Total Revenue" not in income_stmt.index or "Net Income" not in income_stmt.index:
        return []

    cols = list(income_stmt.columns)
    n_back = R["yoy_quarters_back"]

    def val(i: int) -> tuple[float | None, float | None]:
        rev = income_stmt.loc["Total Revenue", cols[i]]
        ni = income_stmt.loc["Net Income", cols[i]]
        rev = float(rev) if pd.notna(rev) else None
        ni = float(ni) if pd.notna(ni) else None
        return rev, ni

    out: list[dict] = []
    for i in range(len(cols)):
        rev_l, np_l = val(i)
        if rev_l is None or np_l is None or rev_l == 0:
            continue  # can't even report a raw margin for this quarter — skip it
        period_end = pd.to_datetime(cols[i]).date()
        margin_l = np_l / rev_l * 100

        row = {
            "period_end": period_end,
            "quarter": quarter_label(period_end),
            "revenue_actual": rev_l,
            "profit_actual": np_l,
            "margin_pct": round(margin_l, 2),
            "revenue_growth_pct": None,
            "profit_growth_pct": None,
            "margin_change_pct": None,
            "basis": "Raw",
        }

        # A YoY comparator exists only if a column `n_back` further out is
        # present AND itself has usable Revenue/Net Income.
        prior_i = i + n_back
        if prior_i < len(cols):
            rev_p, np_p = val(prior_i)
            if rev_p is not None and np_p is not None and rev_p != 0:
                rev_g = _growth(rev_l, rev_p)
                prof_g = _growth(np_l, np_p)
                margin_p = np_p / rev_p * 100
                row.update({
                    "revenue_growth_pct": rev_g,
                    "profit_growth_pct": prof_g,
                    "margin_change_pct": round(margin_l - margin_p, 2),
                    "basis": "YoY",
                })
        out.append(row)
    return out


def classify(rev_g: float | None, prof_g: float | None) -> str:
    if rev_g is None or prof_g is None:
        return "Neutral"
    if rev_g >= R["strong_growth_pct"] and prof_g >= R["strong_growth_pct"]:
        return "Strong"
    if rev_g < R["weak_decline_pct"] or prof_g < R["weak_decline_pct"]:
        return "Weak"
    return "Neutral"
