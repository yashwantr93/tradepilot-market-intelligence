# TradePilot AI — Brand Guidelines
### Market Intelligence Platform

---

## 1. Brand Name & Positioning

| | |
|---|---|
| **Full name** | TradePilot AI — Market Intelligence Platform |
| **Short name** | TradePilot AI |
| **Category** | Rule-Based Swing Trading Intelligence System for the Indian Stock Market |

**A note on "AI" in the name.** This is a product-naming choice, not a methodology claim. The platform's guarantee — stated on every relevant page and in the README — is that it uses **zero machine learning or AI scoring**; every priority, action, and label is a transparent, deterministic rule. If this naming tension is a concern, the recommended resolution is to keep "AI" as a brand identifier (common in fintech naming) while every in-product disclaimer continues to clarify "no AI scoring" — the two coexist as **name** vs. **method**, and should not be conflated in copy.

### Elevator pitch
> TradePilot AI identifies high-quality swing trading opportunities (~1–8 weeks) across the Indian market by combining six independent rule-based signal sources — Deal Flow, Institutional Activity, Sector Rotation, Corporate Actions, Quarterly Results, and Technical Confirmation — into one daily, fully-explainable research workflow. It is a research and opportunity-discovery system, not a prediction engine.

---

## 2. Logo System

### 2.1 The mark

The emblem is a circular orbit (steady, systematic monitoring) with a green growth arc sweeping into an upward arrow (momentum/trend detection), framing three ascending candlesticks that resolve green (the confirmed setup).

| Element | Meaning |
|---|---|
| Blue ring | Continuous, systematic market monitoring |
| Green growth arc + arrow | Momentum, trend detection, the "pilot" guiding through data |
| Three ascending candlesticks | Price action; the story rises left→right, ending in a bullish (green) close |

### 2.2 Files delivered

```
assets/brand/
├── logo-mark.svg            emblem only, vector, transparent — theme-agnostic
├── logo-full-light.svg      icon + wordmark, dark text — for light surfaces
├── logo-full-dark.svg       icon + wordmark, light text — for dark surfaces
├── logo-full-light.png      1:1 raster of the above (640x160, transparent)
├── logo-full-dark.png       1:1 raster of the above (640x160, transparent)
├── mark-96.png              emblem raster, transparent — in-app use (sidebar)
├── mark-256.png             emblem raster, transparent — higher-res use
├── app-icon-512.png         emblem on a filled navy rounded-square plate (512x512)
├── favicon-32.png           simplified emblem on a filled navy plate (32x32)
└── favicon.ico              multi-resolution favicon (16 / 32 / 48 px)
```

### 2.3 Why the favicon is a *different* drawing, not a scaled copy

The full mark (three candles, thin wicks, fine arrow) turns to mush below ~48px. `favicon.ico` / `favicon-32.png` use a **deliberately simplified** composition — two bold candles, a thicker two-tone ring, a solid arrowhead with no shaft — designed to hold up at 16px. This is standard icon-design practice: don't scale the detailed mark down, redraw a simpler one for small sizes.

### 2.4 Why the favicon/app-icon have a fixed plate, not two light/dark variants

The mark's own colors (blue/green) are vivid enough to read on both light and dark UI *when used inline* — that's why `logo-mark.svg` and the two full-logo variants share the same icon colors and only swap wordmark text color. But a favicon sits in a browser tab whose chrome color is unpredictable and not swappable at runtime by this app. So the favicon/app-icon are given a **fixed navy plate** (`#0B1220`) behind the mark — guaranteeing contrast regardless of the viewer's OS/browser theme, rather than shipping two favicons that only one of which would ever actually get used correctly.

### 2.5 Usage rules

- **Minimum size:** mark not smaller than 24px inline; full logo not narrower than 160px.
- **Clear space:** keep at least half the ring's diameter as empty margin on all sides.
- **Do not** recolor the ring/arc/candles outside the defined palette.
- **Do not** stretch non-uniformly — scale width and height together.
- **Do not** place the light-text full logo on a light background, or vice versa — use `logo-full-light` on light surfaces and `logo-full-dark` on dark surfaces.
- On a **transparent or unknown background**, prefer `logo-mark.svg` alone, or the app-icon's plated version.

---

## 3. Color Palette

The palette is **not new** — it formalizes colors already active in the product's CSS (`components.py`), so adopting these guidelines requires no re-theming.

### 3.1 Brand colors

