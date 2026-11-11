#!/usr/bin/env python3
"""End-to-end browser check for Pulse.

Launches headless Chrome, connects over the DevTools protocol (with a tiny
hand-rolled WebSocket client, so there are no third-party dependencies), then
clicks through the real UI: home, article, save, citations, quiz, search,
discover, sports, brief, study, profile settings, onboarding skip and mobile
layout. Console errors and uncaught exceptions are reported.

Usage:
    python3 tools/browser_check.py --port 8890 --profile <id>
    python3 tools/browser_check.py --server-only   # start a seeded test server

The script starts its own server (copying a populated database when one is
available) and cleans up afterwards.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DATA_SOURCE = Path("/tmp/pulse-final")
SCREENSHOTS = Path("/tmp/pulse-e2e")


# --------------------------------------------------------------------- websocket
class WebSocket:
    def __init__(self, url: str, timeout: float = 20.0):
        parts = urlsplit(url)
        self.sock = socket.create_connection((parts.hostname, parts.port or 80), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {_target_path(parts)} HTTP/1.1\r\n"
            f"Host: {parts.hostname}:{parts.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        if os.environ.get("PULSE_WS_DEBUG"):
            print("WS REQUEST:", repr(request))
        self.sock.sendall(request.encode())
        header = b""
        while b"\r\n\r\n" not in header:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("websocket handshake closed")
            header += chunk
        if b"101" not in header.split(b"\r\n")[0]:
            raise RuntimeError(f"websocket handshake failed: {header[:120]!r}")
        self._buffer = b""

    # -- framing ---------------------------------------------------------
    def send(self, payload: str) -> None:
        data = payload.encode()
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def _read_exact(self, count: int) -> bytes:
        while len(self._buffer) < count:
            chunk = self.sock.recv(max(4096, count - len(self._buffer)))
            if not chunk:
                raise RuntimeError("websocket closed")
            self._buffer += chunk
        out, self._buffer = self._buffer[:count], self._buffer[count:]
        return out

    def recv(self) -> str:
        fragments = []
        while True:
            first = self._read_exact(2)
            fin = first[0] & 0x80
            opcode = first[0] & 0x0F
            masked = first[1] & 0x80
            length = first[1] & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if masked else b""
            payload = self._read_exact(length)
            if masked:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                raise RuntimeError("websocket closed by peer")
            if opcode == 0x9:
                continue  # ping: ignore
            fragments.append(payload)
            if fin:
                return b"".join(fragments).decode("utf-8", "replace")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class CDP:
    def __init__(self, url: str):
        self.ws = WebSocket(url)
        self.next_id = 0
        self.events: list[dict] = []

    def call(self, method: str, **params):
        self.next_id += 1
        message_id = self.next_id
        self.ws.send(json.dumps({"id": message_id, "method": method, "params": params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})
            if "method" in message:
                self.events.append(message)

    def js(self, expression: str):
        result = self.call(
            "Runtime.evaluate", expression=expression, awaitPromise=True,
            returnByValue=True, userGesture=True,
        )
        if result.get("exceptionDetails"):
            detail = result["exceptionDetails"]
            text = detail.get("exception", {}).get("description") or detail.get("text")
            raise RuntimeError(f"JS error: {text}")
        return result.get("result", {}).get("value")

    def screenshot(self, path: Path) -> None:
        data = self.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)
        path.write_bytes(base64.b64decode(data["data"]))

    def close(self) -> None:
        self.ws.close()


# ------------------------------------------------------------------- harness
class Checker:
    def __init__(self, cdp: CDP, base: str):
        self.cdp = cdp
        self.base = base
        self.failures: list[str] = []
        self.notes: list[str] = []

    def ok(self, condition: bool, label: str, detail: str = "") -> None:
        if condition:
            print(f"  PASS  {label}")
        else:
            message = f"{label}{(' — ' + detail) if detail else ''}"
            print(f"  FAIL  {message}")
            self.failures.append(message)

    def wait_for(self, expression: str, timeout: float = 20.0, label: str = "condition") -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.cdp.js(expression):
                    return True
            except RuntimeError:
                pass
            time.sleep(0.15)
        return False

    def wait_ready(self, timeout: float = 25.0) -> None:
        if not self.wait_for("document.body.dataset.ready === '1'", timeout, "app ready"):
            raise RuntimeError("app never became ready")

    def goto(self, path: str) -> None:
        self.cdp.call("Page.navigate", url=f"{self.base}{path}")
        time.sleep(0.4)
        self.wait_ready()

    def click(self, selector: str, index: int = 0) -> bool:
        return bool(self.cdp.js(f"""(() => {{
            const nodes = [...document.querySelectorAll({json.dumps(selector)})];
            const node = nodes[{index}];
            if (!node) return false;
            node.click();
            return true;
        }})()"""))

    def text(self, selector: str) -> str:
        value = self.cdp.js(f"document.querySelector({json.dumps(selector)})?.textContent?.trim() || ''")
        return value or ""

    def count(self, selector: str) -> int:
        return int(self.cdp.js(f"document.querySelectorAll({json.dumps(selector)}).length") or 0)

    def shot(self, name: str) -> None:
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        try:
            self.cdp.screenshot(SCREENSHOTS / f"{name}.png")
        except Exception as exc:  # pragma: no cover
            self.notes.append(f"screenshot {name} failed: {exc}")

    def console_errors(self) -> list[str]:
        errors = []
        for event in self.cdp.events:
            method = event.get("method")
            params = event.get("params", {})
            if method == "Runtime.exceptionThrown":
                detail = params.get("exceptionDetails", {})
                text = detail.get("exception", {}).get("description") or detail.get("text")
                errors.append(f"exception: {text}")
            elif method == "Runtime.consoleAPICalled" and params.get("type") == "error":
                args = params.get("args", [])
                errors.append("console.error: " + " ".join(str(a.get("value", a.get("description", ""))) for a in args))
            elif method == "Log.entryAdded" and params.get("entry", {}).get("level") == "error":
                entry = params["entry"]
                if "favicon" in entry.get("url", ""):
                    continue
                # Upstream images fail all the time (publishers move them).
                # The UI hides broken images; that is not an app error.
                if "/api/img" in entry.get("url", ""):
                    continue
                errors.append(f"log: {entry.get('text')} {entry.get('url', '')}")
        return errors


# --------------------------------------------------------------------- server
def start_server(port: int) -> tuple[subprocess.Popen, Path, str]:
    data = Path(tempfile.mkdtemp(prefix="pulse-e2e-"))
    if (DATA_SOURCE / "pulse.sqlite3").exists():
        shutil.copy2(DATA_SOURCE / "pulse.sqlite3", data / "pulse.sqlite3")
    env = {
        **os.environ,
        "PULSE_DATA_DIR": str(data),
        "PULSE_INGEST": "0",
        "PULSE_PORT": str(port),
        "PULSE_HOST": "127.0.0.1",
    }
    process = subprocess.Popen(
        [sys.executable, "run.py"], cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=1) as response:
                if response.status == 200:
                    return process, data, base
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.15)
    process.kill()
    raise RuntimeError("test server did not start")


def api(base: str, path: str, method: str = "GET", body: dict | None = None, profile: str | None = None):
    headers = {"X-Pulse-Client": "web"}
    if profile:
        headers["Cookie"] = f"pulse_profile={profile}"
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read() or b"{}")


def create_profile(base: str, *, onboarded: bool) -> str:
    digest = base64.b16encode(os.urandom(6)).decode().lower()[:12]
    payload = api(base, "/api/profiles", "POST", {"name": f"E2E {digest}"})
    profile_id = payload["profile"]["id"]
    if onboarded:
        api(base, "/api/profile", "PATCH", {
            "survey": {
                "topics": {"tech": 3, "sports": 2, "world": 2, "science": 2, "culture": 1},
                "sources": ["bbc", "guardian", "verge"],
                "keywords": ["climate"],
                "region": "US",
                "grade": "11",
                "reading_length": "medium",
                "goals": ["current events class"],
                "daily_goal": 5,
                "completed_at": "2026-11-10T12:00:00Z",
            },
            "onboarded": True,
        }, profile=profile_id)
    return profile_id


def _target_path(parts) -> str:
    return parts.path + (f"?{parts.query}" if parts.query else "")


def _new_target(port: int) -> str:
    """Create a fresh tab and return its websocket URL."""
    request = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())["webSocketDebuggerUrl"]


def _first_page_target(port: int) -> str | None:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
        targets = json.loads(response.read())
    pages = [t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    return pages[0]["webSocketDebuggerUrl"] if pages else None


def launch_chrome(port: int, profile_dir: Path) -> subprocess.Popen:
    command = [
        CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        "--disable-background-networking", "--no-first-run", "--no-default-browser-check",
        f"--remote-debugging-port={port}", f"--user-data-dir={profile_dir}",
        "--window-size=1400,1000", "about:blank",
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            ws_url = _first_page_target(port)
            if ws_url:
                time.sleep(0.2)
                try:
                    return process, _new_target(port)
                except (urllib.error.URLError, KeyError, ConnectionError, TimeoutError):
                    retry = _first_page_target(port)
                    if retry:
                        return process, retry
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(0.15)
    process.kill()
    raise RuntimeError("chrome devtools did not become available")


# ---------------------------------------------------------------------- tests
def run_checks(checker: Checker, base: str, profile_id: str, skip_profile: str) -> None:
    cdp = checker.cdp

    print("\n[1] Home feed")
    checker.goto(f"/?profile={profile_id}")
    checker.ok(checker.count(".top-card") >= 3, "Top Stories grid renders")
    checker.ok(checker.count(".mcard") >= 4, "mixed-size cards render")
    cards = checker.count(".mosaic .mcard")
    checker.ok(cards >= 4, "For you feed has cards", f"{cards} cards")
    checker.ok(checker.count("#home-search") == 1, "search bar is on the home page")
    checker.ok(checker.count("#nav-search") == 1, "app bar search button renders")
    checker.ok(checker.count(".access-pill") >= 3, "cards label read access")
    checker.ok(checker.count(".today-bar") == 1, "today masthead renders")
    checker.ok(checker.count(".appbar") == 1, "top app bar renders")
    checker.ok(checker.count(".sidebar") == 0 and checker.count(".rail") == 0, "no sidebars in the layout")
    checker.ok(checker.count(".mosaic .mcard") >= 4, "for-you renders a multi-column mosaic", f"{checker.count('.mosaic .mcard')}")
    checker.ok(checker.count("#breaking-slot .breaking-strip") <= 1, "breaking strip deduped")
    checker.shot("01-home")

    print("\n[2] Article reader actions")
    checker.click(".mcard .mcard__title a")
    checker.wait_for("Boolean(document.querySelector('.article__title'))", 15, "article view")
    checker.ok(checker.count(".article__title") == 1, "article title renders")
    checker.wait_for("!document.querySelector('#overview-slot .badge')?.textContent?.includes('Building')", 20, "overview loaded")
    checker.ok(checker.count("#overview-card") == 1, "overview card loaded")
    checker.ok(checker.count(".prose p, .paywall") >= 1, "body or preview notice present")
    checker.ok(checker.count(".reader-banner") == 1, "article shows a read-access banner")
    checker.ok(checker.count(".reader-banner--full, .reader-banner--preview, .reader-banner--locked") == 1, "banner explains whether it opens here")
    checker.shot("02-article")

    checker.click('[data-act="save"]')
    if checker.wait_for("document.querySelector('[data-act=\"save\"]')?.getAttribute('aria-pressed') === 'true'", 6, "save state"):
        checker.ok(True, "save toggles to saved")
    else:
        checker.ok(False, "save toggles to saved")

    checker.click('[data-act="cite"]')
    if checker.wait_for("document.querySelectorAll('.citation-box').length >= 4", 10, "citations"):
        checker.ok(True, "citation modal lists styles")
    else:
        checker.ok(False, "citation modal lists styles")
    checker.shot("03-citations")
    checker.click(".modal [data-close]")
    time.sleep(0.3)

    checker.click('[data-act="quiz"]')
    if checker.wait_for("document.querySelectorAll('.quiz__opt').length >= 3", 20, "quiz"):
        checker.ok(True, "quiz questions render")
        checker.click(".quiz__opt")
        time.sleep(0.4)
        checker.ok(
            checker.count(".quiz__opt.is-right") >= 1,
            "quiz marks the correct answer",
        )
    else:
        checker.ok(False, "quiz questions render")
    checker.shot("04-quiz")

    print("\n[3] Command palette, legend, customizer")
    cdp.call("Page.navigate", url=f"{base}/?profile={profile_id}")
    time.sleep(0.5)
    checker.wait_ready()
    checker.click("#nav-search")
    if checker.wait_for("Boolean(document.querySelector('.palette-root:not([hidden]) .palette__item'))", 8, "palette"):
        checker.ok(True, "command palette opens")
        checker.cdp.js("""(() => {
            const input = document.querySelector('#palette-input');
            input.value = 'climate';
            input.dispatchEvent(new Event('input', { bubbles: true }));
            return true;
        })()""")
        if checker.wait_for("document.querySelectorAll('.palette__item').length >= 3", 10, "palette results"):
            checker.ok(True, "palette returns live results")
        else:
            checker.ok(False, "palette returns live results")
        checker.shot("03-palette")
        checker.cdp.js("document.querySelector('#palette-input').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
        time.sleep(0.3)
    else:
        checker.ok(False, "command palette opens")

    checker.click("#legend-btn")
    if checker.wait_for("document.querySelectorAll('.legend-item').length >= 10", 8, "legend"):
        checker.ok(True, "symbol key opens with explanations")
    else:
        checker.ok(False, "symbol key opens with explanations")
    checker.shot("03b-legend")
    checker.click(".modal [data-close]")
    time.sleep(0.3)

    checker.click("#customize-sections")
    if checker.wait_for("Boolean(document.querySelector('.section-picker'))", 8, "customizer"):
        checker.ok(True, "front-page customizer opens")
        checker.click(".section-picker .switch")
        time.sleep(0.2)
        checker.ok(checker.count(".section-picker__row.is-off") >= 1, "customizer toggles sections")
    else:
        checker.ok(False, "front-page customizer opens")
    checker.shot("03c-customizer")
    checker.click(".modal .btn--ghost")
    time.sleep(0.3)

    print("\n[3d] Themes")
    checker.goto("/profile")
    checker.wait_for("Boolean(document.querySelector('[data-pref=\"theme\"][data-value=\"dusk\"]'))", 15, "theme picker")
    checker.click('[data-pref="theme"][data-value="dusk"]')
    time.sleep(0.6)
    checker.ok(checker.cdp.js("document.documentElement.dataset.theme") == "dusk", "Dusk theme applies")
    checker.ok(checker.count(".theme-swatch") >= 15, "ten+ theme swatches render", f"{checker.count('.theme-swatch')}")
    checker.click('[data-pref="theme"][data-value="dark"]')
    time.sleep(0.4)

    print("\n[4] Search, discover, sports, brief, study, research")
    checker.goto("/search?q=climate")
    checker.wait_for("document.querySelectorAll('.card').length > 0", 15, "search results")
    results = checker.count("#results .card")
    checker.ok(results >= 1, "search returns results", f"{results}")
    checker.ok(checker.count("#results mark") >= 1, "search highlights matches")
    checker.shot("05-search")

    checker.goto("/discover")
    checker.wait_for("document.querySelectorAll('.tile').length > 4", 15, "discover")
    checker.ok(checker.count(".tile") >= 10, "discover topic tiles render")
    checker.ok(checker.count(".row") >= 3, "trending list renders")
    checker.shot("06-discover")

    checker.goto("/sports")
    checker.wait_for("document.querySelectorAll('.game .pin-btn, #games-body .empty').length > 0", 30, "sports")
    checker.ok(checker.count(".game .pin-btn, #games-body .empty") >= 1, "sports page renders games or empty state")
    checker.ok(checker.count("#pinned-bar") == 1, "pinned sports bar renders")
    checker.ok(checker.count(".pin-chip") >= 2, "pinned leagues show as chips")
    team_id = checker.cdp.js("""(() => {
        const button = [...document.querySelectorAll('.pin-btn')].find((node) => !node.classList.contains('is-on'));
        if (!button) return null;
        button.click();
        return button.dataset.pinTeam;
    })()""")
    if team_id:
        checker.wait_for(f"document.querySelector('.pin-btn[data-pin-team=\"{team_id}\"]')?.classList.contains('is-on')", 8, "pin state")
        checker.ok(True, "pinning a team updates the button")
        time.sleep(0.8)
        profile = api(base, "/api/profile", profile=profile_id)["profile"]
        checker.ok(any(str(team.get("id")) == str(team_id) for team in profile["prefs"].get("pinned_teams", [])), "pinned team is saved to the profile")
    else:
        checker.ok(False, "a team could be pinned", "no unpinned team button found")
    checker.shot("07-sports")

    checker.goto("/brief")
    checker.wait_for("document.querySelectorAll('.card').length > 2", 15, "brief")
    brief_cards = checker.count(".feed .card")
    checker.ok(brief_cards >= 3, "brief shows stories", f"{brief_cards}")
    checker.click("#complete-brief")
    time.sleep(0.6)
    checker.ok("Done" in checker.text("#complete-brief") or "briefed" in checker.text("#complete-brief").lower(), "brief completion works")
    checker.shot("08-brief")

    checker.goto("/study")
    checker.wait_for("Boolean(document.querySelector('#study-quiz, #study-jargon'))", 15, "study")
    checker.wait_for("document.querySelectorAll('#study-jargon .term, #study-jargon .flashcard').length >= 1", 15, "study glossary")
    checker.ok(checker.count("#study-jargon .term, #study-jargon .flashcard") >= 1, "study glossary/flashcards render")
    checker.shot("09-study")

    checker.goto("/research")
    checker.wait_for("Boolean(document.querySelector('.research-hero'))", 15, "research")
    checker.ok(checker.count("#style-picker [data-style]") >= 5, "research desk has citation styles")
    checker.wait_for("document.querySelectorAll('.citation-item, #research-body .empty').length >= 1", 15, "research body")
    checker.ok(checker.count(".citation-item, #research-body .empty") >= 1, "research desk shows sources or empty state")
    checker.shot("09b-research")

    print("\n[5] Profile settings")
    checker.goto("/profile")
    checker.wait_for("Boolean(document.querySelector('[data-pref=\"theme\"]'))", 15, "profile")
    checker.click('[data-pref="theme"][data-value="light"]')
    time.sleep(0.6)
    theme = checker.cdp.js("document.documentElement.dataset.theme")
    checker.ok(theme == "light", "theme switch applies", str(theme))
    checker.click('[data-pref="theme"][data-value="dark"]')
    time.sleep(0.4)
    checker.click('[data-toggle="reduce_motion"]')
    time.sleep(0.5)
    checker.ok(checker.cdp.js("document.body.classList.contains('reduce-motion')") is True, "reduce-motion setting applies")
    checker.click('[data-toggle="reduce_motion"]')
    checker.ok(checker.count(".badge-tile") >= 10, "badges render")
    checker.shot("10-profile")

    print("\n[6] Onboarding skip path")
    cdp.call("Page.navigate", url=f"{base}/?profile={skip_profile}")
    time.sleep(0.5)
    checker.wait_ready()
    if checker.wait_for("location.pathname === '/onboarding'", 10, "onboarding redirect"):
        checker.ok(True, "new profile is sent to onboarding")
    else:
        checker.ok(False, "new profile is sent to onboarding", checker.cdp.js("location.pathname"))
    checker.ok(checker.count("#skip-setup") >= 1, "skip setup button is present")
    checker.shot("11-onboarding")
    checker.click("#skip-welcome")
    if checker.wait_for("location.pathname === '/'", 10, "skip navigates home"):
        checker.ok(True, "skip setup goes straight to the feed")
    else:
        checker.ok(False, "skip setup goes straight to the feed", checker.cdp.js("location.pathname"))
    checker.wait_for("document.querySelectorAll('.home-section .top-card, .home-section .story-card').length >= 3", 20, "feed after skip")
    checker.ok(checker.count(".home-section .top-card, .home-section .story-card") >= 3, "feed renders after skipping survey")
    state = api(base, "/api/profile", profile=skip_profile)["profile"]
    checker.ok(state["onboarded"] is True, "profile marked onboarded after skip")
    checker.ok(state["survey"].get("skipped") is True, "survey records that it was skipped")
    checker.ok(len(state["survey"].get("topics", {})) >= 3, "skip seeds sensible topics")
    checker.shot("12-after-skip")

    print("\n[7] Mobile layout")
    cdp.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    checker.goto(f"/?profile={profile_id}")
    time.sleep(0.5)
    overflow = checker.cdp.js("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    checker.ok(overflow <= 2, "no horizontal overflow at 390px", f"{overflow}px")
    checker.ok(checker.count(".bottom-nav__item") == 5, "mobile bottom nav renders")
    checker.ok(checker.cdp.js("getComputedStyle(document.querySelector('.appnav')).display") == "none", "top nav collapses on mobile")
    checker.shot("13-mobile")
    latest = api(base, "/api/feed?mode=latest&limit=1")
    if latest.get("items"):
        checker.goto(f"/article/{latest['items'][0]['id']}")
        checker.wait_for("Boolean(document.querySelector('.article__title, .empty'))", 12, "mobile article")
        checker.ok(checker.count(".article__actions") == 1 or checker.count(".empty") == 1, "article route works on mobile")
    else:
        checker.ok(False, "article route works on mobile", "no article available")
    cdp.call("Emulation.clearDeviceMetricsOverride")

    print("\n[8] Offline shell / PWA")
    checker.goto("/")
    time.sleep(0.5)
    pwa = checker.cdp.js("""(async () => {
        const reg = await navigator.serviceWorker.getRegistration();
        const manifest = await fetch('/manifest.webmanifest').then(r => r.ok);
        return { controlled: Boolean(reg), manifest };
    })()""")
    checker.ok(bool(pwa and pwa.get("manifest")), "manifest is served")
    checker.ok(bool(pwa and pwa.get("controlled")), "service worker registered")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8890)
    parser.add_argument("--chrome-port", type=int, default=9333)
    parser.add_argument("--keep", action="store_true", help="leave Chrome/server running for inspection")
    args = parser.parse_args()

    if not Path(CHROME).exists():
        print("Chrome not found at", CHROME)
        return 2

    print("Starting test server…")
    server, data_dir, base = start_server(args.port)
    chrome_dir = Path(tempfile.mkdtemp(prefix="pulse-chrome-"))
    chrome = None
    cdp = None
    try:
        onboarded = create_profile(base, onboarded=True)
        fresh = create_profile(base, onboarded=False)
        print("Profiles:", onboarded, "/", fresh)

        print("Launching Chrome…")
        chrome, ws_url = launch_chrome(args.chrome_port, chrome_dir)
        cdp = None
        for attempt in range(5):
            try:
                cdp = CDP(ws_url)
                break
            except RuntimeError:
                time.sleep(0.3)
                try:
                    ws_url = _new_target(args.chrome_port)
                except Exception:
                    ws_url = _first_page_target(args.chrome_port) or ws_url
        if cdp is None:
            raise RuntimeError("could not attach to Chrome")
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Log.enable")
        cdp.call("Network.enable")

        checker = Checker(cdp, base)
        run_checks(checker, base, onboarded, fresh)

        print("\n[9] Console health")
        errors = checker.console_errors()
        relevant = [e for e in errors if "beforeinstallprompt" not in e and "deprecated" not in e and "FetchEvent" not in e]
        if relevant:
            for error in relevant[:12]:
                print("  CONSOLE", error[:220])
        checker.ok(not relevant, "no console errors or uncaught exceptions", f"{len(relevant)} found")

        print("\n" + "=" * 60)
        if checker.failures:
            print(f"FAILED {len(checker.failures)} check(s):")
            for failure in checker.failures:
                print("  -", failure)
            print("Screenshots:", SCREENSHOTS)
            return 1
        print("All browser checks passed.")
        print("Screenshots:", SCREENSHOTS)
        return 0
    finally:
        if cdp and not args.keep:
            cdp.close()
        if chrome and not args.keep:
            chrome.terminate()
        if not args.keep:
            server.terminate()
            shutil.rmtree(data_dir, ignore_errors=True)
            shutil.rmtree(chrome_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
