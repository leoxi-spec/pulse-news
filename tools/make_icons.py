#!/usr/bin/env python3
"""Generate Pulse app icons as PNGs using only the standard library."""
import struct
import math
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "pulse" / "static" / "icons"


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded_rect(x, y, w, h, radius, px, py):
    if x + radius <= px <= x + w - radius or y + radius <= py <= y + h - radius:
        inside_x = x <= px <= x + w
        inside_y = y <= py <= y + h
        if inside_x and inside_y:
            return True
    for cx, cy in ((x + radius, y + radius), (x + w - radius, y + radius),
                   (x + radius, y + h - radius), (x + w - radius, y + h - radius)):
        if (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2:
            return True
    return x <= px <= x + w and y <= py <= y + h and (
        (x + radius <= px <= x + w - radius) or (y + radius <= py <= y + h - radius)
    )


def _blend(base, over, alpha):
    alpha = max(0.0, min(1.0, alpha))
    return tuple(round(base[i] + (over[i] - base[i]) * alpha) for i in range(3))


def _circle(px, py, cx, cy, radius):
    return (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2


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


def _star_points(cx, cy, outer, inner, points=5):
    import math
    result = []
    for index in range(points * 2):
        angle = -math.pi / 2 + index * math.pi / points
        radius = outer if index % 2 == 0 else inner
        result.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return result


def _snowflake(px, py, cx, cy, radius):
    """Six-spoke snowflake, drawn as thin lines without a graphics library."""
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


def draw(size: int, *, padding: float = 0.0, transparent: bool = False) -> bytearray:
    """Christmas Pulse icon: evergreen/crimson tile, snowy bars, gold star."""
    if transparent:
        bg = (10, 12, 17)
    else:
        bg = lerp((12, 60, 43), (119, 27, 39), 0.38)
    start = (12, 60, 43)       # deep pine
    end = (119, 27, 39)        # Christmas crimson
    snow = (255, 250, 242)
    gold = (247, 201, 72)
    red = (243, 78, 91)
    pixels = bytearray()
    inset = int(size * padding)
    tile = (inset, inset, size - inset, size - inset)
    radius = int((tile[2] - tile[0]) * 0.23)
    bars = [0.38, 0.65, 0.95, 0.78, 0.50]

    # Centred in the tile; scaled to fit the safe area.
    fit = 0.82
    bar_w = max(2, round(size * 0.160 * fit))
    gap = max(1, round(size * 0.042 * fit))
    total_w = len(bars) * bar_w + (len(bars) - 1) * gap
    left = (size - total_w) // 2
    max_bar = int(size * 0.9600 * fit)
    baseline = int(size * (0.5 + (0.9600 * fit * 0.95) / 2))

    tallest_top = baseline - int(max_bar * 0.95)
    star_cx = left + 2 * (bar_w + gap) + bar_w / 2
    star_cy = tallest_top - max(3, int(size * 0.035))
    star_r = max(5, int(size * 0.058))
    star = _star_points(star_cx, star_cy, star_r, star_r * 0.42)
    ornament_r = max(2, int(size * 0.014))
    ornaments = [
        (left + (bar_w + gap) + bar_w / 2, baseline - int(max_bar * 0.65 * 0.52), red),
        (left + 2 * (bar_w + gap) + bar_w / 2, baseline - int(max_bar * 0.95 * 0.40), gold),
        (left + 3 * (bar_w + gap) + bar_w / 2, baseline - int(max_bar * 0.78 * 0.55), red),
    ]
    snowflakes = [
        (int(size * 0.875), int(size * 0.17), max(2, int(size * 0.030))),
        (int(size * 0.945), int(size * 0.74), max(2, int(size * 0.024))),
        (int(size * 0.075), int(size * 0.22), max(2, int(size * 0.017))),
    ]

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

            # A soft gold halo around the tree-topper star.
            dx, dy = x - star_cx, y - star_cy
            halo = (dx * dx + dy * dy) ** 0.5
            if halo < star_r * 3.0:
                color = _blend(color, gold, 0.10 * (1 - halo / (star_r * 3.0)))

            # Snowflakes sit behind the waveform.
            for fx, fy, fr in snowflakes:
                if _snowflake(x, y, fx, fy, fr):
                    color = _blend(color, snow, 0.72)
                    break

            # Five snowy pulse bars.
            in_bar = False
            for index, height in enumerate(bars):
                bx = left + index * (bar_w + gap)
                bh = int(max_bar * height)
                by = baseline - bh
                if rounded_rect(bx, by, bar_w, bh, bar_w // 2, x, y):
                    color = snow
                    in_bar = True
                    break

            # Baubles on the bars.
            for ox, oy, ornament in ornaments:
                if _circle(x, y, ox, oy, ornament_r):
                    color = ornament
                    break

            # Gold star, with a warmer centre.
            if _polygon(x, y, star):
                color = gold
                if _circle(x, y, star_cx, star_cy, max(1, star_r * 0.22)):
                    color = (255, 235, 160)

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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        pixels = draw(size)
        write_png(OUT / f"icon-{size}.png", size, pixels, size, size)
    # Maskable icon: same art with safe padding on an opaque background.
    size = 512
    pixels = draw(size)
    write_png(OUT / "icon-maskable.png", size, pixels, size, size)
    # Apple touch icon
    pixels = draw(180)
    write_png(OUT / "apple-touch-icon.png", 180, pixels, 180, 180)
    (OUT / "icon.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="Pulse — Christmas edition">
  <defs>
    <linearGradient id="pine" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0c3c2b"/>
      <stop offset="1" stop-color="#771b27"/>
    </linearGradient>
    <radialGradient id="glow" cx="32" cy="6" r="12" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#f7c948" stop-opacity=".22"/>
      <stop offset="1" stop-color="#f7c948" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="64" height="64" rx="15" fill="url(#pine)"/>
  <rect width="64" height="64" rx="15" fill="url(#glow)"/>
  <g stroke="#fffaf2" stroke-opacity=".72" stroke-width=".42" stroke-linecap="round">
    <g transform="translate(56 11)"><path d="M-2 0H2M-1-1.73 1 1.73M-1 1.73 1-1.73"/></g>
    <g transform="translate(4.8 14.1)"><path d="M-1.2 0H1.2M-.6-1.04 1.04-.6M-.6 1.04 1.04.6"/></g>
    <g transform="translate(60.5 47)"><path d="M-1.5 0H1.5M-.75-1.3 1.3-0.75M-.75 1.3 1.3 0.75"/></g>
  </g>
  <g fill="#fffaf2" transform="translate(5.333 0)">
    <rect x="1.25" y="36.75" width="8.375" height="19.125" rx="4.1875"/>
    <rect x="11.875" y="23.25" width="8.375" height="32.625" rx="4.1875"/>
    <rect x="22.5" y="8.125" width="8.375" height="47.75" rx="4.1875"/>
    <rect x="33.125" y="16.625" width="8.375" height="39.25" rx="4.1875"/>
    <rect x="43.75" y="30.75" width="8.375" height="25.125" rx="4.1875"/>
  </g>
  <g transform="translate(5.333 0)">
    <circle cx="16.062" cy="38.875" r=".875" fill="#f34e5b"/>
    <circle cx="26.688" cy="36.75" r=".875" fill="#f7c948"/>
    <circle cx="37.312" cy="34.375" r=".875" fill="#f34e5b"/>
  </g>
  <g fill="#f7c948" transform="translate(5.333 0)">
    <polygon points="26.688,2.375 27.583,4.768 30.136,4.88 28.136,6.47 28.819,8.933 26.688,7.522 24.557,8.933 25.24,6.47 23.24,4.88 25.793,4.768"/>
    <circle cx="26.688" cy="6" r=".7" fill="#ffeba0"/>
  </g>
</svg>
""",
        encoding="utf-8",
    )
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
