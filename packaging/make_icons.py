#!/usr/bin/env python3
"""
Generate all icon formats needed for the COPPIR builds.

Outputs:
  icon.png       512x512 PNG  (Linux, and source for all others)
  icon.ico       multi-size ICO for Windows (16, 32, 48, 64, 128, 256)
  icon.iconset/  directory of PNGs for macOS; run `iconutil -c icns icon.iconset`
                 to produce icon.icns (macOS only, build_mac.sh does this automatically)

Requires: pip install Pillow
Run from the packaging/ directory.
"""

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise SystemExit("Pillow is required:  pip install Pillow")

HERE = Path(__file__).parent

# Colors
BG    = (0, 10, 0, 255)    # very dark green matching the app theme
FG    = (255, 255, 255, 255)  # white eye on dark background


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _rounded_rect(draw: ImageDraw.ImageDraw, x0, y0, x1, y1, r, fill):
    """Fill a rounded rectangle (corner radius r) using three overlapping rects
    and four corner ellipses. PIL < 9.2 does not support rounded_rectangle."""
    draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
    draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
    draw.ellipse([x0,      y0,      x0 + 2*r, y0 + 2*r], fill=fill)
    draw.ellipse([x1 - 2*r, y0,      x1,       y0 + 2*r], fill=fill)
    draw.ellipse([x0,      y1 - 2*r, x0 + 2*r, y1      ], fill=fill)
    draw.ellipse([x1 - 2*r, y1 - 2*r, x1,      y1      ], fill=fill)


def _quadratic_bezier(p0, ctrl, p2, n=80):
    """Sample n+1 points on a quadratic Bezier curve."""
    pts = []
    for i in range(n + 1):
        t  = i / n
        mt = 1.0 - t
        x  = mt*mt*p0[0] + 2*mt*t*ctrl[0] + t*t*p2[0]
        y  = mt*mt*p0[1] + 2*mt*t*ctrl[1] + t*t*p2[1]
        pts.append((x, y))
    return pts


def _eye_polygon(cx, cy, hw, hh_top, hh_bot):
    """Return vertex list for an almond/eye outline.

    Two quadratic Bezier arcs share the left (cx-hw, cy) and right (cx+hw, cy)
    tip points and curve upward/downward through control points.
    """
    left  = (cx - hw, cy)
    right = (cx + hw, cy)
    top   = _quadratic_bezier(left,  (cx, cy - hh_top), right, 80)
    bot   = _quadratic_bezier(right, (cx, cy + hh_bot), left,  80)
    # Skip the duplicate endpoint where the arcs meet
    return top + bot[1:]


# ---------------------------------------------------------------------------
# Icon renderer
# ---------------------------------------------------------------------------

def make_icon(size: int) -> Image.Image:
    """Render a monochromatic eye icon at the given pixel size.

    The image is rendered at 4x resolution and downsampled with LANCZOS
    to produce clean anti-aliased edges at small sizes.
    """
    SCALE = 4
    S     = size * SCALE
    cx = cy = S / 2.0

    img  = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark rounded-square background
    corner_r = S * 0.22
    _rounded_rect(draw, 0, 0, S - 1, S - 1, corner_r, fill=BG)

    # Eye geometry (proportions chosen so the icon reads well at 16px)
    hw      = S * 0.42          # half-width of the eye
    hh_top  = S * 0.44          # control-point offset for the upper arc
    hh_bot  = S * 0.37          # slightly flatter lower arc
    stroke  = max(int(S * 0.048), 3)

    pts = _eye_polygon(cx, cy, hw, hh_top, hh_bot)

    # Eye outline — Pillow polygon outline, no fill
    draw.polygon(pts, fill=None, outline=FG, width=stroke)

    # Iris ring
    r_iris = hh_top * 0.52
    draw.ellipse(
        [cx - r_iris, cy - r_iris, cx + r_iris, cy + r_iris],
        fill=None, outline=FG, width=stroke,
    )

    # Pupil (solid)
    r_pupil = r_iris * 0.44
    draw.ellipse(
        [cx - r_pupil, cy - r_pupil, cx + r_pupil, cy + r_pupil],
        fill=FG,
    )

    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------

def main():
    print("Generating COPPIR icons...")

    # PNG — primary source, used directly on Linux
    png = make_icon(512)
    png.save(HERE / "icon.png")
    print("  icon.png  (512x512)")

    # ICO — Windows multi-size bundle
    ico_sizes  = [16, 32, 48, 64, 128, 256]
    ico_frames = [make_icon(s) for s in ico_sizes]
    ico_frames[0].save(
        HERE / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=ico_frames[1:],
    )
    print("  icon.ico  (16/32/48/64/128/256)")

    # iconset — macOS; build_mac.sh runs `iconutil -c icns icon.iconset`
    iconset = HERE / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    for s in [16, 32, 128, 256, 512]:
        make_icon(s    ).save(iconset / f"icon_{s}x{s}.png")
        make_icon(s * 2).save(iconset / f"icon_{s}x{s}@2x.png")
    print("  icon.iconset/  (run `iconutil -c icns icon.iconset` on macOS)")

    print("Done.")


if __name__ == "__main__":
    main()
