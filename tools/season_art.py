#!/usr/bin/env python3
"""Large, hand-built vector artwork for the 24 seasonal Pulse icons.

The old seasonal icons were the same five waveform bars with a tiny holiday
motif on top. This module gives every observance its own large illustration:
a clock for New Year, a lantern for Lunar New Year, a rainbow for Pride, a
menorah for Hanukkah, and so on. A faint heartbeat line and the Pulse tile
shape keep the family recognisable without making the icons interchangeable.

The module emits SVG. ``tools/make_icons.py`` rasterises it with the local
Chrome build, so the app itself still has no third-party runtime dependency.
"""
from __future__ import annotations

import math
from typing import Callable

W = 512
H = 512
RADIUS = 116


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(part * 2 for part in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _hex(value: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in value)


def _mix(a: str, b: str, amount: float) -> str:
    ca, cb = _rgb(a), _rgb(b)
    return _hex(tuple(ca[i] + (cb[i] - ca[i]) * amount for i in range(3)))


def _poly(points, fill: str, *, opacity: float = 1.0, extra: str = "") -> str:
    value = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon points="{value}" fill="{fill}" fill-opacity="{opacity:g}" {extra}/>'


def _circle(cx, cy, r, fill: str, *, opacity: float = 1.0, extra: str = "") -> str:
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" fill-opacity="{opacity:g}" {extra}/>'


def _ellipse(cx, cy, rx, ry, fill: str, *, opacity: float = 1.0, rotate: float = 0, extra: str = "") -> str:
    transform = f' transform="rotate({rotate:g} {cx:.1f} {cy:.1f})"' if rotate else ""
    return (
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
        f'fill="{fill}" fill-opacity="{opacity:g}"{transform} {extra}/>'
    )


def _rect(x, y, w, h, r, fill: str, *, opacity: float = 1.0, rotate: float = 0, extra: str = "") -> str:
    cx, cy = x + w / 2, y + h / 2
    transform = f' transform="rotate({rotate:g} {cx:.1f} {cy:.1f})"' if rotate else ""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r:.1f}" '
        f'fill="{fill}" fill-opacity="{opacity:g}"{transform} {extra}/>'
    )


def _line(x1, y1, x2, y2, color: str, width: float, *, opacity: float = 1.0, cap: str = "round") -> str:
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{width:g}" stroke-opacity="{opacity:g}" '
        f'stroke-linecap="{cap}"/>'
    )


def _path(d: str, fill: str, *, opacity: float = 1.0, extra: str = "") -> str:
    return f'<path d="{d}" fill="{fill}" fill-opacity="{opacity:g}" {extra}/>'


def _stroke_path(d: str, color: str, width: float, *, opacity: float = 1.0, extra: str = "") -> str:
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}" '
        f'stroke-opacity="{opacity:g}" stroke-linecap="round" stroke-linejoin="round" {extra}/>'
    )


def _star(cx, cy, outer, inner, fill: str, *, points: int = 5, rotate: float = -90, opacity: float = 1.0) -> str:
    coords = []
    for index in range(points * 2):
        angle = math.radians(rotate + index * 180 / points)
        radius = outer if index % 2 == 0 else inner
        coords.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return _poly(coords, fill, opacity=opacity)


def _sparkle(cx, cy, r, fill: str, *, opacity: float = 1.0) -> str:
    return _poly(
        [(cx, cy - r), (cx + r * 0.18, cy - r * 0.18), (cx + r, cy),
         (cx + r * 0.18, cy + r * 0.18), (cx, cy + r),
         (cx - r * 0.18, cy + r * 0.18), (cx - r, cy),
         (cx - r * 0.18, cy - r * 0.18)],
        fill, opacity=opacity,
    )


def _heart(cx, cy, r, fill: str, *, opacity: float = 1.0, rotate: float = 0) -> str:
    d = (
        f"M {cx:.1f} {cy + r * .92:.1f} "
        f"C {cx - r * .86:.1f} {cy + r * .30:.1f} {cx - r:.1f} {cy - r * .22:.1f} {cx - r:.1f} {cy - r * .46:.1f} "
        f"C {cx - r:.1f} {cy - r * .82:.1f} {cx - r * .55:.1f} {cy - r:.1f} {cx - r * .25:.1f} {cy - r:.1f} "
        f"C {cx - r * .08:.1f} {cy - r:.1f} {cx + r * .08:.1f} {cy - r * .84:.1f} {cx:.1f} {cy - r * .69:.1f} "
        f"C {cx + r * .08:.1f} {cy - r * .84:.1f} {cx + r * .08:.1f} {cy - r:.1f} {cx + r * .25:.1f} {cy - r:.1f} "
        f"C {cx + r * .55:.1f} {cy - r:.1f} {cx + r:.1f} {cy - r * .82:.1f} {cx + r:.1f} {cy - r * .46:.1f} "
        f"C {cx + r:.1f} {cy - r * .22:.1f} {cx + r * .86:.1f} {cy + r * .30:.1f} {cx:.1f} {cy + r * .92:.1f} Z"
    )
    transform = f' transform="rotate({rotate:g} {cx:.1f} {cy:.1f})"' if rotate else ""
    return f'<path d="{d}" fill="{fill}" fill-opacity="{opacity:g}"{transform}/>'


def _maple_points(cx, cy, r):
    return [
        (cx, cy - r), (cx + r * .16, cy - r * .48), (cx + r * .55, cy - r * .67),
        (cx + r * .40, cy - r * .10), (cx + r * .94, cy - r * .14),
        (cx + r * .60, cy + r * .22), (cx + r * .74, cy + r * .48),
        (cx + r * .18, cy + r * .40), (cx, cy + r * .90),
        (cx - r * .18, cy + r * .40), (cx - r * .74, cy + r * .48),
        (cx - r * .60, cy + r * .22), (cx - r * .94, cy - r * .14),
        (cx - r * .40, cy - r * .10), (cx - r * .55, cy - r * .67),
        (cx - r * .16, cy - r * .48),
    ]


def _shamrock(cx, cy, r, fill: str, detail: str) -> str:
    parts = [
        _circle(cx, cy - r * .42, r * .44, fill),
        _circle(cx - r * .50, cy + r * .03, r * .44, fill),
        _circle(cx + r * .50, cy + r * .03, r * .44, fill),
        _rect(cx - r * .09, cy + r * .14, r * .18, r * .90, r * .09, fill),
    ]
    parts.append(_line(cx, cy + r * .20, cx - r * .28, cy + r * .82, detail, r * .035, opacity=.45))
    return "".join(parts)


def _arc(cx, cy, r, start, end, color, width, *, opacity=1.0):
    sx = cx + math.cos(math.radians(start)) * r
    sy = cy + math.sin(math.radians(start)) * r
    ex = cx + math.cos(math.radians(end)) * r
    ey = cy + math.sin(math.radians(end)) * r
    large = 1 if abs(end - start) > 180 else 0
    sweep = 1 if end > start else 0
    return _stroke_path(f"M {sx:.1f} {sy:.1f} A {r:.1f} {r:.1f} 0 {large} {sweep} {ex:.1f} {ey:.1f}", color, width, opacity=opacity)


