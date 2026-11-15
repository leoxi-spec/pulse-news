#!/usr/bin/env python3
"""Generate Pulse app icons as PNGs using only the standard library.

The regular icon and the 24 holiday icons all use the same waveform geometry,
so the brand stays recognisable while the palette and small motif change.
"""
from __future__ import annotations

import math
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pulse.holidays import SEASONS  # noqa: E402

OUT = ROOT / "pulse" / "static" / "icons"
SEASON_OUT = OUT / "seasons"

NORMAL = {
    "id": "normal",
    "label": "Pulse",
    "icon": {
        "start": "#7c5cff", "end": "#ff4d8d", "bar": "#ffffff",
        "motif": "none", "motif_color": "#ffffff", "detail": "#ffffff",
        "pattern": "none",
    },
}


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rounded_rect(x, y, w, h, radius, px, py):
    if x + radius <= px <= x + w - radius or y + radius <= py <= y + h - radius:
        if x <= px <= x + w and y <= py <= y + h:
            return True
    for cx, cy in ((x + radius, y + radius), (x + w - radius, y + radius),
                   (x + radius, y + h - radius), (x + w - radius, y + h - radius)):
        if (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2:
            return True
    return False


def _blend(base, over, alpha):
    alpha = max(0.0, min(1.0, alpha))
    return tuple(round(base[i] + (over[i] - base[i]) * alpha) for i in range(3))


def _circle(px, py, cx, cy, radius):
    return (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2


def _ellipse(px, py, cx, cy, rx, ry):
    return ((px - cx) / max(rx, 0.001)) ** 2 + ((py - cy) / max(ry, 0.001)) ** 2 <= 1


def _polygon(px, py, points):
    inside = False
    j = len(points) - 1
    for i in range(len(points)):
        xi, yi = points[i]
        xj, yj = points[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def _star_points(cx, cy, outer, inner, points=5, rotation=-math.pi / 2):
    result = []
    for index in range(points * 2):
        angle = rotation + index * math.pi / points
        radius = outer if index % 2 == 0 else inner
        result.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return result


def _snowflake(px, py, cx, cy, radius):
    dx, dy = px - cx, py - cy
    if dx * dx + dy * dy > (radius * 1.04) ** 2:
        return False
    for angle in (0, 30, 60, 90, 120, 150):
        radians = math.radians(angle)
        ux, uy = math.cos(radians), math.sin(radians)
        along = dx * ux + dy * uy
        across = abs(dx * uy - dy * ux)
        if abs(along) <= radius and across <= max(0.8, radius * 0.055):
            return True
    return False


def _heart(px, py, cx, cy, r):
    if _circle(px, py, cx - r * 0.43, cy - r * 0.24, r * 0.57):
        return True
    if _circle(px, py, cx + r * 0.43, cy - r * 0.24, r * 0.57):
        return True
    return _polygon(px, py, [
        (cx - r, cy - r * 0.12), (cx + r, cy - r * 0.12), (cx, cy + r * 0.92),
    ])


def _shamrock(px, py, cx, cy, r):
    if _circle(px, py, cx, cy - r * 0.40, r * 0.43):
        return True
    if _circle(px, py, cx - r * 0.48, cy + r * 0.04, r * 0.43):
        return True
    if _circle(px, py, cx + r * 0.48, cy + r * 0.04, r * 0.43):
        return True
    return rounded_rect(cx - r * 0.09, cy + r * 0.12, r * 0.18, r * 0.86, r * 0.09, px, py)


def _star6(px, py, cx, cy, r):
    up = [(cx, cy - r), (cx + r * 0.86, cy + r * 0.5), (cx - r * 0.86, cy + r * 0.5)]
    down = [(cx, cy + r), (cx + r * 0.86, cy - r * 0.5), (cx - r * 0.86, cy - r * 0.5)]
    return _polygon(px, py, up) or _polygon(px, py, down)


def _maple(px, py, cx, cy, r):
    points = [
        (cx, cy - r), (cx + r * .16, cy - r * .48), (cx + r * .55, cy - r * .67),
        (cx + r * .40, cy - r * .10), (cx + r * .94, cy - r * .14),
        (cx + r * .60, cy + r * .22), (cx + r * .74, cy + r * .48),
        (cx + r * .18, cy + r * .40), (cx, cy + r * .90),
        (cx - r * .18, cy + r * .40), (cx - r * .74, cy + r * .48),
        (cx - r * .60, cy + r * .22), (cx - r * .94, cy - r * .14),
        (cx - r * .40, cy - r * .10), (cx - r * .55, cy - r * .67),
        (cx - r * .16, cy - r * .48),
    ]
    return _polygon(px, py, points)


def _rainbow(px, py, cx, cy, r):
    dx, dy = px - cx, py - cy
    dist = math.hypot(dx, dy)
    return dy <= 0 and r * .48 <= dist <= r * 1.05


def _crescent(px, py, cx, cy, r):
    return _circle(px, py, cx, cy, r) and not _circle(px, py, cx + r * .38, cy - r * .08, r * .82)


def _diamond(px, py, cx, cy, r):
    return abs(px - cx) + abs(py - cy) <= r


def _motif_color(style, px, py, cx, cy, r):
    motif = style["motif"]
    main = rgb(style["motif_color"])
    detail = rgb(style["detail"])
    if motif == "none":
        return None
    if motif == "star":
        return main if _polygon(px, py, _star_points(cx, cy, r, r * .42)) else None
    if motif == "star6":
        return main if _star6(px, py, cx, cy, r) else None
    if motif == "heart":
        return main if _heart(px, py, cx, cy, r) else None
    if motif == "shamrock":
        return main if _shamrock(px, py, cx, cy, r) else None
    if motif == "crescent":
        return main if _crescent(px, py, cx, cy, r) else None
    if motif == "egg":
        if _ellipse(px, py, cx, cy, r * .68, r):
            return detail if (cy + r * .18 < py < cy + r * .34) else main
    if motif == "globe":
        if _circle(px, py, cx, cy, r):
            return detail if (_circle(px, py, cx - r * .34, cy - r * .24, r * .42) or _circle(px, py, cx + r * .30, cy + r * .28, r * .35)) else main
    if motif == "flower":
        for angle in range(0, 360, 72):
            a = math.radians(angle)
            if _circle(px, py, cx + math.cos(a) * r * .52, cy + math.sin(a) * r * .52, r * .38):
                return main
        return detail if _circle(px, py, cx, cy, r * .27) else None
    if motif == "maple":
        return main if _maple(px, py, cx, cy, r) else None
    if motif == "rainbow":
        if _rainbow(px, py, cx, cy, r):
            return main if math.hypot(px - cx, py - cy) > r * .78 else detail
        return None
    if motif == "tie":
        knot = [(cx - r * .22, cy - r * .72), (cx + r * .22, cy - r * .72), (cx + r * .28, cy - r * .30), (cx - r * .28, cy - r * .30)]
        body = [(cx - r * .28, cy - r * .20), (cx + r * .28, cy - r * .20), (cx + r * .58, cy + r * .88), (cx - r * .58, cy + r * .88)]
        if _polygon(px, py, knot):
            return detail
        return main if _polygon(px, py, body) else None
    if motif == "gear":
        dist = math.hypot(px - cx, py - cy)
        angle = math.atan2(py - cy, px - cx)
        teeth = 0.72 + 0.28 * (1 if math.cos(angle * 12) > .15 else 0)
        if dist <= r * teeth and dist >= r * .35:
            return main
        return None
    if motif == "apple":
        if _circle(px, py, cx, cy + r * .05, r * .82):
            return main
        if _ellipse(px, py, cx + r * .33, cy - r * .84, r * .36, r * .16):
            return detail
        return detail if rounded_rect(cx - r * .06, cy - r * .98, r * .12, r * .35, r * .06, px, py) else None
    if motif == "diya":
        if _ellipse(px, py, cx, cy + r * .34, r * .90, r * .40):
            return main
        if _ellipse(px, py, cx, cy - r * .22, r * .23, r * .48):
            return detail
        return None
    if motif == "pumpkin":
        if _ellipse(px, py, cx, cy + r * .10, r * .86, r * .72):
            if abs(px - cx) < r * .10 or abs(abs(px - cx) - r * .38) < r * .07:
                return detail
            return main
        return detail if rounded_rect(cx - r * .08, cy - r * .86, r * .16, r * .34, r * .08, px, py) else None
    if motif == "leaf":
        if _ellipse(px, py, cx, cy, r * .62, r):
            return detail if abs(px - cx) < r * .05 else main
    if motif == "lantern":
        if rounded_rect(cx - r * .55, cy - r * .70, r * 1.10, r * 1.35, r * .26, px, py):
            if abs(px - cx) < r * .06 or abs(py - cy) < r * .06:
                return detail
            return main
        return detail if _circle(px, py, cx, cy - r * .92, r * .18) else None
    if motif in ("menorah", "kinara"):
        for index in range(7):
            offset = (index - 3) * r * .31
            candle_color = detail if motif == "kinara" and index % 3 == 1 else main
            top = cy - r * (.42 if index != 3 else .72)
            if rounded_rect(cx + offset - r * .07, top, r * .14, r * 1.10, r * .07, px, py):
                return candle_color
            if _ellipse(px, py, cx + offset, top - r * .12, r * .09, r * .15):
                return detail
        return detail if rounded_rect(cx - r * .92, cy + r * .62, r * 1.84, r * .14, r * .07, px, py) else None
    if motif == "sun":
        if _circle(px, py, cx, cy, r * .62):
            return main
        angle = math.atan2(py - cy, px - cx)
        dist = math.hypot(px - cx, py - cy)
        if r * .72 <= dist <= r * 1.02 and math.cos(angle * 10) > .15:
            return detail
    return None


def _pattern_color(style, x, y, size):
    pattern = style["pattern"]
    if pattern == "none":
        return None
    if pattern == "snow":
        for fx, fy, fr in (
            (int(size * .875), int(size * .17), max(2, int(size * .030))),
            (int(size * .945), int(size * .74), max(2, int(size * .024))),
            (int(size * .075), int(size * .22), max(2, int(size * .017))),
        ):
            if _snowflake(x, y, fx, fy, fr):
                return (255, 250, 242), 0.72
        return None
    if pattern == "confetti":
        dots = (
            (int(size * .10), int(size * .17), rgb(style["detail"])),
            (int(size * .88), int(size * .16), rgb(style["motif_color"])),
            (int(size * .91), int(size * .63), rgb(style["detail"])),
            (int(size * .09), int(size * .70), rgb(style["motif_color"])),
            (int(size * .22), int(size * .09), rgb(style["detail"])),
        )
        for cx, cy, color in dots:
            if _circle(x, y, cx, cy, max(2, int(size * .018))):
                return color, 0.82
        return None
    if pattern == "stars":
        points = (
            (int(size * .88), int(size * .17), rgb(style["detail"])),
            (int(size * .91), int(size * .72), rgb(style["motif_color"])),
            (int(size * .08), int(size * .25), rgb(style["detail"])),
        )
        for cx, cy, color in points:
            if _diamond(x, y, cx, cy, max(2, int(size * .024))):
                return color, 0.80
        return None
    if pattern in ("petals", "bubbles"):
        dots = (
            (int(size * .09), int(size * .22), rgb(style["detail"])),
            (int(size * .89), int(size * .18), rgb(style["motif_color"])),
            (int(size * .92), int(size * .70), rgb(style["detail"])),
            (int(size * .08), int(size * .68), rgb(style["motif_color"])),
        )
        for cx, cy, color in dots:
            radius = max(2, int(size * .015))
            if pattern == "bubbles":
                if _circle(x, y, cx, cy, radius) and not _circle(x, y, cx, cy, radius * .52):
                    return color, 0.75
            elif _circle(x, y, cx, cy, radius):
                return color, 0.78
        return None
    if pattern == "leaves":
        for cx, cy in ((int(size * .09), int(size * .22)), (int(size * .90), int(size * .70))):
            if _ellipse(x, y, cx, cy, max(2, int(size * .024)), max(2, int(size * .012))):
                return rgb(style["detail"]), 0.78
    return None


def draw(size: int, style: dict | None = None, *, padding: float = 0.0, transparent: bool = False) -> bytearray:
    """Draw a centred Pulse waveform in the supplied seasonal style."""
    style = style or NORMAL
    config = style["icon"]
    start = rgb(config["start"])
    end = rgb(config["end"])
    bar_color = rgb(config["bar"])
    if transparent:
        bg = (10, 12, 17)
    else:
        bg = lerp(start, end, 0.38)
    pixels = bytearray()
    inset = int(size * padding)
    tile = (inset, inset, size - inset, size - inset)
    radius = int((tile[2] - tile[0]) * 0.23)
    bars = [0.38, 0.65, 0.95, 0.78, 0.50]

    fit = 0.82
    bar_w = max(2, round(size * 0.160 * fit))
    gap = max(1, round(size * 0.042 * fit))
    total_w = len(bars) * bar_w + (len(bars) - 1) * gap
    left = (size - total_w) // 2
    max_bar = int(size * 0.9600 * fit)
    baseline = int(size * (0.5 + (0.9600 * fit * 0.95) / 2))

    tallest_top = baseline - int(max_bar * 0.95)
    motif_cx = left + 2 * (bar_w + gap) + bar_w / 2
    motif_cy = tallest_top - max(3, int(size * 0.035))
    motif_r = max(5, int(size * 0.058))
    ornament_r = max(2, int(size * 0.014))
    ornaments = [
        (left + (bar_w + gap) + bar_w / 2, baseline - int(max_bar * 0.65 * 0.52), rgb(config["motif_color"])),
        (left + 2 * (bar_w + gap) + bar_w / 2, baseline - int(max_bar * 0.95 * 0.40), rgb(config["detail"])),
        (left + 3 * (bar_w + gap) + bar_w / 2, baseline - int(max_bar * 0.78 * 0.55), rgb(config["motif_color"])),
    ]
    has_motif = config["motif"] != "none"

    for y in range(size):
        row = bytearray()
        for x in range(size):
            if not transparent and not rounded_rect(*tile, radius, x, y):
                row += b"\x00\x00\x00\x00"
                continue
            t = ((x - tile[0]) + (y - tile[1])) / max(1, (tile[2] - tile[0]) + (tile[3] - tile[1]))
            color = lerp(start, end, min(1.0, max(0.0, t)))
            if transparent:
                color = bg

            pattern = _pattern_color(config, x, y, size)
            if pattern:
                color = _blend(color, pattern[0], pattern[1])

            if has_motif:
                halo = math.hypot(x - motif_cx, y - motif_cy)
                if halo < motif_r * 2.7:
                    color = _blend(color, rgb(config["motif_color"]), 0.09 * (1 - halo / (motif_r * 2.7)))

            for index, height in enumerate(bars):
                bx = left + index * (bar_w + gap)
                bh = int(max_bar * height)
                by = baseline - bh
                if rounded_rect(bx, by, bar_w, bh, bar_w // 2, x, y):
                    color = bar_color
                    break

            if has_motif:
                for ox, oy, ornament in ornaments:
                    if _circle(x, y, ox, oy, ornament_r):
                        color = ornament
                        break

            if has_motif:
                motif = _motif_color(config, x, y, motif_cx, motif_cy, motif_r)
                if motif:
                    color = motif

            row += bytes((*color, 255))
        pixels += b"\x00" + row
    return pixels


def write_png(path: Path, size: int, pixels: bytearray, width: int, height: int) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = zlib.compress(bytes(pixels), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", raw)
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def write_style(directory: Path, style: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for size in (192, 512, 180):
        write_png(directory / f"icon-{size}.png", size, draw(size, style), size, size)
    write_png(directory / "apple-touch-icon.png", 180, draw(180, style), 180, 180)
    write_png(directory / "icon-maskable.png", 512, draw(512, style), 512, 512)


def normal_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="Pulse">
  <defs>
    <linearGradient id="pulse" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#7c5cff"/>
      <stop offset="1" stop-color="#ff4d8d"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="15" fill="url(#pulse)"/>
  <g fill="#ffffff">
    <rect x="6.583" y="36.75" width="8.375" height="19.125" rx="4.1875"/>
    <rect x="17.208" y="23.25" width="8.375" height="32.625" rx="4.1875"/>
    <rect x="27.833" y="8.125" width="8.375" height="47.75" rx="4.1875"/>
    <rect x="38.458" y="16.625" width="8.375" height="39.25" rx="4.1875"/>
    <rect x="49.083" y="30.75" width="8.375" height="25.125" rx="4.1875"/>
  </g>
</svg>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        pixels = draw(size, NORMAL)
        write_png(OUT / f"icon-{size}.png", size, pixels, size, size)
        write_png(OUT / f"icon-{size}-v24.png", size, pixels, size, size)
    write_png(OUT / "icon-maskable.png", 512, draw(512, NORMAL), 512, 512)
    write_png(OUT / "icon-maskable-v24.png", 512, draw(512, NORMAL), 512, 512)
    write_png(OUT / "apple-touch-icon.png", 180, draw(180, NORMAL), 180, 180)
    write_png(OUT / "apple-touch-icon-v24.png", 180, draw(180, NORMAL), 180, 180)
    svg = normal_svg()
    (OUT / "icon.svg").write_text(svg, encoding="utf-8")
    (OUT / "icon-v24.svg").write_text(svg, encoding="utf-8")

    for season in SEASONS:
        write_style(SEASON_OUT / season["id"], season)
    print(f"icons written to {OUT} (normal + {len(SEASONS)} seasons)")


if __name__ == "__main__":
    main()
