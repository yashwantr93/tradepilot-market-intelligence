![TradePilot AI](assets/brand/logo-full-light.png#gh-light-mode-only)
![TradePilot AI](assets/brand/logo-full-dark.png#gh-dark-mode-only)

# TradePilot AI — Market Intelligence Platform

**Rule-Based Swing Trading Intelligence System for the Indian Stock Market**

> **A note on the name:** "AI" here is part of the product name, not a claim about
> methodology. Per the Guarantees below, TradePilot AI uses **zero machine learning
> or AI scoring** — every output is a transparent, deterministic rule. See
> [docs/BRAND_GUIDELINES.md](docs/BRAND_GUIDELINES.md) for the full brand system.

---

## Purpose

This platform is designed to identify high-quality swing trading opportunities
(approximately **1–8 weeks**) using multiple **independent rule-based data sources**
including:

- **Deal Flow** — bulk & block deals (NSE)
- **Institutional Activity** — FII/DII flows
- **Sector Rotation** — relative strength of NSE sectors
- **Corporate Actions** — buybacks, bonuses, order wins, M&A, results, etc.
- **Quarterly Results** — YoY revenue / profit / margin classification
- **Technical Confirmation** — price, 20-SMA, 52-week range, breakout distance

> It is **not** a prediction engine.
> It does **not** use AI scoring.
> It does **not** generate buy/sell recommendations.
> It is a **research and opportunity-discovery system**.

Everything is **deterministic, transparent, and fully explainable** — every stock
on the list can tell you exactly which rules it satisfied and why.

---

## How a trader uses it (under 2 minutes)

```
Morning Dashboard
   ↓
Today's Focus  (3–5 highest-conviction research candidates)
   ↓
Open those 3–5 charts
   ↓
Apply your own strategy
   (Price Action + Fibonacci + 20 SMA + Volume + RSI + Bollinger Bands)
   ↓
Take the trade only if the setup is confirmed.
```

The dashboard discovers and explains candidates. **You** make the trading decision.

---

## Architecture

```
Connectors → Processing → Database (SQLite) → Contracts → Dashboard (read-only)
```

- **Connectors** — fetch real data (NSE archive CSVs, yfinance).
- **Processing** — shared rule-based logic (technicals, classifiers).
- **Database** — local SQLite store (`data_store/market.db`).
- **Contracts** — the only read bridge to the UI (`data/contracts.py`).
- **Dashboard** — Streamlit pages, strictly read-only (no calculation in the UI).

---

## Running it

```bash
pip install -r requirements.txt

# 1) Refresh the data (engine pipelines — run these in the morning):
python run_live.py            # Deal Flow (bulk/block deals + technicals)
python run_institutional.py   # FII/DII + Sector Rotation
python run_corp_actions.py    # Corporate Actions
python run_results.py          # Quarterly Results
python run_combined.py         # Confluence (tiered combined watchlist)
python run_validation.py       # Signal validation (forward returns)

# 2) Open the dashboard:
streamlit run app.py
```

The dashboard always reads whatever the pipelines last wrote — re-run a pipeline
and reload the page to refresh.

---

## Dashboard pages

| Page | What it shows |
|---|---|
| 🎯 **Daily Opportunity Hub** | Today's Focus + tiered Priority A/B/C — start here |
| 🧩 Combined Watchlist | Tier 1/2/3 confluence of Deal Flow + Institutional |
| 📈 Deal Flow Watchlist | Bulk/block-deal candidates with technicals |
| 🏦 Institutional Watchlist | FII/DII flows + sector rotation + leaders |
| 🏛️ Corporate Actions | Classified announcements by priority/impact |
| 📊 Results Watchlist | Quarterly results: Strong / Neutral / Weak |
| ✅ Validation Dashboard | How each engine's past signals performed |

---

## Deploying

This README covers local development. For deploying to Render (persistent
disk, environment variables, scheduling), see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Guarantees

- **No AI. No ML. No probabilistic scoring. No hidden ranking.**
- Every priority, action, and star is a transparent if/else rule.
- The UI is read-only; all logic lives in the backend.

`docs/` contains the historical phase-by-phase design specifications.