def _flame(cx, cy, r, outer: str, inner: str) -> str:
    d = (
        f"M {cx:.1f} {cy - r:.1f} C {cx + r * .68:.1f} {cy - r * .12:.1f} "
        f"{cx + r * .52:.1f} {cy + r * .72:.1f} {cx:.1f} {cy + r * .86:.1f} "
        f"C {cx - r * .52:.1f} {cy + r * .72:.1f} {cx - r * .68:.1f} {cy - r * .12:.1f} "
        f"{cx:.1f} {cy - r:.1f} Z"
    )
    inner_d = (
        f"M {cx:.1f} {cy - r * .52:.1f} C {cx + r * .30:.1f} {cy - r * .08:.1f} "
        f"{cx + r * .22:.1f} {cy + r * .44:.1f} {cx:.1f} {cy + r * .55:.1f} "
        f"C {cx - r * .22:.1f} {cy + r * .44:.1f} {cx - r * .30:.1f} {cy - r * .08:.1f} "
        f"{cx:.1f} {cy - r * .52:.1f} Z"
    )
    return _path(d, outer) + _path(inner_d, inner)


def _cloud(cx, cy, r, fill: str, *, opacity: float = 1.0) -> str:
    return "".join([
        _circle(cx - r * .56, cy + r * .08, r * .46, fill, opacity=opacity),
        _circle(cx, cy - r * .10, r * .62, fill, opacity=opacity),
        _circle(cx + r * .58, cy + r * .08, r * .46, fill, opacity=opacity),
        _rect(cx - r, cy + r * .03, r * 2, r * .50, r * .22, fill, opacity=opacity),
    ])


def _hexagon(cx, cy, r):
    return [(cx + math.cos(math.radians(60 * i)) * r, cy + math.sin(math.radians(60 * i)) * r) for i in range(6)]


def _snowflake(cx, cy, r, color, width, opacity=.7):
    parts = []
    for angle in range(0, 360, 60):
        a = math.radians(angle)
        parts.append(_line(cx, cy, cx + math.cos(a) * r, cy + math.sin(a) * r, color, width, opacity=opacity))
        bx = cx + math.cos(a) * r * .68
        by = cy + math.sin(a) * r * .68
        for offset in (-32, 32):
            b = math.radians(angle + offset)
            parts.append(_line(bx, by, bx + math.cos(b) * r * .28, by + math.sin(b) * r * .28, color, width * .8, opacity=opacity))
    return "".join(parts)


def _bat(cx, cy, r, fill, opacity=1.0):
    return _path(
        f"M {cx:.1f} {cy:.1f} "
        f"C {cx - r * .12:.1f} {cy - r * .42:.1f} {cx - r * .42:.1f} {cy - r * .44:.1f} {cx - r:.1f} {cy - r * .20:.1f} "
        f"C {cx - r * .70:.1f} {cy - r * .02:.1f} {cx - r * .54:.1f} {cy + r * .20:.1f} {cx - r * .30:.1f} {cy + r * .10:.1f} "
        f"C {cx - r * .30:.1f} {cy + r * .42:.1f} {cx - r * .08:.1f} {cy + r * .46:.1f} {cx:.1f} {cy + r * .26:.1f} "
        f"C {cx + r * .08:.1f} {cy + r * .46:.1f} {cx + r * .30:.1f} {cy + r * .42:.1f} {cx + r * .30:.1f} {cy + r * .10:.1f} "
        f"C {cx + r * .54:.1f} {cy + r * .20:.1f} {cx + r * .70:.1f} {cy - r * .02:.1f} {cx + r:.1f} {cy - r * .20:.1f} "
        f"C {cx + r * .42:.1f} {cy - r * .44:.1f} {cx + r * .12:.1f} {cy - r * .42:.1f} {cx:.1f} {cy:.1f} Z",
        fill, opacity=opacity,
    )


# --------------------------------------------------------------------------
# Palettes


class Palette:
    def __init__(self, season: dict):
        icon = season["icon"]
        palette = season["palette"]
        self.start = icon["start"]
        self.end = icon["end"]
        self.bar = icon["bar"]
        self.main = icon["motif_color"]
        self.detail = icon["detail"]
        self.accent = palette.get("--accent", self.main)
        self.accent2 = palette.get("--accent-2", self.detail)
        self.accent3 = palette.get("--accent-3", self.bar)
        self.bg = palette.get("--bg", "#0a0c11")
        self.surface = palette.get("--surface", "#151923")
        self.deep = _mix(self.start, "#05050a", .58)
        self.ink = _mix(self.end, "#05050a", .48)
        self.soft = _mix(self.bar, self.bg, .42)
        self.white = self.bar
        self.gold = "#ffd166" if self.main.lower() not in ("#ffd166", "#f7c948") else self.main
        self.green_light = _mix(self.accent3, "#ffffff", .18)
        self.green_mid = _mix(self.accent3, "#04140c", .16)
        self.green_dark = _mix(self.accent3, "#04140c", .30)


# --------------------------------------------------------------------------
# Background patterns

PATTERNS = {
    "new-year": "fireworks",
    "lunar-new-year": "bunting",
    "valentines": "hearts",
    "st-patricks": "coins",
    "holi": "confetti",
    "eid": "stars",
    "easter": "petals",
    "passover": "stars",
    "earth-day": "leaves",
    "mothers-day": "petals",
    "victoria-day": "fireworks",
    "pride": "sparkles",
    "fathers-day": "stars",
    "juneteenth": "stars",
    "canada-day": "maple",
    "independence-day": "fireworks",
    "labor-day": "rays",
    "rosh-hashanah": "hex",
    "diwali": "sparkles",
    "halloween": "bats",
    "thanksgiving": "leaves",
    "hanukkah": "stars",
    "christmas": "snow",
    "kwanzaa": "sparkles",
}


