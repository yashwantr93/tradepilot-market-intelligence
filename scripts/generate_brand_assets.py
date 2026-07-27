"""
Generates TradePilot AI raster brand assets (PNG + ICO) from hand-specified
geometry that mirrors assets/brand/logo-mark.svg exactly (same coordinates,
same colors) so the SVG and PNG renditions are visually identical.

Run manually whenever the mark design changes:
    python scripts/generate_brand_assets.py

Outputs (under assets/brand/):
    mark-96.png          transparent, for in-app use (sidebar, About page)
    mark-256.png         transparent, higher-res mark
    app-icon-512.png     filled rounded-square plate, 512x512 app icon
    favicon-32.png        filled rounded-square plate, 32x32 favicon
    favicon.ico            multi-resolution icon (16/32/48)
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "brand"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

BLUE = (37, 99, 235, 255)      # #2563EB
GREEN = (34, 197, 94, 255)     # #22C55E
SLATE = (100, 116, 139, 255)   # #64748B
NAVY = (11, 18, 32, 255)       # #0B1220 — brand ink, used as the icon plate
INK = (15, 23, 42, 255)        # #0F172A — wordmark on light backgrounds
WHITE = (248, 250, 252, 255)   # #F8FAFC — wordmark on dark backgrounds
SLATE_LIGHT = (100, 116, 139, 255)   # #64748B — subtitle on light backgrounds
SLATE_DARK = (148, 163, 184, 255)    # #94A3B8 — subtitle on dark backgrounds
BLUE_BRIGHT = (59, 130, 246, 255)    # #3B82F6 — candle 2 on dark backgrounds

_FONT_DIR = Path(r"C:\Windows\Fonts")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_FONT_DIR / name), size)

# Base design canvas the geometry below is expressed in (512x512), matching
# logo-mark.svg 1:1. Rendered at higher supersampling then downscaled for
# clean anti-aliasing at small target sizes.
BASE = 512
SS = 4  # supersample factor


def _pt(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def draw_mark(size: int, *, transparent: bool = True, plate: bool = False) -> Image.Image:
    """Draw the TradePilot AI emblem at `size`x`size` pixels."""
    canvas = size * SS
    scale = canvas / BASE
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if plate:
        # Filled rounded-square plate so the icon is legible on any tab/home-
        # screen background (deliberate fixed-contrast choice — see brand docs).
        pad = int(18 * scale)
        radius = int(96 * scale)
        d.rounded_rectangle([pad, pad, canvas - pad, canvas - pad], radius=radius, fill=NAVY)

    def S(v: float) -> float:
        return v * scale

    cx, cy, r = S(256), S(256), S(215)
    ring_w = S(23)

    # Outer ring (blue)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLUE, width=int(ring_w))

    # Growth arc (green) — bottom-left -> bottom -> upper-right, matches the
    # SVG's 140deg -> -20deg sweep in the same (x-right, y-down) angle system.
    bbox = [cx - r, cy - r, cx + r, cy + r]
    d.arc(bbox, start=-20, end=140, fill=GREEN, width=int(ring_w))
    # Pillow's arc() draws start->end increasing angle; round the caps by
    # stamping small filled circles at both ends (arc() has no linecap option).
    for a in (-20, 140):
        px, py = _pt(cx, cy, r, a)
        rr = ring_w / 2
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=GREEN)

    # Candlesticks — ascending left -> right
    candles = [
        (S(174), S(220), S(348), S(151), S(246), S(197), S(328), SLATE),   # x, wick_y1, wick_y2, body L, body T, body R, body B, color
        (S(256), S(179), S(348), S(233), S(205), S(279), S(328), BLUE),
        (S(338), S(128), S(348), S(315), S(154), S(361), S(328), GREEN),
    ]
    wick_w = S(9)
    for x, wy1, wy2, bl, bt, br, bb, color in candles:
        d.line([x, wy1, x, wy2], fill=color, width=int(wick_w))
        rr = wick_w / 2
        d.ellipse([x - rr, wy1 - rr, x + rr, wy1 + rr], fill=color)
        d.ellipse([x - rr, wy2 - rr, x + rr, wy2 + rr], fill=color)
        radius = S(6)
        d.rounded_rectangle([bl, bt, br, bb], radius=radius, fill=color)

    # Upward trend arrow (green), continuing the growth arc
    shaft_w = S(14)
    d.line([S(409.6), S(138.4), S(428), S(120)], fill=GREEN, width=int(shaft_w))
    for px, py in ((S(409.6), S(138.4)), (S(428), S(120))):
        rr = shaft_w / 2
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=GREEN)
    d.polygon([(S(452), S(96)), (S(442.1), S(134.1)), (S(413.9), S(105.9))], fill=GREEN)

    return img.resize((size, size), Image.LANCZOS)


def draw_favicon(size: int) -> Image.Image:
    """Simplified mark for tiny sizes (16-48px) — 2 bold candles, thick ring,
    bold chevron, no thin wick nubs. The full 3-candle mark turns to mush this
    small, so this is a deliberately reduced composition, not a scaled-down copy.
    """
    canvas = size * SS
    scale = canvas / BASE
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = int(14 * scale)
    radius = int(110 * scale)
    d.rounded_rectangle([pad, pad, canvas - pad, canvas - pad], radius=radius, fill=NAVY)

    def S(v: float) -> float:
        return v * scale

    cx, cy, r = S(256), S(256), S(190)
    ring_w = S(40)
    bbox = [cx - r, cy - r, cx + r, cy + r]
    d.arc(bbox, start=120, end=340, fill=BLUE, width=int(ring_w))
    d.arc(bbox, start=-20, end=120, fill=GREEN, width=int(ring_w))
    # Round the two seams (120 deg, and the -20/340 wrap-around point) so the
    # two-tone ring reads as one continuous stroke rather than two flat-capped bars.
    rr = ring_w / 2
    for angle, color in ((120, BLUE), (340, GREEN)):
        px, py = _pt(cx, cy, r, angle)
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=color)

    # Two bold candles only.
    body_w = S(64)
    d.rounded_rectangle([S(196), S(210), S(196) + body_w, S(340)], radius=S(10), fill=BLUE)
    d.rounded_rectangle([S(292), S(150), S(292) + body_w, S(340)], radius=S(10), fill=GREEN)

    # Bold arrowhead, no shaft (reads cleanly at tiny sizes).
    d.polygon([(S(430), S(78)), (S(414), S(140)), (S(372), S(122))], fill=GREEN)

    return img.resize((size, size), Image.LANCZOS)


def draw_full_logo(*, dark_bg: bool) -> Image.Image:
    """Horizontal lockup (icon + wordmark + subtitle), matching the SVG 1:1.

    dark_bg=True  -> light wordmark, for placement on dark surfaces.
    dark_bg=False -> dark wordmark, for placement on light surfaces.
    """
    W, H = 640 * SS, 160 * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    scale = SS  # 1 logical px -> SS supersampled px

    icon_scale = (140 / BASE) * scale
    ox, oy = 10 * scale, 10 * scale

    def P(x: float, y: float) -> tuple[float, float]:
        return ox + x * icon_scale, oy + y * icon_scale

    candle1_color = SLATE_DARK if dark_bg else SLATE
    candle2_color = BLUE_BRIGHT if dark_bg else BLUE

    cx, cy, r = P(256, 256)[0], P(256, 256)[1], 215 * icon_scale
    ring_w = 23 * icon_scale
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=BLUE, width=int(ring_w))
    bbox = [cx - r, cy - r, cx + r, cy + r]
    d.arc(bbox, start=-20, end=140, fill=GREEN, width=int(ring_w))
    for a in (-20, 140):
        px, py = _pt(cx, cy, r, a)
        rr = ring_w / 2
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=GREEN)

    candles = [
        (174, 220, 348, 151, 246, 197, 328, candle1_color),
        (256, 179, 348, 233, 205, 279, 328, candle2_color),
        (338, 128, 348, 315, 154, 361, 328, GREEN),
    ]
    wick_w = 9 * icon_scale
    for x, wy1, wy2, bl, bt, br, bb, color in candles:
        x0, y1 = P(x, wy1)
        _, y2 = P(x, wy2)
        d.line([x0, y1, x0, y2], fill=color, width=int(wick_w))
        rr = wick_w / 2
        d.ellipse([x0 - rr, y1 - rr, x0 + rr, y1 + rr], fill=color)
        d.ellipse([x0 - rr, y2 - rr, x0 + rr, y2 + rr], fill=color)
        blx, bty = P(bl, bt)
        brx, bby = P(br, bb)
        d.rounded_rectangle([blx, bty, brx, bby], radius=6 * icon_scale, fill=color)

    shaft_w = 14 * icon_scale
    sx1, sy1 = P(409.6, 138.4)
    sx2, sy2 = P(428, 120)
    d.line([sx1, sy1, sx2, sy2], fill=GREEN, width=int(shaft_w))
    for px, py in ((sx1, sy1), (sx2, sy2)):
        rr = shaft_w / 2
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=GREEN)
    tri = [P(452, 96), P(442.1, 134.1), P(413.9, 105.9)]
    d.polygon(tri, fill=GREEN)

    # Wordmark
    main_color = WHITE if dark_bg else INK
    sub_color = SLATE_DARK if dark_bg else SLATE_LIGHT
    f_main = _font("segoeuib.ttf", 44 * scale)
    f_sub = _font("segoeuib.ttf", 15 * scale)

    tx, ty = 176 * scale, 42 * scale
    d.text((tx, ty), "TradePilot", font=f_main, fill=main_color)
    w_main = d.textlength("TradePilot", font=f_main)
    d.text((tx + w_main + 10 * scale, ty), "AI", font=f_main, fill=GREEN)

    sub_text = "M A R K E T   I N T E L L I G E N C E   P L A T F O R M"
    d.text((178 * scale, 100 * scale), sub_text, font=f_sub, fill=sub_color)

    return img.resize((640, 160), Image.LANCZOS)


def main() -> None:
    draw_mark(96, plate=False).save(ASSETS_DIR / "mark-96.png")
    draw_mark(256, plate=False).save(ASSETS_DIR / "mark-256.png")
    draw_mark(512, plate=True).save(ASSETS_DIR / "app-icon-512.png")

    draw_favicon(32).save(ASSETS_DIR / "favicon-32.png")

    icon_sizes = [16, 32, 48]
    imgs = [draw_favicon(s) for s in icon_sizes]
    imgs[0].save(ASSETS_DIR / "favicon.ico", format="ICO",
                sizes=[(s, s) for s in icon_sizes])

    draw_full_logo(dark_bg=False).save(ASSETS_DIR / "logo-full-light.png")
    draw_full_logo(dark_bg=True).save(ASSETS_DIR / "logo-full-dark.png")

    print("Wrote:", *[p.name for p in ASSETS_DIR.glob("*.png")],
          "favicon.ico", sep="\n  - ")


if __name__ == "__main__":
    main()
