"""
Reusable UI components and shared styling helpers.

Keeping presentation helpers here means every page renders KPI cards, section
headers and Plotly charts with a single, consistent institutional look.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# Shared color palette (works on both light and dark themes).
COLORS = {
    "positive": "#16a34a",
    "negative": "#dc2626",
    "neutral": "#ca8a04",
    "accent": "#2563eb",
    "muted": "#64748b",
    "grid": "rgba(128,128,128,0.15)",
}

# Plotly template that adapts to Streamlit's dark/light theme.
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=40, b=10),
    font=dict(family="Inter, Segoe UI, sans-serif", size=13),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def inject_global_css() -> None:
    """Inject CSS for the institutional card / layout styling."""
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
        /* KPI card — explicit dark-theme colours for high contrast */
        .kpi-card {
            background: #161b26;
            border: 1px solid rgba(148,163,184,0.18);
            border-left: 4px solid #2563eb;
            border-radius: 12px;
            padding: 14px 16px 16px 16px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.25);
            height: 100%;
        }
        .kpi-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #94a3b8;
            margin-bottom: 6px;
            font-weight: 700;
        }
        .kpi-value {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.0;
            color: #f8fafc;
        }
        .kpi-help {color: #64748b; font-size: 0.8rem; margin-left: 5px; cursor: help;}
        .kpi-delta {font-size: 0.82rem; font-weight: 600; margin-top: 6px;}
        .delta-up {color: #22c55e;}
        .delta-down {color: #f87171;}
        .delta-flat {color: #94a3b8;}
        /* Section header */
        .section-header {
            font-size: 1.15rem;
            font-weight: 700;
            margin: 14px 0 4px 0;
            padding-bottom: 6px;
            border-bottom: 2px solid rgba(37,99,235,0.45);
        }
        .pill {
            display: inline-block;
            padding: 3px 12px;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 700;
            color: #fff;
        }
        .badge {
            display: inline-block;
            padding: 3px 10px;
            margin: 2px 6px 2px 0;
            border-radius: 8px;
            font-size: 0.78rem;
            font-weight: 700;
            border: 1px solid transparent;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_ACCENT = {"up": "#22c55e", "down": "#f87171", "flat": "#2563eb"}


def kpi_card(label: str, value: str, delta: str | None = None,
             delta_dir: str = "flat", help: str | None = None) -> None:
    """Render a high-contrast KPI card (dark-theme optimized).

    delta_dir: "up" | "down" | "flat" — sets the accent border and delta color.
    help: optional hover tooltip explaining the metric.
    """
    accent = _ACCENT.get(delta_dir, "#2563eb")
    delta_html = ""
    if delta is not None:
        arrow = {"up": "▲", "down": "▼", "flat": ""}.get(delta_dir, "")
        delta_html = f'<div class="kpi-delta delta-{delta_dir}">{arrow} {delta}</div>'
    hint = ""
    if help:
        safe = help.replace('"', "&quot;")
        hint = f'<span class="kpi-help" title="{safe}">&#9432;</span>'
    st.markdown(
        f"""
        <div class="kpi-card" style="border-left-color:{accent};">
            <div class="kpi-label">{label}{hint}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# Consistent, plain-English help text reused as column tooltips across pages.
COLUMN_HELP = {
    "Priority": "A = strictest setup (open first) · B = solid · C = weaker / needs work. Rule-based, not a score.",
    "Action": "Ready = clean near-breakout setup · Research = validate first · Watch = monitor · Avoid = weak.",
    "Setup": "Stars: Strong Sector · Strong RS · Above 20 SMA · Near Breakout · Strong Results (max 5). Display only — never affects ranking.",
    "Breakout": "Distance to 52-week high: 🟢 Near ≤5% · 🟡 Building ≤15% · ⚪ Far >15%.",
    "Results": "Latest quarter vs a year ago: Strong (rev & profit ≥15%) / Neutral / Weak (any decline).",
    "Corp Action": "Most material recent corporate announcement and its rule-based impact (▲ bullish / ■ neutral / ▼ bearish).",
    "Do Now": "Rule-based directive: Open chart now / Wait for breakout / Wait for pullback / Review earnings first / Ignore for now.",
    "Rel. Str": "Relative strength vs Nifty over ~50 sessions: Strong / Neutral / Weak.",
    "Rel. Strength": "Relative strength vs Nifty over ~50 sessions: Strong / Neutral / Weak.",
    "Above 20 SMA": "Is the price above its 20-day simple moving average (short-term uptrend)?",
    "52W High ↓%": "How far below the 52-week high the price is (smaller = closer to breakout).",
    "↓ High %": "Distance below the 52-week high (%).",
    "↑ Low %": "Distance above the 52-week low (%).",
    "Sector Trend": "Rule-based sector rotation status: Strong / Improving / Neutral / Weak.",
}


# Color sets for status badges (text, background, border) on dark theme.
_BADGE_STYLES = {
    "green": ("#bbf7d0", "rgba(34,197,94,0.16)", "rgba(34,197,94,0.45)"),
    "amber": ("#fde68a", "rgba(202,138,4,0.16)", "rgba(202,138,4,0.45)"),
    "red": ("#fecaca", "rgba(239,68,68,0.16)", "rgba(239,68,68,0.45)"),
    "blue": ("#bfdbfe", "rgba(37,99,235,0.16)", "rgba(37,99,235,0.45)"),
    "gray": ("#cbd5e1", "rgba(148,163,184,0.14)", "rgba(148,163,184,0.4)"),
}


def badge(text: str, kind: str = "gray") -> str:
    """Return an inline HTML badge string (use inside st.markdown)."""
    fg, bg, br = _BADGE_STYLES.get(kind, _BADGE_STYLES["gray"])
    return (f'<span class="badge" style="color:{fg};background:{bg};'
            f'border-color:{br};">{text}</span>')


def badges_row(items: list[tuple[str, str]]) -> None:
    """Render a row of badges from (text, kind) tuples."""
    html = "".join(badge(t, k) for t, k in items)
    st.markdown(html, unsafe_allow_html=True)


def section_header(title: str) -> None:
    """Render a consistent section header."""
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def style_fig(fig: go.Figure, height: int = 320, title: str | None = None) -> go.Figure:
    """Apply the shared Plotly layout to a figure."""
    fig.update_layout(**PLOTLY_LAYOUT, height=height)
    if title:
        fig.update_layout(title=dict(text=title, x=0.0, font=dict(size=15)))
    fig.update_xaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=COLORS["grid"], zeroline=False)
    return fig