def _pattern(season: dict, p: Palette) -> str:
    name = PATTERNS.get(season["id"], season["icon"].get("pattern", "none"))
    c1, c2, c3 = p.main, p.detail, p.accent3
    if name == "fireworks":
        out = []
        for cx, cy, r, color in ((105, 135, 46, c1), (415, 112, 38, c2), (390, 320, 30, c3)):
            for angle in range(0, 360, 30):
                a = math.radians(angle)
                out.append(_line(cx, cy, cx + math.cos(a) * r, cy + math.sin(a) * r, color, 3.2, opacity=.55))
                out.append(_circle(cx + math.cos(a) * r * 1.08, cy + math.sin(a) * r * 1.08, 3.2, color, opacity=.65))
            out.append(_circle(cx, cy, 3.5, p.bar, opacity=.8))
        return f'<g opacity=".8">{"".join(out)}</g>'
    if name == "bunting":
        out = []
        for index, (x, y, color) in enumerate(((60, 54, c1), (132, 36, c2), (204, 30, c3), (308, 30, c3), (380, 37, c2), (452, 56, c1))):
            out.append(_poly([(x, y), (x + 42, y), (x + 21, y + 58 + index % 2 * 8)], color, opacity=.52))
        out.append(_stroke_path("M 42 44 Q 256 10 470 44", p.bar, 2.4, opacity=.25))
        return "".join(out)
    if name == "hearts":
        return "".join(
            _heart(cx, cy, r, color, opacity=.30)
            for cx, cy, r, color in ((82, 100, 18, c1), (430, 86, 22, c2), (445, 300, 14, c1), (76, 320, 12, c2), (112, 198, 9, c3))
        )
    if name == "coins":
        out = []
        for cx, cy, r in ((74, 110, 20), (438, 84, 15), (452, 320, 22), (66, 330, 14), (110, 62, 9)):
            out.append(_circle(cx, cy, r, c1, opacity=.62))
            out.append(f'<circle cx="{cx}" cy="{cy}" r="{r * .62:.1f}" fill="none" stroke="{c2}" stroke-width="2.2" stroke-opacity=".62"/>')
        return "".join(out)
    if name == "confetti":
        out = []
        for index, (x, y, color) in enumerate(((52, 88, c1), (452, 92, c2), (470, 250, c3), (44, 250, c2), (86, 402, c1), (432, 390, c3))):
            out.append(_rect(x, y, 10 + index % 2 * 5, 24, 5, color, opacity=.46, rotate=index * 29))
        for x, y, color in ((118, 54, c2), (394, 50, c1), (472, 174, c2), (36, 170, c3)):
            out.append(_circle(x, y, 5, color, opacity=.62))
        return "".join(out)
    if name == "stars":
        out = []
        for x, y, r, color in ((68, 94, 12, c1), (445, 78, 16, c2), (454, 290, 10, c3), (58, 300, 13, c2), (116, 54, 6, c3), (392, 198, 7, c1)):
            out.append(_sparkle(x, y, r, color, opacity=.58))
        return "".join(out)
    if name == "petals":
        out = []
        for x, y, color, angle in ((66, 96, c1, -28), (452, 78, c2, 24), (472, 276, c3, 40), (44, 300, c2, -42), (100, 410, c1, 18), (420, 408, c3, -18)):
            out.append(_ellipse(x, y, 17, 8, color, opacity=.38, rotate=angle))
        return "".join(out)
    if name == "leaves":
        out = []
        for x, y, color, angle in ((70, 84, c1, -40), (450, 96, c2, 38), (470, 308, c3, 70), (42, 280, c2, -65), (92, 408, c3, -20), (424, 408, c1, 25)):
            out.append(_ellipse(x, y, 22, 9, color, opacity=.36, rotate=angle))
            out.append(_line(x - 15, y, x + 15, y, p.bar, 1.6, opacity=.22))
        return "".join(out)
    if name == "sparkles":
        out = []
        for x, y, r, color in ((60, 88, 9, c1), (450, 76, 13, c2), (460, 300, 8, c3), (52, 312, 11, c2), (116, 46, 5, c3), (400, 190, 6, c1)):
            out.append(_sparkle(x, y, r, color, opacity=.65))
        return "".join(out)
    if name == "rays":
        out = []
        for angle in range(0, 360, 18):
            a = math.radians(angle)
            out.append(_line(256 + math.cos(a) * 210, 256 + math.sin(a) * 210,
                             256 + math.cos(a) * 250, 256 + math.sin(a) * 250, p.bar, 4, opacity=.16))
        return "".join(out)
    if name == "hex":
        out = []
        for cx, cy, r in ((72, 86, 26), (438, 82, 20), (460, 292, 30), (54, 300, 20), (106, 410, 16)):
            out.append(_poly(_hexagon(cx, cy, r), c1, opacity=.28, extra=f'stroke="{c2}" stroke-width="2" stroke-opacity=".55"'))
        return "".join(out)
    if name == "bats":
        return "".join(
            _bat(cx, cy, r, color, opacity=.55)
            for cx, cy, r, color in ((76, 88, 23, c1), (434, 78, 18, c2), (452, 270, 12, c1), (62, 300, 10, c2))
        )
    if name == "maple":
        return "".join(
            _poly(_maple_points(cx, cy, r), color, opacity=.25)
            for cx, cy, r, color in ((66, 92, 20, c1), (448, 84, 16, c2), (450, 304, 12, c1))
        )
    if name == "snow":
        out = []
        for cx, cy, r in ((82, 94, 20), (438, 78, 15), (460, 300, 18), (58, 288, 13), (104, 410, 10), (424, 404, 12)):
            out.append(_snowflake(cx, cy, r, p.bar, 2.2, opacity=.55))
        for cx, cy, r in ((140, 44, 3), (354, 50, 2.5), (472, 186, 2.5), (34, 176, 3)):
            out.append(_circle(cx, cy, r, p.bar, opacity=.5))
        return "".join(out)
    return ""


# --------------------------------------------------------------------------
# Individual illustrations. Each returns the foreground SVG for one icon.


def art_new_year(uid: str, p: Palette) -> str:
    ticks = []
    for index in range(12):
        a = math.radians(index * 30 - 90)
        r1, r2 = 154, 166
        ticks.append(_line(256 + math.cos(a) * r1, 256 + math.sin(a) * r1,
                           256 + math.cos(a) * r2, 256 + math.sin(a) * r2,
                           p.main, 4 if index % 3 == 0 else 2.4, opacity=.75))
    skyline = _path(
        "M 24 450 L 24 402 L 62 402 L 62 366 L 102 366 L 102 416 L 138 416 L 138 344 "
        "L 180 344 L 180 390 L 218 390 L 218 318 L 252 318 L 252 398 L 292 398 L 292 354 "
        "L 332 354 L 332 410 L 374 410 L 374 336 L 414 336 L 414 382 L 452 382 L 452 360 "
        "L 488 360 L 488 450 Z", p.deep, opacity=.94,
    )
    windows = "".join(
        _rect(x, y, 8, 11, 2, p.main, opacity=.58)
        for x, y in ((50, 418), (78, 384), (116, 434), (154, 362), (192, 408), (238, 340),
                     (278, 414), (314, 374), (352, 426), (390, 354), (428, 402), (462, 380))
    )
    body = "".join([
        _circle(256, 256, 208, p.main, opacity=.08),
        _circle(256, 256, 176, p.deep, opacity=.55),
        f'<circle cx="256" cy="256" r="168" fill="none" stroke="{p.main}" stroke-width="15"/>',
        f'<circle cx="256" cy="256" r="148" fill="none" stroke="{p.main}" stroke-width="3" stroke-opacity=".25"/>',
        *ticks,
        _line(256, 256, 256, 132, p.bar, 11),
        _line(256, 256, 330, 304, p.bar, 8, opacity=.9),
        _circle(256, 256, 13, p.main),
        _circle(256, 256, 5, p.deep),
        skyline,
        windows,
    ])
    return body


