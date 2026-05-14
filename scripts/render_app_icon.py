#!/usr/bin/env python3
"""Render the HealthGraphSync iOS app icon.

Combines:
  - A radial "Aura" gradient background (deep purple → magenta → pink → orange)
    that echoes the Neo4j Aura brand identity.
  - A clean white heart silhouette (Apple Health cue) centered on the canvas.
  - Six graph "nodes" positioned around the heart, connected to a hub node at
    the heart's geometric center — evoking a property graph of health metrics.

Outputs:
  ios/HealthGraphSync/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png
  docs/app-icon-1024.png            (mirror for the README / PR previews)

iOS 14+ accepts a single 1024×1024 PNG and derives the other sizes at build
time, so we only ship one asset.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
OUT_ICON = Path(__file__).resolve().parent.parent / (
    "ios/HealthGraphSync/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png"
)
OUT_DOC = Path(__file__).resolve().parent.parent / "docs/app-icon-1024.png"


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def radial_gradient(size: int) -> Image.Image:
    """Aura-inspired radial gradient: deep indigo center → magenta → coral edge."""
    img = Image.new("RGB", (size, size), (0, 0, 0))
    px = img.load()
    cx, cy = size / 2, size / 2
    max_r = math.hypot(cx, cy)

    # Aura-ish brand stops (indigo → magenta → coral → soft amber on the rim)
    stops = [
        (0.00, (28, 22, 66)),     # deep indigo
        (0.32, (98, 33, 152)),    # neo violet
        (0.60, (220, 47, 138)),   # magenta
        (0.85, (255, 110, 110)),  # coral
        (1.00, (255, 196, 130)),  # warm amber edge
    ]

    for y in range(size):
        for x in range(size):
            r = math.hypot(x - cx, y - cy) / max_r
            r = min(1.0, r)
            # find the two stops bracketing r
            for i in range(len(stops) - 1):
                t0, c0 = stops[i]
                t1, c1 = stops[i + 1]
                if t0 <= r <= t1:
                    span = t1 - t0
                    t = (r - t0) / span if span > 0 else 0
                    px[x, y] = _lerp(c0, c1, t)
                    break
    return img


def heart_path(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
    """Parametric heart curve, scaled to roughly fit a bounding box `size` wide."""
    pts = []
    steps = 720
    # The classic parametric heart curve. Normalise so x in [-1,1].
    xmax = 0.0
    raw = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        raw.append((x, -y))  # flip y so the cusp points up
        if abs(x) > xmax:
            xmax = abs(x)
    scale = (size / 2) / xmax
    for x, y in raw:
        pts.append((cx + x * scale, cy + y * scale))
    return pts


def draw_glow_heart(img: Image.Image) -> None:
    """White heart with a soft outer glow and subtle inner shadow."""
    cx, cy = SIZE / 2, SIZE / 2 + 18  # nudge down slightly so cusp sits on optical center
    heart_size = SIZE * 0.62

    # Glow layer (heart rendered larger, blurred, semi-transparent white)
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.polygon(heart_path(cx, cy, heart_size * 1.05), fill=(255, 255, 255, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=42))
    img.alpha_composite(glow)

    # Main heart fill
    heart = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    hd = ImageDraw.Draw(heart)
    hd.polygon(heart_path(cx, cy, heart_size), fill=(255, 255, 255, 255))
    img.alpha_composite(heart)

    # Inner highlight (top-left sheen)
    sheen = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheen)
    sd.polygon(heart_path(cx - 60, cy - 60, heart_size * 0.55), fill=(255, 255, 255, 70))
    sheen = sheen.filter(ImageFilter.GaussianBlur(radius=18))
    img.alpha_composite(sheen)


def draw_graph_nodes(img: Image.Image) -> None:
    """Hub node at heart center, six satellite nodes ringing the heart."""
    cx, cy = SIZE / 2, SIZE / 2 + 30
    hub_r = 32
    sat_r = 22
    ring_r = SIZE * 0.36
    line_color = (28, 22, 66, 200)  # deep indigo, mostly opaque

    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # Satellite positions — six points evenly spaced, rotated so none sit on the cusp
    angles = [math.radians(a) for a in (-90, -30, 30, 90, 150, 210)]
    sats = [(cx + ring_r * math.cos(a), cy + ring_r * math.sin(a)) for a in angles]

    # Edges first, so the nodes draw over their endpoints
    for sx, sy in sats:
        d.line([(cx, cy), (sx, sy)], fill=line_color, width=10)

    # Hub node — filled magenta with a white inner dot
    d.ellipse(
        [cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r],
        fill=(220, 47, 138, 255),
        outline=(255, 255, 255, 255),
        width=6,
    )

    # Satellites — alternating brand colors
    palette = [
        (98, 33, 152),    # violet
        (220, 47, 138),   # magenta
        (255, 110, 110),  # coral
        (98, 33, 152),
        (220, 47, 138),
        (255, 110, 110),
    ]
    for (sx, sy), color in zip(sats, palette):
        d.ellipse(
            [sx - sat_r, sy - sat_r, sx + sat_r, sy + sat_r],
            fill=(*color, 255),
            outline=(255, 255, 255, 255),
            width=5,
        )

    img.alpha_composite(overlay)


def add_subtle_vignette(img: Image.Image) -> None:
    """Darken the corners slightly for a more premium feel."""
    vignette = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(vignette)
    # Draw a transparent rounded rectangle with darker corners by inverting
    for i in range(40):
        alpha = int(2 + i * 1.5)
        d.rectangle([i, i, SIZE - i, SIZE - i], outline=(0, 0, 0, alpha))
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=18))
    img.alpha_composite(vignette)


def render() -> Image.Image:
    bg = radial_gradient(SIZE).convert("RGBA")
    draw_glow_heart(bg)
    draw_graph_nodes(bg)
    add_subtle_vignette(bg)
    return bg


def main() -> None:
    OUT_ICON.parent.mkdir(parents=True, exist_ok=True)
    OUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    img = render()
    img.convert("RGB").save(OUT_ICON, format="PNG", optimize=True)
    img.convert("RGB").save(OUT_DOC, format="PNG", optimize=True)
    print(f"Wrote {OUT_ICON}")
    print(f"Wrote {OUT_DOC}")


if __name__ == "__main__":
    main()
