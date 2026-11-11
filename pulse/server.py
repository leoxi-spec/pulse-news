"""HTTP server: static PWA + JSON API with production hygiene.

* threaded, keep-alive, gzip, ETag/304
* strict security headers and a tight CSP
* profile cookie (HttpOnly, SameSite=Lax) + CSRF header check
* optional bearer-token gate for exposing the app beyond localhost
"""
from __future__ import annotations

import gzip
import hashlib
import json
import mimetypes
import os
import re
import signal
import socket
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import api, profiles
from .config import APP_VERSION, settings
from .db import db
from .logging_setup import get_logger

log = get_logger("server")

SAFE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), interest-cohort=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob:; "
    "media-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "manifest-src 'self'; "
    "worker-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'"
)

COOKIE_PROFILE = "pulse_profile"
COOKIE_TOKEN = "pulse_token"
_CTYPE_OVERRIDES = {
    ".webmanifest": "application/manifest+json",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
}


class Handler(BaseHTTPRequestHandler):
    server_version = f"Pulse/{APP_VERSION}"
    protocol_version = "HTTP/1.1"
    sys_version = ""

    # -------------------------------------------------------------- dispatch
    def do_GET(self):
        self._dispatch("GET")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self._base_headers(extra={"Allow": "GET, HEAD, POST, PATCH, PUT, DELETE, OPTIONS"})
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _dispatch(self, method: str) -> None:
        started = time.monotonic()
        parsed = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parsed.path)
        query = {k: v[-1] for k, v in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).items()}
        status = 500
        try:
            # Local profile switching (families sharing one computer): a
            # validated profile id in the query sets the cookie and redirects to
            # a clean URL. No data is exposed without the matching cookie.
            switch = query.get("profile") or ""
            if not path.startswith("/api/") and re.fullmatch(r"[a-f0-9]{24}", switch or ""):
                remaining = {key: value for key, value in query.items() if key != "profile"}
                location = (path or "/") + ("?" + urllib.parse.urlencode(remaining) if remaining else "")
                self.send_response(302)
                self._base_headers(extra={
                    "Location": location,
                    "Set-Cookie": f"{COOKIE_PROFILE}={switch}; Path=/; Max-Age=63072000; HttpOnly; SameSite=Lax",
                })
                self.send_header("Content-Length", "0")
                self.end_headers()
                status = 302
                return

            if path.startswith("/api/"):
                status = self._handle_api(method, path, query)
            else:
                status = self._handle_static(method, path, query)
        except BrokenPipeError:
            return
        except Exception:
            log.exception("unhandled error for %s %s", method, path)
            try:
                self._send_json(500, {"error": "Internal server error"})
            except Exception:
                pass
            status = 500
        finally:
            duration = (time.monotonic() - started) * 1000
            if path.startswith("/api/") and path not in ("/api/img",):
                log.info("%s %s -> %s (%.0fms)", method, path, status, duration)

    # -------------------------------------------------------------------- api
    def _handle_api(self, method: str, path: str, query: dict) -> int:
        cookies = self._cookies()
        profile_id = cookies.get(COOKIE_PROFILE)
        client_id = self.headers.get("X-Pulse-Client")

        length = int(self.headers.get("Content-Length") or 0)
        if length > api.MAX_BODY:
            self._send_json(413, {"error": "Request body too large"})
            return 413
        # Always drain the body so keep-alive connections stay in sync.
        body = self.rfile.read(length) if length else b""

        set_cookies: list[str] = []
        if settings.access_token:
            provided = None
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                provided = auth[7:].strip()
            provided = provided or cookies.get(COOKIE_TOKEN) or query.get("token")
            if not _secure_equal(provided, settings.access_token):
                self._send_json(401, {"error": "Access token required", "code": "token_required"})
                return 401
            if query.get("token") and cookies.get(COOKIE_TOKEN) != settings.access_token:
                set_cookies.append(
                    f"{COOKIE_TOKEN}={settings.access_token}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax"
                )
        elif method in ("POST", "PATCH", "PUT", "DELETE"):
            if not client_id:
                # A custom header cannot be sent cross-site without a preflight.
                origin = self.headers.get("Origin")
                host = self.headers.get("Host", "")
                same_origin = bool(origin) and urllib.parse.urlsplit(origin).netloc == host
                if not same_origin:
                    self._send_json(403, {"error": "Missing X-Pulse-Client header", "code": "csrf"})
                    return 403

        request = api.Request(
            method=method,
            path=path,
            query=query,
            headers={k.lower(): v for k, v in self.headers.items()},
            body=body,
            profile_id=profile_id,
            client_id=client_id,
            remote=self.client_address[0] if self.client_address else "",
        )
        try:
            status, payload, headers = api.handle(request)
        except api.ApiError as exc:
            self._send_json(exc.status, {"error": exc.message, "code": exc.code})
            return exc.status

        extra = dict(headers or {})
        api_cookies = extra.pop("Set-Cookie", None)
        if api_cookies:
            if isinstance(api_cookies, str):
                set_cookies.append(api_cookies)
            else:
                set_cookies.extend(api_cookies)
        explicit_profile = extra.pop("Set-Profile", None)
        if explicit_profile:
            set_cookies.append(
                f"{COOKIE_PROFILE}={explicit_profile}; Path=/; Max-Age=63072000; HttpOnly; SameSite=Lax"
            )
        elif request.profile_id and request.profile_id != profile_id:
            set_cookies.append(
                f"{COOKIE_PROFILE}={request.profile_id}; Path=/; Max-Age=63072000; HttpOnly; SameSite=Lax"
            )
        if set_cookies:
            extra["Set-Cookie"] = set_cookies

        if isinstance(payload, (bytes, bytearray)):
            self._send_bytes(status, bytes(payload), extra)
        else:
            self._send_json(status, payload, extra)
        return status

    # ----------------------------------------------------------------- static
    def _handle_static(self, method: str, path: str, query: dict) -> int:
        if method not in ("GET", "HEAD"):
            self._send_json(405, {"error": "Method not allowed"})
            return 405
        if settings.access_token:
            cookies = self._cookies()
            provided = cookies.get(COOKIE_TOKEN) or query.get("token")
            if not _secure_equal(provided, settings.access_token):
                self._send_login()
                return 401
            if query.get("token"):
                self.send_response(303)
                self._base_headers(extra={
                    "Location": path or "/",
                    "Set-Cookie": f"{COOKIE_TOKEN}={settings.access_token}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax",
                })
                self.send_header("Content-Length", "0")
                self.end_headers()
                return 303
        if ".." in path.split("/"):
            self._send_json(403, {"error": "Forbidden"})
            return 403
        if path in ("/", ""):
            return self._send_file(settings.static_dir / "index.html", spa=True)
        # Client-side routes render the SPA shell. Anything without a file
        # extension is treated as a route, so new pages never 404 on refresh.
        if "." not in Path(path).name:
            return self._send_file(settings.static_dir / "index.html", spa=True)
        target = (settings.static_dir / path.lstrip("/")).resolve()
        try:
            target.relative_to(settings.static_dir.resolve())
        except ValueError:
            self._send_json(403, {"error": "Forbidden"})
            return 403
        if not target.exists() or target.is_dir():
            self._send_json(404, {"error": "Not found"})
            return 404
        return self._send_file(target)

    def _send_file(self, path: Path, *, spa: bool = False) -> int:
        try:
            stat = path.stat()
        except OSError:
            self._send_json(404, {"error": "Not found"})
            return 404
        etag = f'"{hashlib.sha1(f"{stat.st_mtime_ns}-{stat.st_size}".encode()).hexdigest()[:20]}"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self._base_headers(extra={"ETag": etag, "Cache-Control": "no-cache"})
            self.end_headers()
            return 304
        data = path.read_bytes()
        suffix = path.suffix.lower()
        content_type = _CTYPE_OVERRIDES.get(suffix) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        compressible = suffix in (".html", ".css", ".js", ".mjs", ".json", ".svg", ".webmanifest", ".txt")
        extra = {
            "ETag": etag,
            "Cache-Control": "no-cache",  # always revalidate app code; ETag makes it a cheap 304
        }
        if compressible and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            data = gzip.compress(data, 6)
            extra["Content-Encoding"] = "gzip"
            extra["Vary"] = "Accept-Encoding"
        self.send_response(200)
        self._base_headers(extra=extra)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)
        return 200

    def _send_login(self) -> None:
        body = (
            "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Pulse — sign in</title><style>"
            "body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0a0c11;color:#eef1f6;"
            "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}"
            "main{width:min(420px,90vw);padding:2rem;border:1px solid #262f3d;border-radius:18px;background:#141922}"
            "h1{margin:0 0 .4rem;font-size:1.4rem}p{color:#86909f;font-size:.9rem;margin:0 0 1rem}"
            "input{width:100%;padding:.7rem .85rem;border-radius:10px;border:1px solid #262f3d;background:#0e1117;color:#fff;"
            "box-sizing:border-box}button{margin-top:.8rem;width:100%;padding:.7rem;border:0;border-radius:10px;"
            "background:linear-gradient(120deg,#7c5cff,#ff4d8d);color:#fff;font-weight:700;font-size:.95rem;cursor:pointer}"
            ".err{color:#ff5e5e;font-size:.82rem;margin-top:.7rem;display:none}"
            "</style></head><body><main><h1>Pulse</h1>"
            "<p>This server is protected. Enter the access token to continue.</p>"
            "<form method=\"get\" action=\"/\">"
            "<input name=\"token\" type=\"password\" placeholder=\"Access token\" autofocus autocomplete=\"current-password\">"
            "<button type=\"submit\">Open Pulse</button></form>"
            "<p class=\"err\">That token was not accepted.</p>"
            "</main></body></html>"
        ).encode("utf-8")
        self.send_response(401)
        self._base_headers(extra={"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"})
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # ---------------------------------------------------------------- output
    def _send_json(self, status: int, payload, extra: dict | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        body, encoding = self._maybe_gzip(body)
        self.send_response(status)
        self._base_headers(extra={"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", **(extra or {})})
        if encoding:
            self.send_header("Content-Encoding", encoding)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_bytes(self, status: int, body: bytes, extra: dict | None = None) -> None:
        self.send_response(status)
        self._base_headers(extra=extra or {})
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _maybe_gzip(self, body: bytes) -> tuple[bytes, str | None]:
        if len(body) < 1200:
            return body, None
        if "gzip" not in (self.headers.get("Accept-Encoding") or ""):
            return body, None
        return gzip.compress(body, 5), "gzip"

    def _base_headers(self, extra: dict | None = None) -> None:
        for key, value in SAFE_HEADERS.items():
            self.send_header(key, value)
        self.send_header("Content-Security-Policy", CSP)
        for key, value in (extra or {}).items():
            if isinstance(value, (list, tuple)):
                for item in value:
                    self.send_header(key, item)
            else:
                self.send_header(key, value)

    def _cookies(self) -> dict[str, str]:
        raw = self.headers.get("Cookie") or ""
        jar = {}
        for part in raw.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                jar[key.strip()] = value.strip()
        return jar

    def log_message(self, fmt: str, *args) -> None:  # quieter default logging
        log.debug("%s - %s", self.address_string(), fmt % args)


def _secure_equal(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    import hmac

    return hmac.compare_digest(a.encode(), b.encode())


def serve(host: str | None = None, port: int | None = None) -> None:
    host = host or settings.host
    port = port or settings.port
    settings.ensure_dirs()
    db.init()
    from .sources import FEEDS, SOURCES

    db.seed_catalog(SOURCES, FEEDS)

    from .ingest import ingest

    ingest.start()

    try:
        httpd = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        log.error("Could not bind %s:%s — %s", host, port, exc)
        sys.exit(2)
    httpd.daemon_threads = True
    httpd.allow_reuse_address = True

    shown_host = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    log.info("Pulse running at http://%s:%s", shown_host, port)
    log.info("data: %s", settings.db_path)
    if settings.ai_enabled:
        log.info("AI overviews: %s via %s", settings.ai_model, settings.ai_base_url)
    else:
        log.info("AI overviews: off (set PULSE_AI_BASE_URL to enable)")

    def _shutdown(signum, frame):
        log.info("shutting down (signal %s)", signum)
        ingest.stop()
        # shutdown() blocks until serve_forever() returns. Because signal
        # handlers run on the same thread as serve_forever, calling it directly
        # here deadlocks the process. Hand it to a helper thread instead.
        threading.Thread(target=httpd.shutdown, name="pulse-shutdown", daemon=True).start()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _shutdown)
        except (ValueError, OSError):
            pass

    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        ingest.stop()
        httpd.server_close()
        log.info("stopped")