def art_lunar_new_year(uid: str, p: Palette) -> str:
    def lantern(cx, cy, scale, opacity=1.0):
        w, h = 156 * scale, 190 * scale
        body = _rect(cx - w / 2, cy - h / 2, w, h, w * .36, p.detail, opacity=opacity)
        ribs = "".join(
            _line(cx + (index - 2) * w * .19, cy - h * .38, cx + (index - 2) * w * .19, cy + h * .38,
                  p.main, 3.2 * scale, opacity=.55 * opacity)
            for index in range(5)
        )
        caps = (
            _rect(cx - w * .34, cy - h * .60, w * .68, 18 * scale, 8 * scale, p.main, opacity=opacity)
            + _rect(cx - w * .34, cy + h * .52, w * .68, 18 * scale, 8 * scale, p.main, opacity=opacity)
            + _line(cx, cy + h * .60, cx, cy + h * .92, p.main, 4 * scale, opacity=.85 * opacity)
            + _poly([(cx, cy + h * .78), (cx + 12 * scale, cy + h * .88), (cx, cy + h * .99),
                     (cx - 12 * scale, cy + h * .88)], p.detail, opacity=opacity)
        )
        return body + ribs + caps

    clouds = "".join([
        _cloud(92, 372, 52, p.main, opacity=.18),
        _cloud(430, 396, 44, p.main, opacity=.13),
    ])
    return "".join([
        clouds,
        lantern(128, 190, .54, .45),
        lantern(386, 174, .46, .36),
        lantern(256, 258, 1.08),
        _circle(256, 258, 150, p.main, opacity=.07),
    ])


def art_valentines(uid: str, p: Palette) -> str:
    heart = _heart(256, 260, 154, p.main)
    shine = _heart(226, 220, 42, p.bar, opacity=.19)
    arrow = "".join([
        _line(96, 398, 416, 132, p.gold, 13),
        _poly([(416, 132), (362, 142), (397, 178)], p.gold),
        _poly([(96, 398), (106, 344), (69, 363)], p.detail),
        _poly([(96, 398), (150, 388), (131, 425)], p.detail),
    ])
    return "".join([
        _circle(256, 260, 190, p.main, opacity=.06),
        heart,
        shine,
        arrow,
        _sparkle(128, 170, 18, p.detail, opacity=.8),
        _sparkle(392, 356, 13, p.main),
    ])


def art_st_patricks(uid: str, p: Palette) -> str:
    shoe = _stroke_path("M 136 346 C 136 174 376 174 376 346", p.gold, 25)
    holes = "".join(
        _circle(x, y, 4, p.deep, opacity=.8)
        for x, y in ((136, 330), (150, 246), (196, 188), (256, 166), (316, 188), (362, 246), (376, 330))
    )
    return "".join([
        _circle(256, 250, 188, p.main, opacity=.08),
        shoe, holes,
        _shamrock(256, 278, 98, p.accent3, p.main),
        _circle(118, 402, 29, p.gold),
        f'<circle cx="118" cy="402" r="19" fill="none" stroke="{p.deep}" stroke-width="2" stroke-opacity=".55"/>',
        _circle(392, 414, 23, p.gold, opacity=.9),
        f'<circle cx="392" cy="414" r="14" fill="none" stroke="{p.deep}" stroke-width="2" stroke-opacity=".5"/>',
        _sparkle(110, 138, 11, p.bar, opacity=.8),
        _sparkle(408, 160, 8, p.gold, opacity=.8),
    ])


def art_holi(uid: str, p: Palette) -> str:
    splash = "".join([
        _circle(218, 246, 112, p.accent, opacity=.92),
        _circle(302, 236, 102, p.accent2, opacity=.88),
        _circle(256, 300, 94, p.accent3, opacity=.88),
        _circle(256, 256, 76, p.main, opacity=.8),
        _path(
            "M 198 154 C 234 118 300 126 328 158 C 354 190 382 208 376 256 "
            "C 370 304 330 336 292 346 C 248 358 198 338 170 304 C 140 266 144 208 198 154 Z",
            p.detail, opacity=.28,
        ),
    ])
    drops = []
    for index in range(14):
        a = math.radians(index * 25.7 + 9)
        r = 152 + (index % 3) * 28
        cx, cy = 256 + math.cos(a) * r, 256 + math.sin(a) * r
        radius = 8 + (index % 4) * 4
        color = (p.accent, p.accent2, p.accent3, p.main)[index % 4]
        drops.append(_circle(cx, cy, radius, color, opacity=.9))
        if index % 3 == 0:
            drops.append(_circle(cx + 10, cy + 10, radius * .34, p.bar, opacity=.6))
    hand = "".join([
        _rect(210, 278, 94, 96, 28, p.bar, opacity=.92),
        _rect(211, 214, 16, 82, 8, p.bar, opacity=.92),
        _rect(231, 198, 16, 98, 8, p.bar, opacity=.92),
        _rect(251, 192, 16, 104, 8, p.bar, opacity=.92),
        _rect(271, 204, 16, 94, 8, p.bar, opacity=.92),
        _rect(291, 226, 15, 74, 7.5, p.bar, opacity=.92),
        _rect(180, 310, 17, 63, 8.5, p.bar, opacity=.92, rotate=-42),
        _circle(222, 300, 7, p.accent, opacity=.65),
        _circle(264, 330, 9, p.accent2, opacity=.55),
        _circle(292, 292, 5, p.accent3, opacity=.8),
    ])
    return "".join([splash, "".join(drops), hand, _circle(256, 256, 196, p.main, opacity=.05)])


def art_eid(uid: str, p: Palette) -> str:
    mask = f'<mask id="{uid}-crescent"><rect width="512" height="512" fill="#fff"/><circle cx="322" cy="196" r="118" fill="#000"/></mask>'
    mosque = "".join([
        _rect(128, 360, 24, 102, 8, p.deep),
        _rect(360, 360, 24, 102, 8, p.deep),
        _rect(112, 350, 56, 18, 7, p.main, opacity=.8),
        _rect(344, 350, 56, 18, 7, p.main, opacity=.8),
        _path("M 168 452 L 168 380 Q 168 318 256 296 Q 344 318 344 380 L 344 452 Z", p.deep),
        _stroke_path("M 178 380 Q 178 328 256 310 Q 334 328 334 380", p.main, 5, opacity=.45),
        _rect(206, 404, 100, 48, 8, p.main, opacity=.24),
    ])
    return "".join([
        mask,
        _circle(256, 246, 190, p.main, opacity=.07),
        f'<g mask="url(#{uid}-crescent)"><circle cx="236" cy="236" r="134" fill="{p.main}"/></g>',
        _circle(314, 190, 168, p.main, opacity=.035),
        mosque,
        _sparkle(112, 154, 12, p.bar, opacity=.8),
        _sparkle(414, 292, 9, p.main, opacity=.8),
        _star(384, 142, 11, 4.5, p.main, opacity=.8),
    ])


