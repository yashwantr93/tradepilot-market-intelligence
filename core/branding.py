"""
Branding / identity constants — single source of truth for the application name,
subtitle, and purpose. Imported by the UI and the report generators so naming
stays consistent everywhere. (Pure constants — no logic.)
"""

from __future__ import annotations

from pathlib import Path

APP_NAME = "TradePilot AI"
APP_SUBTITLE = "Market Intelligence Platform"
APP_FULL_NAME = f"{APP_NAME} — {APP_SUBTITLE}"
APP_SHORT = "TradePilot AI"
APP_DESCRIPTION = (
    "TradePilot AI is a Rule-Based Swing Trading Intelligence System "
    "for the Indian Stock Market."
)

# Brand asset locations (logo / favicon / app icon — see docs/BRAND_GUIDELINES.md).
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "brand"
LOGO_MARK_SVG = ASSETS_DIR / "logo-mark.svg"           # emblem only, theme-agnostic (vector)
LOGO_FULL_LIGHT_SVG = ASSETS_DIR / "logo-full-light.svg"   # dark wordmark, for light UI
LOGO_FULL_DARK_SVG = ASSETS_DIR / "logo-full-dark.svg"     # light wordmark, for dark UI
MARK_96 = ASSETS_DIR / "mark-96.png"                   # emblem raster, for in-app use (sidebar)
MARK_256 = ASSETS_DIR / "mark-256.png"
LOGO_FULL_LIGHT = ASSETS_DIR / "logo-full-light.png"
LOGO_FULL_DARK = ASSETS_DIR / "logo-full-dark.png"
APP_ICON_PNG = ASSETS_DIR / "app-icon-512.png"
FAVICON_PNG = ASSETS_DIR / "favicon-32.png"
FAVICON_ICO = ASSETS_DIR / "favicon.ico"

# Independent rule-based data sources the system combines.
DATA_SOURCES = [
    "Deal Flow",
    "Institutional Activity",
    "Sector Rotation",
    "Corporate Actions",
    "Quarterly Results",
    "Technical Confirmation",
]

# What the system is — and explicitly is NOT.
DISCLAIMERS = [
    "Not a prediction engine.",
    "Does not use AI scoring.",
    "Does not generate buy/sell recommendations.",
    "A research and opportunity-discovery system.",
]

PURPOSE = (
    f"{APP_NAME} is designed to identify high-quality swing trading opportunities "
    "(approximately 1–8 weeks) using multiple independent rule-based data sources "
    "including:\n"
    "• Deal Flow\n• Institutional Activity\n• Sector Rotation\n• Corporate Actions\n"
    "• Quarterly Results\n• Technical Confirmation\n\n"
    "It is not a prediction engine.\n"
    "It does not use AI scoring.\n"
    "It does not generate buy/sell recommendations.\n"
    "It is a research and opportunity-discovery system."
)

# One-line banner reused under report titles and dashboard headers.
TAGLINE = "Rule-based swing-trade research · ~1–8 week horizon · no AI / no scoring / no buy-sell calls"
