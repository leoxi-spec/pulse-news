"""Polite, resilient HTTP fetching on top of the standard library.

Features that matter in production:
  * gzip decoding + explicit byte caps
  * conditional GET (ETag / Last-Modified) so a 12-minute sweep is cheap
  * bounded retries with jitter on transient failures
  * per-host politeness (concurrency + minimum spacing)
  * SSRF guard (no private / loopback / link-local targets)
  * optional curl fallback when the local OpenSSL build cannot validate a chain
  * robots.txt awareness for full-article extraction
"""
from __future__ import annotations

import gzip
import io
import json
import random
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field

from . import tls
from .config import settings
from .logging_setup import get_logger

log = get_logger("http")

_REDIRECT_CODES = {301, 302, 303, 307, 308}
_ALLOW_PRIVATE = __import__("os").environ.get("PULSE_ALLOW_PRIVATE_HOSTS", "").lower() in ("1", "true", "yes")
_SAFE_PORTS = {80, 443, 8080, 8443}


class FetchError(Exception):
    """Network-level failure that is safe to show in a feed-health report."""


@dataclass
class FetchResult:
    url: str
    status: int
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and not self.not_modified

    @property
    def text(self) -> str:
        return decode_body(self.body, self.headers.get("content-type", ""))


def decode_body(body: bytes, content_type: str = "") -> str:
    if not body:
        return ""
    charset = ""
    match = re.search(r"charset=[\"']?([\w.:-]+)", content_type or "", re.I)
    if match:
        charset = match.group(1)
    if not charset:
        head = body[:2048].decode("ascii", "ignore")
        meta = re.search(r"charset=[\"']?([\w.:-]+)", head, re.I)
        if meta:
            charset = meta.group(1)
    for candidate in (charset, "utf-8", "latin-1"):
        if not candidate:
            continue
        try:
            return body.decode(candidate, "strict")
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", "replace")


class _HostGate:
    """Limits concurrent requests per host and spaces them out."""

    def __init__(self, concurrency: int = 2, min_interval: float = 0.35):
        self._sem = threading.BoundedSemaphore(concurrency)
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def __enter__(self):
        self._sem.acquire()
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            self._next_allowed = max(now, self._next_allowed) + self._min_interval
        if wait > 0:
            time.sleep(min(wait, 5.0))
        return self

    def __exit__(self, *exc):
        self._sem.release()
        return False


_gates: dict[str, _HostGate] = {}
_gates_lock = threading.Lock()
_dns_cache: dict[str, tuple[str, float]] = {}


def _gate(host: str) -> _HostGate:
    with _gates_lock:
        gate = _gates.get(host)
        if gate is None:
            gate = _HostGate(concurrency=2, min_interval=0.35)
            _gates[host] = gate
        return gate