def art_easter(uid: str, p: Palette) -> str:
    egg_clip = f'<clipPath id="{uid}-egg"><ellipse cx="256" cy="292" rx="122" ry="158"/></clipPath>'
    eggs = "".join([
        _ellipse(196, 116, 30, 92, p.main, opacity=.75, rotate=-19),
        _ellipse(316, 116, 30, 92, p.main, opacity=.75, rotate=19),
        _ellipse(196, 116, 15, 60, p.detail, opacity=.55, rotate=-19),
        _ellipse(316, 116, 15, 60, p.detail, opacity=.55, rotate=19),
        _ellipse(256, 292, 122, 158, p.bar),
        f'<g clip-path="url(#{uid}-egg)">',
        _rect(120, 190, 272, 42, 0, p.main, opacity=.85),
        _rect(120, 260, 272, 22, 0, p.detail, opacity=.75),
        _rect(120, 352, 272, 38, 0, p.main, opacity=.55),
        _path("M 118 310 L 146 288 L 174 310 L 202 288 L 230 310 L 258 288 L 286 310 L 314 288 L 342 310 L 370 288 L 396 310", p.detail, opacity=.7),
        _circle(190, 228, 13, p.detail, opacity=.8),
        _circle(250, 228, 9, p.bar, opacity=.8),
        _circle(320, 226, 15, p.detail, opacity=.8),
        _circle(202, 388, 11, p.bar, opacity=.8),
        _circle(318, 390, 8, p.bar, opacity=.8),
        "</g>",
        _ellipse(256, 292, 122, 158, "none", extra=f'stroke="{p.main}" stroke-width="6" stroke-opacity=".7"'),
    ])
    return "".join([egg_clip, _circle(256, 290, 190, p.main, opacity=.05), eggs, _sparkle(104, 160, 13, p.detail), _sparkle(408, 384, 10, p.main)])


def art_passover(uid: str, p: Palette) -> str:
    cup = "".join([
        _path("M 214 154 L 298 154 L 282 236 Q 256 260 230 236 Z", p.main),
        _line(256, 250, 256, 292, p.main, 9),
        _rect(224, 288, 64, 12, 6, p.main),
        _ellipse(256, 152, 44, 10, p.bar, opacity=.45),
    ])
    plate = "".join([
        _ellipse(256, 370, 178, 58, p.deep, opacity=.85),
        _ellipse(256, 360, 178, 58, p.bar, opacity=.18),
        f'<ellipse cx="256" cy="356" rx="164" ry="48" fill="none" stroke="{p.main}" stroke-width="4" stroke-opacity=".55"/>',
        *[
            _circle(x, y, 26, color, opacity=.92)
            for x, y, color in ((166, 342, p.detail), (214, 378, p.main), (298, 378, p.main),
                                (346, 342, p.detail), (256, 322, p.accent3))
        ],
        _circle(256, 360, 24, p.bar, opacity=.20),
    ])
    return "".join([
        _circle(256, 264, 190, p.main, opacity=.06),
        _star(256, 246, 154, 65, p.main, opacity=.10),
        cup,
        plate,
        _star(120, 186, 11, 4.5, p.bar, opacity=.68),
        _star(398, 220, 8, 3.4, p.main, opacity=.7),
    ])


def art_earth_day(uid: str, p: Palette) -> str:
    globe_clip = f'<clipPath id="{uid}-globe"><circle cx="256" cy="256" r="146"/></clipPath>'
    continents = "".join([
        _path("M 142 206 C 178 174 218 184 232 208 C 246 232 220 250 238 272 C 250 288 224 306 198 292 C 170 278 160 248 142 206 Z", p.main, opacity=.95),
        _path("M 288 170 C 326 156 358 174 354 198 C 350 224 316 222 304 244 C 294 262 264 252 270 228 C 274 208 280 190 288 170 Z", p.accent3, opacity=.88),
        _path("M 292 296 C 326 284 354 304 344 330 C 336 352 302 358 286 342 C 270 326 274 306 292 296 Z", p.main, opacity=.8),
        _path("M 160 334 C 184 326 202 344 192 362 C 182 378 154 374 150 356 C 148 346 152 338 160 334 Z", p.accent3, opacity=.7),
    ])
    return "".join([
        globe_clip,
        _circle(256, 256, 176, p.main, opacity=.06),
        f'<circle cx="256" cy="256" r="146" fill="{p.detail}" opacity=".95"/>',
        f'<g clip-path="url(#{uid}-globe)">{continents}',
        _path("M 110 216 C 150 196 196 214 236 194", p.bar, opacity=.30),
        _path("M 132 304 C 184 288 226 300 272 282", p.bar, opacity=.22),
        "</g>",
        f'<circle cx="256" cy="256" r="146" fill="none" stroke="{p.bar}" stroke-width="5" stroke-opacity=".35"/>',
        _ellipse(112, 384, 58, 24, p.main, opacity=.82, rotate=-35),
        _line(92, 402, 162, 360, p.bar, 3, opacity=.45),
        _ellipse(404, 166, 24, 48, p.main, opacity=.70, rotate=33),
        _sparkle(420, 354, 11, p.main, opacity=.8),
    ])


def art_mothers_day(uid: str, p: Palette) -> str:
    def flower(cx, cy, r, petal, center):
        petals = "".join(
            _circle(cx + math.cos(math.radians(a)) * r * .62, cy + math.sin(math.radians(a)) * r * .62,
                    r * .40, petal, opacity=.96)
            for a in range(0, 360, 72)
        )
        return petals + _circle(cx, cy, r * .28, center)

    wrap = _path("M 190 330 L 322 330 L 286 468 L 226 468 Z", p.main, opacity=.88)
    wrap2 = _path("M 204 330 L 308 330 L 280 438 L 232 438 Z", p.detail, opacity=.28)
    stems = "".join(
        _line(256, 286, x, 350, p.accent3, 7, opacity=.8)
        for x in (202, 256, 310)
    )
    return "".join([
        _circle(256, 244, 190, p.main, opacity=.07),
        stems,
        wrap, wrap2,
        _path("M 196 330 Q 256 348 316 330", p.bar, opacity=.2),
        flower(190, 204, 70, p.main, p.gold),
        flower(322, 196, 64, p.detail, p.gold),
        flower(256, 150, 58, p.accent3, p.gold),
        _heart(256, 382, 28, p.bar, opacity=.82),
        _sparkle(104, 142, 12, p.bar, opacity=.7),
        _sparkle(416, 282, 9, p.main, opacity=.8),
    ])


def art_victoria_day(uid: str, p: Palette) -> str:
    fireworks = []
    for cx, cy, r, color in ((126, 160, 70, p.main), (386, 144, 54, p.detail)):
        for angle in range(0, 360, 30):
            a = math.radians(angle)
            fireworks.append(_line(cx, cy, cx + math.cos(a) * r, cy + math.sin(a) * r, color, 3, opacity=.58))
            fireworks.append(_circle(cx + math.cos(a) * r * 1.12, cy + math.sin(a) * r * 1.12, 3.2, color, opacity=.8))
    return "".join([
        _circle(256, 292, 202, p.main, opacity=.06),
        "".join(fireworks),
        _poly(_maple_points(256, 318, 146), p.main),
        _poly(_maple_points(256, 318, 108), p.main, opacity=.9),
        _line(256, 248, 256, 194, p.main, 8),
        _sparkle(88, 386, 12, p.bar, opacity=.7),
        _sparkle(424, 340, 8, p.main, opacity=.8),
    ])


