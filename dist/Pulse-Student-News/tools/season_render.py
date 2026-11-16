#!/usr/bin/env python3
"""Rasterise the seasonal SVG artwork with the local Chrome build.

This is a build-time helper only. The delivered app serves the finished PNGs
and has no Chrome or JavaScript runtime dependency.
"""
from __future__ import annotations

import base64
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.browser_check import CDP, launch_chrome  # noqa: E402
from tools.season_art import icon_svg  # noqa: E402

STAGE_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body { margin: 0; padding: 0; background: transparent; }
#stage { position: absolute; top: 0; left: 0; overflow: hidden; background: transparent; }
#stage svg { display: block; width: 100%; height: 100%; }
</style></head><body><div id="stage"></div></body></html>"""


def _set_svg(cdp: CDP, svg: str, size: int) -> None:
    script = f"""window.setSvg({json.dumps(svg)}, {size})"""
    cdp.js(script)


def _capture(cdp: CDP, size: int) -> bytes:
    result = cdp.call(
        "Page.captureScreenshot",
        format="png",
        clip={"x": 0, "y": 0, "width": size, "height": size, "scale": 1},
        captureBeyondViewport=True,
        omitBackground=True,
    )
    return base64.b64decode(result["data"])


def render_seasons(seasons, out_root: Path, *, log=print) -> None:
    """Write icon-192/512, maskable and apple-touch PNGs for every season."""
    out_root = Path(out_root)
    template = STAGE_HTML.replace('id="stage"></div>', 'id="stage"></div>')
    # Add the promise helper once, before any icon is rendered.
    template = template.replace(
        "</body>",
        """<script>
window.setSvg = (svg, size) => new Promise((resolve) => {
  const stage = document.getElementById('stage');
  stage.style.width = stage.style.height = size + 'px';
  stage.innerHTML = svg;
  requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
});
</script></body>""",
    )
    with tempfile.TemporaryDirectory(prefix="pulse-season-render-", ignore_cleanup_errors=True) as tmp:
        page = Path(tmp) / "render.html"
        page.write_text(template, encoding="utf-8")
        chrome, ws = launch_chrome(9642, Path(tmp) / "chrome")
        try:
            cdp = CDP(ws)
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Emulation.setDeviceMetricsOverride", width=1200, height=1200, deviceScaleFactor=1, mobile=False)
            cdp.call("Page.navigate", url=page.as_uri())
            time.sleep(0.7)
            total = len(seasons)
            for index, season in enumerate(seasons, start=1):
                ident = season["id"]
                directory = out_root / ident
                directory.mkdir(parents=True, exist_ok=True)
                rounded = icon_svg(season)
                full = icon_svg(season, maskable=True)
                (directory / "icon.svg").write_text(rounded, encoding="utf-8")
                (directory / "icon-maskable.svg").write_text(full, encoding="utf-8")

                for size, name, svg in (
                    (512, "icon-512.png", rounded),
                    (192, "icon-192.png", rounded),
                    (512, "icon-maskable.png", full),
                    (180, "apple-touch-icon.png", full),
                ):
                    _set_svg(cdp, svg, size)
                    (directory / name).write_bytes(_capture(cdp, size))
                log(f"[{index:02d}/{total}] {ident}")
        finally:
            chrome.terminate()
            try:
                chrome.wait(timeout=10)
            except Exception:
                chrome.kill()


if __name__ == "__main__":
    from pulse.holidays import SEASONS

    render_seasons(SEASONS, ROOT / "pulse" / "static" / "icons" / "seasons" / "v28")