def _is_public_host(host: str) -> bool:
    if _ALLOW_PRIVATE:
        return True
    now = time.monotonic()
    cached = _dns_cache.get(host)
    if cached and cached[1] > now:
        addr = cached[0]
    else:
        try:
            addr = socket.getaddrinfo(host, None)[0][4][0]
        except socket.gaierror as exc:
            raise FetchError(f"DNS lookup failed for {host}") from exc
        _dns_cache[host] = (addr, now + 300)
    import ipaddress

    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise FetchError("Only http(s) URLs are allowed")
    if not parsed.hostname:
        raise FetchError("URL has no host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in _SAFE_PORTS:
        raise FetchError(f"Port {port} is not allowed")
    if not _is_public_host(parsed.hostname):
        raise FetchError("Refusing to fetch a non-public address")
    return urllib.parse.urlunsplit(parsed)


class HttpClient:
    def __init__(self, user_agent: str | None = None, max_bytes: int | None = None):
        self.user_agent = user_agent or settings.user_agent
        self.max_bytes = max_bytes or settings.max_body_bytes

    # ------------------------------------------------------------------ core
    def fetch(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        accept: str = "*/*",
        timeout: float | None = None,
        retries: int = 2,
        allow_curl_fallback: bool = True,
    ) -> FetchResult:
        url = validate_url(url)
        host = urllib.parse.urlsplit(url).hostname or ""
        timeout = timeout or settings.feed_timeout_seconds
        headers = {
            "User-Agent": self.user_agent,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
            "Connection": "close",
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        last_error: Exception | None = None
        started = time.monotonic()
        for attempt in range(retries + 1):
            try:
                with _gate(host):
                    result = self._fetch_once(url, headers, timeout)
                result.elapsed_ms = int((time.monotonic() - started) * 1000)
                if result.status in (429, 500, 502, 503, 504) and attempt < retries:
                    retry_after = result.headers.get("retry-after", "")
                    delay = 1.5 * (attempt + 1) + random.uniform(0, 1.2)
                    try:
                        delay = max(delay, min(float(retry_after), 20))
                    except (TypeError, ValueError):
                        pass
                    time.sleep(delay)
                    continue
                return result
            except ssl.SSLError as exc:
                last_error = exc
                if allow_curl_fallback:
                    fallback = self._fetch_with_curl(url, headers, timeout)
                    if fallback is not None:
                        fallback.elapsed_ms = int((time.monotonic() - started) * 1000)
                        return fallback
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, FetchError) as exc:
                last_error = exc
            if attempt < retries:
                time.sleep(1.2 * (attempt + 1) + random.uniform(0, 0.8))
        raise FetchError(_short_error(last_error))

    def _fetch_once(self, url: str, headers: dict[str, str], timeout: float) -> FetchResult:
        request = urllib.request.Request(url, headers=headers, method="GET")
        ctx = tls.get_context() if url.startswith("https://") else None
        try:
            response = urllib.request.urlopen(request, timeout=timeout, context=ctx)
        except urllib.error.HTTPError as exc:
            # HTTPError is a response object too; 304 is a success for our purposes.
            if exc.code == 304:
                return FetchResult(
                    url=url,
                    status=304,
                    not_modified=True,
                    headers={k.lower(): v for k, v in exc.headers.items()},
                    etag=exc.headers.get("ETag"),
                    last_modified=exc.headers.get("Last-Modified"),
                )
            if exc.code in _REDIRECT_CODES:
                location = exc.headers.get("Location")
                if location:
                    return self.fetch(urllib.parse.urljoin(url, location), timeout=timeout, retries=0)
            return FetchResult(
                url=url,
                status=exc.code,
                headers={k.lower(): v for k, v in (exc.headers or {}).items()},
            )
        with response:
            raw = response.read(self.max_bytes + 1)
            if len(raw) > self.max_bytes:
                raise FetchError("Response exceeded size limit")
            body = _decompress(raw, response.headers.get("Content-Encoding", ""))
            hdrs = {k.lower(): v for k, v in response.headers.items()}
            return FetchResult(
                url=response.geturl(),
                status=response.status,
                body=body,
                headers=hdrs,
                etag=hdrs.get("etag"),
                last_modified=hdrs.get("last-modified"),
            )

    def _fetch_with_curl(self, url: str, headers: dict[str, str], timeout: float):
        """Fallback used when the local OpenSSL cannot validate a chain.

        curl uses the OS trust store on macOS, which often knows about
        corporate/parental-control roots that a bare OpenSSL bundle does not.
        Certificate verification stays ON.
        """
        import shutil
        import subprocess

        curl = shutil.which("curl")
        if not curl:
            return None
        cmd = [curl, "-sS", "-L", "--max-time", str(int(timeout)), "--compressed", "-o", "-", "-w", "\n%{http_code}"]
        for key, value in headers.items():
            if key.lower() in ("connection", "accept-encoding"):
                continue
            cmd += ["-H", f"{key}: {value}"]
        cmd += ["-H", "Accept-Encoding: gzip", url]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 5, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        raw = proc.stdout
        split = raw.rfind(b"\n")
        if split < 0:
            return None
        try:
            status = int(raw[split + 1 :].strip() or 0)
        except ValueError:
            return None
        body = raw[:split]
        return FetchResult(url=url, status=status, body=body, headers={})

    # --------------------------------------------------------------- helpers
    def get_text(self, url: str, **kwargs) -> FetchResult:
        return self.fetch(url, accept="application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5", **kwargs)

    def get_json(self, url: str, **kwargs) -> dict:
        result = self.fetch(url, accept="application/json", **kwargs)
        if not result.ok:
            raise FetchError(f"HTTP {result.status} for {url}")
        try:
            return json.loads(result.text)
        except json.JSONDecodeError as exc:
            raise FetchError(f"Invalid JSON from {url}") from exc


def _decompress(raw: bytes, encoding: str) -> bytes:
    encoding = (encoding or "").lower()
    if "gzip" in encoding:
        try:
            return gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        except OSError:
            return raw
    if "deflate" in encoding:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            try:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
            except zlib.error:
                return raw
    return raw


def _short_error(exc: Exception | None) -> str:
    if exc is None:
        return "Unknown network error"
    if isinstance(exc, FetchError):
        return str(exc)
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        return f"Network error: {reason}"
    return f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------- robots
_robots_lock = threading.Lock()
_robots_cache: dict[str, tuple[float, list[tuple[str, bool]]]] = {}


def robots_allowed(url: str, client: HttpClient | None = None) -> bool:
    """Conservative robots.txt check. Failure to load robots.txt = allowed."""
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    origin = f"{parsed.scheme}://{parsed.netloc}"
    now = time.monotonic()
    with _robots_lock:
        cached = _robots_cache.get(origin)
        if cached and cached[0] > now:
            rules = cached[1]
        else:
            rules = []
            try:
                client = client or _default_client()
                result = client.fetch(origin + "/robots.txt", timeout=8, retries=0, accept="text/plain")
                if result.ok:
                    rules = _parse_robots(result.text, client.user_agent)
            except FetchError:
                rules = []
            _robots_cache[origin] = (now + 3600, rules)
    if not rules:
        return True
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    allowed = True
    best_len = -1
    for pattern, is_allow in rules:
        if pattern == "/":
            matched = True
        else:
            regex = _robots_regex(pattern)
            matched = bool(regex.match(path))
        if matched and len(pattern) >= best_len:
            best_len = len(pattern)
            allowed = is_allow
    return allowed


def _robots_regex(pattern: str) -> re.Pattern[str]:
    escaped = re.escape(pattern).replace(r"\*", ".*")
    if escaped.endswith(r"\$"):
        escaped = escaped[:-2] + "$"
    return re.compile("^" + escaped)


def _parse_robots(text: str, ua: str) -> list[tuple[str, bool]]:
    groups: list[tuple[list[str], list[tuple[str, bool]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, bool]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
        elif key in ("allow", "disallow") and value:
            rules.append((value, key == "allow"))
    if agents or rules:
        groups.append((agents, rules))

    ua_l = ua.lower()
    chosen: list[tuple[str, bool]] = []
    best = -1
    for group_agents, group_rules in groups:
        for agent in group_agents:
            if agent == "*":
                score = 0
            elif agent and agent in ua_l:
                score = len(agent)
            else:
                continue
            if score > best:
                best = score
                chosen = list(group_rules)
            elif score == best:
                chosen.extend(group_rules)
    return chosen


_default: HttpClient | None = None


def _default_client() -> HttpClient:
    global _default
    if _default is None:
        _default = HttpClient()
    return _default