def art_pride(uid: str, p: Palette) -> str:
    colors = ("#ff5c5c", "#ff9f43", "#ffd166", "#43d17c", "#38bdf8", "#a78bfa")
    bands = []
    for index, color in enumerate(colors):
        r = 188 - index * 25
        bands.append(_arc(256, 400, r, 180, 360, color, 22, opacity=.96))
    return "".join([
        _circle(256, 334, 210, p.main, opacity=.05),
        *bands,
        _cloud(72, 382, 54, p.bar, opacity=.90),
        _cloud(438, 382, 48, p.bar, opacity=.90),
        _sparkle(98, 142, 14, p.main, opacity=.8),
        _sparkle(412, 156, 9, p.bar, opacity=.9),
        _sparkle(256, 126, 7, p.main, opacity=.7),
    ])


def art_fathers_day(uid: str, p: Palette) -> str:
    wrench = "".join([
        _line(120, 408, 372, 168, p.main, 20),
        _path("M 352 170 C 330 154 342 122 368 116 C 386 112 404 124 408 142 L 384 148 L 376 132 L 362 136 L 366 154 Z", p.main),
        _circle(366, 142, 8, p.deep),
    ])
    tie = "".join([
        _poly([(232, 156), (280, 156), (292, 204), (220, 204)], p.main),
        _poly([(220, 214), (292, 214), (320, 420), (256, 458), (192, 420)], p.detail),
        _line(256, 220, 256, 438, p.bar, 2.5, opacity=.23),
        _line(212, 240, 236, 420, p.bar, 2.2, opacity=.15),
        _line(300, 240, 276, 420, p.bar, 2.2, opacity=.15),
    ])
    return "".join([
        _circle(256, 280, 190, p.main, opacity=.06),
        wrench,
        tie,
        _circle(256, 232, 7, p.bar, opacity=.85),
        _sparkle(94, 156, 10, p.main, opacity=.8),
        _sparkle(426, 354, 8, p.bar, opacity=.6),
    ])


def art_juneteenth(uid: str, p: Palette) -> str:
    blue = "#1e3a8a"
    red = "#d7263d"
    white = p.bar
    rays = "".join(
        _line(256, 232, 256 + math.cos(math.radians(a)) * 178, 232 + math.sin(math.radians(a)) * 178,
              white, 3, opacity=.20)
        for a in range(0, 360, 45)
    )
    chain = "".join([
        f'<rect x="{x}" y="{y}" width="27" height="16" rx="8" fill="none" stroke="{white}" stroke-width="4" stroke-opacity=".82" transform="rotate({angle} {x + 13} {y + 8})"/>'
        for x, y, angle in ((152, 400, -15), (182, 390, 16), (212, 402, -12), (300, 402, 13), (330, 390, -16), (360, 400, 12))
    ])
    return "".join([
        _circle(256, 260, 212, blue, opacity=.18),
        _rect(48, 118, 416, 230, 30, blue),
        _rect(48, 330, 416, 130, 30, red),
        _rect(48, 330, 416, 12, 0, white, opacity=.55),
        rays,
        _path("M 74 336 Q 256 236 438 336", white, opacity=.14, extra=f'stroke="{white}" stroke-width="24" stroke-opacity=".28" fill="none"'),
        _star(256, 232, 152, 65, white),
        _rect(128, 438, 256, 16, 8, white, opacity=.24),
        chain,
    ])


def art_canada_day(uid: str, p: Palette) -> str:
    return "".join([
        _rect(0, 0, 96, 512, 0, "#e63946", opacity=.96),
        _rect(416, 0, 96, 512, 0, "#e63946", opacity=.96),
        _rect(96, 0, 320, 512, 0, p.detail, opacity=.94),
        _circle(256, 256, 210, p.main, opacity=.04),
        _poly(_maple_points(256, 280, 148), "#e63946"),
        _poly(_maple_points(256, 280, 112), p.detail, opacity=.18),
        _line(256, 194, 256, 140, "#e63946", 8),
        _sparkle(140, 160, 11, p.bar, opacity=.8),
        _sparkle(376, 362, 8, p.main, opacity=.8),
    ])


def art_independence_day(uid: str, p: Palette) -> str:
    stripes = "".join(
        _path(
            f"M 32 {238 + i * 38} C 152 {198 + i * 38} 360 {198 + i * 38} 480 {238 + i * 38} "
            f"L 480 {260 + i * 38} C 360 {220 + i * 38} 152 {220 + i * 38} 32 {260 + i * 38} Z",
            p.detail if i % 2 == 0 else p.bar, opacity=.62,
        )
        for i in range(5)
    )
    return "".join([
        _circle(256, 254, 204, p.main, opacity=.06),
        stripes,
        _star(256, 254, 154, 66, p.bar),
        _star(256, 254, 116, 49, p.detail, opacity=.88),
        _star(256, 254, 78, 33, p.bar),
        _sparkle(90, 124, 13, p.main, opacity=.9),
        _sparkle(426, 118, 9, p.bar, opacity=.8),
    ])


def art_labor_day(uid: str, p: Palette) -> str:
    teeth = []
    for angle in range(0, 360, 30):
        a = math.radians(angle)
        teeth.append(_rect(256 + math.cos(a) * 148 - 18, 256 + math.sin(a) * 148 - 18, 36, 40, 8, p.main, rotate=angle))
    gear = "".join([
        *teeth,
        _circle(256, 256, 146, p.main),
        _circle(256, 256, 94, p.deep, opacity=.93),
        _circle(256, 256, 44, p.main, opacity=.9),
        f'<circle cx="256" cy="256" r="94" fill="none" stroke="{p.bar}" stroke-width="3" stroke-opacity=".22"/>',
    ])
    wrench = "".join([
        _line(116, 414, 392, 148, p.detail, 18),
        _path("M 376 148 C 354 128 366 98 392 94 C 412 91 430 104 434 124 L 408 130 L 400 114 L 384 118 L 388 138 Z", p.detail),
    ])
    return "".join([
        _circle(256, 256, 206, p.main, opacity=.05),
        gear, wrench,
        _sparkle(92, 116, 10, p.bar, opacity=.75),
        _sparkle(430, 386, 8, p.main, opacity=.8),
    ])