| Token | Hex | Usage |
|---|---|---|
| **Primary Blue** | `#2563EB` | Ring, primary accent, links, "flat/neutral" KPI border |
| **Growth Green** | `#22C55E` | Growth arc, arrow, "AI" in wordmark, positive/up accent |
| **Deep Green** | `#16A34A` | Positive semantic color in charts/badges (darker, for small text/fills) |
| **Slate** | `#64748B` | Candle 1 (mark), muted text, subtitle on light backgrounds |
| **Ink Navy** | `#0B1220` | Favicon/app-icon plate; conceptual "brand dark" |

### 3.2 Semantic colors (existing, unchanged)

| Token | Hex | Usage |
|---|---|---|
| Negative | `#DC2626` | Down/bearish/avoid states |
| Neutral | `#CA8A04` | Amber — "Research" / caution states |
| Grid | `rgba(128,128,128,0.15)` | Chart gridlines |

### 3.3 Dark-mode surface tokens (existing, unchanged)

| Token | Hex | Usage |
|---|---|---|
| Card surface | `#161B26` | KPI card background |
| Card border | `rgba(148,163,184,0.18)` | KPI card border |
| Text (primary, dark bg) | `#F8FAFC` | KPI values, headings |
| Text (muted, dark bg) | `#94A3B8` | Labels, captions, subtitle |

### 3.4 Light-mode wordmark tokens

| Token | Hex | Usage |
|---|---|---|
| Text (primary, light bg) | `#0F172A` | Wordmark on light backgrounds |
| Text (muted, light bg) | `#64748B` | Subtitle on light backgrounds |

---

## 4. Typography

| Role | Font stack | Notes |
|---|---|---|
| UI / body (in-app) | `Inter, "Segoe UI", Arial, sans-serif` | Already the active stack in `components.py`'s Plotly layout; system-safe, no custom font loading required in Streamlit |
| Logo wordmark | Segoe UI Bold (rendered), Inter-equivalent intent | The PNG lockups are rendered with Segoe UI Bold (available on Windows) as a faithful system-font stand-in for Inter Bold; if Inter is later bundled as a real webfont, re-render `scripts/generate_brand_assets.py` with it for a closer match |
| Subtitle / eyebrow text | Same stack, +3px letter-spacing, uppercase | "MARKET INTELLIGENCE PLATFORM" treatment |

**Why not a custom webfont in the app itself:** Streamlit doesn't cleanly support bundling custom `@font-face` files without injecting raw HTML into the page head, which adds fragility for a cosmetic gain. The existing system-font stack (Inter where installed, Segoe UI/Arial fallback) is the practical, low-risk choice and is what's already deployed.

---

## 5. UI Theme

The dashboard's dark theme (already implemented in `components.py`) is the canonical UI theme:

- **KPI cards:** dark surface (`#161B26`), left accent border in Primary Blue / Growth Green / Negative Red depending on direction, bright white value text (`#F8FAFC`), muted uppercase label (`#94A3B8`).
- **Section headers:** bold text with a Primary-Blue-tinted bottom border.
- **Badges:** rounded pill, tinted background + matching border in green/amber/red/blue/gray families — the same families used for Priority (A/B/C), Action (Ready/Research/Watch/Avoid), and freshness indicators.
- **Charts:** transparent backgrounds so they inherit the surface color; gridlines at low-opacity gray; brand blue/green/red for series color where applicable.

No changes are required to `components.py` for this rebrand — the existing tokens *are* the brand palette (see §3), which is why this rebrand shipped with zero visual-regression risk to the working dashboard.

---

## 6. Where the brand appears

| Surface | Element |
|---|---|
| Browser tab | `favicon.ico` / `favicon-32.png` (page icon), tab title = "TradePilot AI — Market Intelligence Platform" |
| Sidebar | `mark-96.png` + "TradePilot AI" + "Market Intelligence Platform" caption |
| About panel | Full name + purpose + data sources + disclaimers |
| Footer | "© 2026 TradePilot AI — Market Intelligence Platform" |
| README | Full logo lockup (light/dark GitHub-aware), name, purpose |
| Reports (generated .md/.csv) | `core/branding.py`'s `APP_NAME`/`TAGLINE` banner under every report title (via `core/reports.py`) |
| Daily run CLI | `run_daily.py` banner |

All of the above read from **`core/branding.py`** — the single source of truth for the name, subtitle, and asset paths. Changing the brand again means editing that one file (plus re-running `scripts/generate_brand_assets.py` if the mark itself changes).

---

## 7. Regenerating assets

```bash
python scripts/generate_brand_assets.py
```

Rewrites all PNG/ICO files from the geometry defined in the script (which mirrors `logo-mark.svg`'s coordinates 1:1). Edit the SVGs and the script together if the mark design changes, so vector and raster stay in sync.
