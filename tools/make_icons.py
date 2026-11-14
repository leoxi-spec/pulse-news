#!/usr/bin/env python3
"""Generate Pulse app icons as PNGs using only the standard library."""
import struct
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


def draw(size: int, *, padding: float = 0.0, transparent: bool = False) -> bytearray:
    """Violet→pink rounded tile with a white pulse waveform."""
    bg = (10, 12, 17) if transparent else lerp((124, 92, 255), (255, 77, 141), 0.35)
    start = (124, 92, 255)
    end = (255, 77, 141)
    pixels = bytearray()
    inset = int(size * padding)
    tile = (inset, inset, size - inset, size - inset)
    radius = int((tile[2] - tile[0]) * 0.23)
    bars = [0.38, 0.65, 0.95, 0.78, 0.50]  # relative heights of the pulse
    # 1.25x larger than the v9 artwork.  Keep the left edge anchored so the
    # wider mark grows into the available space instead of clipping.
    # Fill the square icon: the previous mark was already 75% of the height,
    # so a literal 1.5x linear scale would leave the canvas.  This is the
    # largest safe enlargement (about 1.5x the visual area).
    bar_w = max(2, round(size * 0.124))
    gap = max(1, round(size * 0.032))
    total_w = len(bars) * bar_w + (len(bars) - 1) * gap
    left = int(size * 0.4775 - total_w / 2)
    baseline = int(size * 0.875)
    max_bar = int(size * 0.75)

    for y in range(size):
        row = bytearray()
        for x in range(size):
            if not transparent and not rounded_rect(*tile, radius, x, y) and not (tile[0] <= x <= tile[2] and tile[1] <= y <= tile[3]):
                row += b"\x00\x00\x00\x00"
                continue
            t = ((x - tile[0]) + (y - tile[1])) / max(1, (tile[2] - tile[0]) + (tile[3] - tile[1]))
            color = lerp(start, end, min(1.0, max(0.0, t)))
            if not transparent and not rounded_rect(*tile, radius, x, y):
                row += b"\x00\x00\x00\x00"
                continue
            alpha = 255
            for index, height in enumerate(bars):
                bx = left + index * (bar_w + gap)
                bh = int(max_bar * height)
                by = baseline - bh
                if rounded_rect(bx, by, bar_w, bh, bar_w // 2, x, y):
                    color = (255, 255, 255)
                    break
            row += bytes((*color, alpha))
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
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="Pulse">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#7c5cff"/><stop offset="1" stop-color="#ff4d8d"/>
  </linearGradient></defs>
  <rect width="64" height="64" rx="15" fill="url(#g)"/>
  <g fill="#fff" transform="translate(32,32) scale(0.8) translate(-32,-32)">
    <rect x="0.5" y="39.2" width="10" height="22.8" rx="5"/>
    <rect x="13" y="23" width="10" height="39" rx="5"/>
    <rect x="25.5" y="5" width="10" height="57" rx="5"/>
    <rect x="38" y="15.2" width="10" height="46.8" rx="5"/>
    <rect x="50.5" y="32" width="10" height="30" rx="5"/>
  </g>
</svg>
""",
        encoding="utf-8",
    )
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