def art_rosh_hashanah(uid: str, p: Palette) -> str:
    apple = "".join([
        _path("M 256 410 C 168 410 120 346 120 270 C 120 198 172 158 226 170 C 242 174 248 180 256 190 C 264 180 270 174 286 170 C 340 158 392 198 392 270 C 392 346 344 410 256 410 Z", "#e14b4b"),
        _path("M 256 408 C 190 398 158 332 164 274 C 170 220 206 190 246 196 C 220 236 214 302 236 350 C 244 370 250 392 256 408 Z", p.main, opacity=.72),
        _line(256, 188, 262, 142, p.main, 9),
        _path("M 260 148 C 300 112 342 118 356 138 C 332 164 292 172 260 148 Z", p.main),
        _line(260, 148, 330, 140, p.bar, 2, opacity=.38),
    ])
    dipper = "".join([
        _line(320, 152, 410, 368, p.main, 8),
        _ellipse(410, 374, 32, 43, p.main, rotate=-8),
        _path("M 386 394 C 396 420 424 420 434 394", "none", extra=f'stroke="{p.gold}" stroke-width="7" stroke-linecap="round"'),
    ])
    honey = "".join(
        _circle(x, y, r, p.gold, opacity=.8)
        for x, y, r in ((422, 424, 5), (410, 440, 4), (430, 452, 3))
    )
    return "".join([
        _circle(256, 270, 196, p.main, opacity=.06),
        _poly(_hexagon(116, 132, 34), p.main, opacity=.16, extra=f'stroke="{p.main}" stroke-width="2" stroke-opacity=".35"'),
        _poly(_hexagon(86, 194, 20), p.main, opacity=.12, extra=f'stroke="{p.main}" stroke-width="2" stroke-opacity=".3"'),
        apple, dipper, honey,
        _sparkle(106, 344, 10, p.bar, opacity=.65),
    ])


def art_diwali(uid: str, p: Palette) -> str:
    rangoli = []
    for index in range(12):
        a = math.radians(index * 30)
        rangoli.append(_ellipse(256 + math.cos(a) * 166, 286 + math.sin(a) * 166, 22, 44, p.main, opacity=.25, rotate=index * 30))
        rangoli.append(_ellipse(256 + math.cos(a) * 132, 286 + math.sin(a) * 132, 14, 29, p.detail, opacity=.32, rotate=index * 30))
    bowl = "".join([
        _path("M 108 318 C 108 404 404 404 404 318 C 366 348 326 360 256 360 C 186 360 146 348 108 318 Z", p.detail),
        _path("M 118 318 C 150 294 362 294 394 318 C 360 338 330 346 256 346 C 182 346 152 338 118 318 Z", p.main, opacity=.94),
    ])
    flame = _flame(256, 228, 62, p.main, p.bar)
    return "".join([
        _circle(256, 250, 202, p.main, opacity=.07),
        "".join(rangoli),
        bowl,
        _line(256, 338, 256, 246, p.main, 10),
        flame,
        _sparkle(116, 160, 13, p.main, opacity=.9),
        _sparkle(400, 150, 9, p.bar, opacity=.8),
        _sparkle(410, 344, 7, p.main, opacity=.8),
    ])


def art_halloween(uid: str, p: Palette) -> str:
    bats = "".join([_bat(118, 148, 34, p.detail, opacity=.85), _bat(390, 118, 24, p.detail, opacity=.8), _bat(424, 304, 17, p.detail, opacity=.65)])
    pumpkin = "".join([
        _ellipse(256, 286, 142, 118, p.main),
        _ellipse(256, 286, 112, 114, p.main, opacity=.55),
        _ellipse(256, 286, 70, 108, p.main, opacity=.35),
        _line(256, 168, 256, 118, p.main, 14),
        _path("M 256 130 C 282 100 318 104 330 118 C 312 144 280 148 256 130 Z", p.main),
        _poly([(180, 242), (222, 242), (201, 278)], p.deep),
        _poly([(290, 242), (332, 242), (311, 278)], p.deep),
        _path("M 178 322 L 208 304 L 238 326 L 256 306 L 274 326 L 304 304 L 334 322 L 318 354 L 286 342 L 274 360 L 256 344 L 238 360 L 226 342 L 194 354 Z", p.deep),
        _circle(156, 286, 13, p.main, opacity=.8),
        _circle(356, 286, 13, p.main, opacity=.8),
    ])
    moon = _path("M 408 404 A 60 60 0 1 1 448 300 A 46 46 0 1 0 408 404 Z", p.bar, opacity=.24)
    return "".join([
        _circle(256, 280, 202, p.main, opacity=.05),
        moon, bats, pumpkin,
        _sparkle(80, 374, 9, p.main, opacity=.8),
    ])


def art_thanksgiving(uid: str, p: Palette) -> str:
    feathers = []
    colors = (p.detail, p.main, p.gold, p.accent2, p.detail, p.main, p.gold)
    for index, color in enumerate(colors):
        angle = 196 + index * 24.5
        a = math.radians(angle)
        cx, cy = 256 + math.cos(a) * 106, 336 + math.sin(a) * 106
        feathers.append(_ellipse(cx, cy, 35, 89, color, opacity=.95, rotate=angle + 90))
        feathers.append(_circle(cx, cy, 8, p.bar, opacity=.16))
    body = "".join([
        *feathers,
        _ellipse(256, 334, 90, 96, p.detail),
        _ellipse(256, 356, 66, 66, p.accent2, opacity=.36),
        _circle(330, 274, 43, p.detail),
        _path("M 318 242 Q 300 198 340 198 Q 358 200 362 220", p.detail),
        _poly([(366, 270), (416, 282), (366, 296)], p.main),
        _path("M 352 300 C 348 326 366 338 380 326", "#d94a3d"),
        _path("M 334 242 C 322 266 330 292 344 284 C 334 274 340 258 348 248", "#d94a3d"),
        _circle(344, 260, 6, p.deep),
        _circle(344, 260, 2.4, p.bar),
        _path("M 174 366 C 196 328 228 334 232 366 C 234 390 208 404 190 390", p.main, opacity=.78),
    ])
    return "".join([
        _circle(256, 300, 206, p.main, opacity=.05),
        body,
        _ellipse(150, 408, 48, 17, p.main, opacity=.48, rotate=-20),
        _ellipse(390, 420, 38, 14, p.detail, opacity=.42, rotate=24),
        _sparkle(92, 150, 10, p.bar, opacity=.62),
    ])


def art_hanukkah(uid: str, p: Palette) -> str:
    candles = []
    for index in range(7):
        offset = (index - 3) * 40
        top = 196 if index == 3 else 224
        color = p.bar if index == 3 else p.main
        candles.append(_rect(256 + offset - 5, top, 10, 150, 5, color))
        candles.append(_flame(256 + offset, top - 28, 18, p.detail, p.bar))
    branches = "".join([
        _stroke_path(f"M 256 356 C {256 + offset * .35:.1f} 356 {256 + offset * .75:.1f} 318 {256 + offset:.1f} 374", p.main, 7)
        for offset in (-120, -80, -40, 40, 80, 120)
    ])
    return "".join([
        _star(256, 232, 188, 81, p.main, opacity=.10),
        branches,
        _rect(96, 382, 320, 16, 8, p.main),
        _rect(174, 366, 164, 20, 10, p.main, opacity=.9),
        *candles,
        _circle(256, 398, 9, p.detail),
        _sparkle(108, 154, 11, p.bar, opacity=.65),
    ])


def art_christmas(uid: str, p: Palette) -> str:
    tree = "".join([
        _poly([(256, 118), (126, 282), (386, 282)], p.green_light),
        _poly([(256, 176), (98, 354), (414, 354)], p.green_mid),
        _poly([(256, 248), (72, 432), (440, 432)], p.green_dark),
        _rect(238, 424, 36, 48, 8, p.deep),
    ])
    ornaments = "".join(
        _circle(x, y, r, color)
        for x, y, r, color in ((210, 270, 12, p.detail), (300, 302, 9, p.gold), (178, 338, 9, p.gold),
                               (332, 356, 12, p.detail), (240, 384, 10, p.gold), (292, 410, 8, p.detail))
    )
    gifts = "".join([
        _rect(88, 410, 72, 66, 7, p.detail),
        _rect(112, 398, 24, 78, 4, p.main, opacity=.8),
        _rect(372, 426, 57, 52, 7, p.main),
        _rect(390, 414, 18, 64, 4, p.gold, opacity=.8),
    ])
    return "".join([
        _circle(256, 290, 210, p.main, opacity=.05),
        tree,
        _star(256, 104, 38, 16, p.gold),
        ornaments,
        gifts,
        _snowflake(102, 148, 18, p.bar, 2.2, opacity=.8),
        _snowflake(422, 196, 12, p.bar, 1.8, opacity=.7),
    ])


def art_kwanzaa(uid: str, p: Palette) -> str:
    candles = []
    for index in range(7):
        offset = (index - 3) * 41
        color = "#17100c" if index == 3 else (p.accent if index < 3 else p.accent2)
        candles.append(_rect(256 + offset - 5, 194, 10, 164, 5, color))
        candles.append(_flame(256 + offset, 166, 18, p.gold, p.bar))
    mat = "".join(
        _rect(44, 380 + index * 14, 424, 10, 0, color)
        for index, color in enumerate((p.detail, p.main, p.accent3, p.detail))
    )
    return "".join([
        _circle(256, 264, 202, p.main, opacity=.05),
        *candles,
        _rect(88, 358, 336, 17, 8, p.main),
        _rect(164, 344, 184, 20, 10, p.main, opacity=.9),
        mat,
        _path("M 378 338 C 392 300 428 300 436 330 C 442 354 414 366 394 352", p.main, opacity=.8),
        _circle(404, 318, 10, p.detail),
        _sparkle(100, 148, 11, p.bar, opacity=.65),
    ])


ART: dict[str, Callable[[str, Palette], str]] = {
    "new-year": art_new_year,
    "lunar-new-year": art_lunar_new_year,
    "valentines": art_valentines,
    "st-patricks": art_st_patricks,
    "holi": art_holi,
    "eid": art_eid,
    "easter": art_easter,
    "passover": art_passover,
    "earth-day": art_earth_day,
    "mothers-day": art_mothers_day,
    "victoria-day": art_victoria_day,
    "pride": art_pride,
    "fathers-day": art_fathers_day,
    "juneteenth": art_juneteenth,
    "canada-day": art_canada_day,
    "independence-day": art_independence_day,
    "labor-day": art_labor_day,
    "rosh-hashanah": art_rosh_hashanah,
    "diwali": art_diwali,
    "halloween": art_halloween,
    "thanksgiving": art_thanksgiving,
    "hanukkah": art_hanukkah,
    "christmas": art_christmas,
    "kwanzaa": art_kwanzaa,
}

ANGLES = {
    "new-year": 158, "lunar-new-year": 22, "valentines": 138, "st-patricks": 104,
    "holi": 48, "eid": 172, "easter": 118, "passover": 78,
    "earth-day": 152, "mothers-day": 24, "victoria-day": 110, "pride": 64,
    "fathers-day": 202, "juneteenth": 136, "canada-day": 92, "independence-day": 20,
    "labor-day": 164, "rosh-hashanah": 72, "diwali": 124, "halloween": 202,
    "thanksgiving": 32, "hanukkah": 88, "christmas": 160, "kwanzaa": 120,
}


def _gradient(uid: str, p: Palette, angle: float) -> str:
    a = math.radians(angle)
    x1 = 50 - math.cos(a) * 50
    y1 = 50 - math.sin(a) * 50
    x2 = 50 + math.cos(a) * 50
    y2 = 50 + math.sin(a) * 50
    return (
        f'<linearGradient id="{uid}-bg" x1="{x1:.1f}%" y1="{y1:.1f}%" x2="{x2:.1f}%" y2="{y2:.1f}%">'
        f'<stop offset="0" stop-color="{p.start}"/><stop offset="1" stop-color="{p.end}"/>'
        "</linearGradient>"
    )


def icon_svg(season: dict, *, maskable: bool = False) -> str:
    uid = season["id"].replace("-", "_")
    p = Palette(season)
    art = ART[season["id"]](uid, p)
    pattern = _pattern(season, p)
    glow = (
        f'<radialGradient id="{uid}-glow">'
        f'<stop offset="0" stop-color="{p.main}" stop-opacity=".30"/>'
        f'<stop offset=".55" stop-color="{p.main}" stop-opacity=".09"/>'
        f'<stop offset="1" stop-color="{p.main}" stop-opacity="0"/>'
        "</radialGradient>"
    )
    pulse = (
        _stroke_path(
            "M 44 426 H 136 L 158 394 L 182 456 L 208 408 L 228 430 H 468",
            p.bar, 9, opacity=.10,
        )
        + _stroke_path(
            "M 44 440 H 152 L 174 416 L 196 462 L 220 432 H 468",
            p.bar, 4, opacity=.07,
        )
    )
    border = "" if maskable else (
        f'<rect x="3" y="3" width="506" height="506" rx="113" fill="none" '
        f'stroke="{p.bar}" stroke-opacity=".08" stroke-width="2"/>'
    )
    if maskable:
        background = f'<rect width="512" height="512" fill="url(#{uid}-bg)"/>'
        wrapper_open = "<g>"
    else:
        background = f'<rect width="512" height="512" rx="{RADIUS}" fill="url(#{uid}-bg)"/>'
        wrapper_open = f'<g clip-path="url(#{uid}-clip)">'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" role="img">'
        f"<defs>{_gradient(uid, p, ANGLES.get(season['id'], 135))}{glow}"
        f'<clipPath id="{uid}-clip"><rect width="512" height="512" rx="{RADIUS}"/></clipPath>'
        f'<filter id="{uid}-shadow" x="-25%" y="-25%" width="150%" height="150%">'
        f'<feDropShadow dx="0" dy="13" stdDeviation="13" flood-color="{p.deep}" flood-opacity=".48"/>'
        f"</filter></defs>"
        f"{wrapper_open}{background}"
        f'<circle cx="256" cy="246" r="228" fill="url(#{uid}-glow)"/>'
        f"{pattern}{pulse}"
        f'<g filter="url(#{uid}-shadow)">{art}</g>'
        f"{border}</g></svg>"
    )
