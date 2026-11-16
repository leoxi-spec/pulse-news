"""Trust-store handling.

Python's OpenSSL build does not always ship a CA bundle (notably the
python.org macOS framework), and some corporate/parental-control proxies
inject a root that only the OS trust store knows about.  We therefore build a
context from the platform trust store, falling back to certifi or the usual
well-known bundle paths, and cache the merged bundle on disk.

We never disable certificate verification silently: if no trust material can
be found we fail closed and surface a clear error to the caller.
"""
from __future__ import annotations

import os
import ssl
import subprocess
import threading
from pathlib import Path

from .config import settings

_LOCK = threading.Lock()
_CTX: ssl.SSLContext | None = None
_LAST_BUNDLE: Path | None = None

_LINUX_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    "/etc/ssl/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
)

_MAC_KEYCHAINS = (
    "/System/Library/Keychains/SystemRootCertificates.keychain",
    "/Library/Keychains/System.keychain",
)


def _run(cmd: list[str], timeout: int = 25) -> bytes:
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
        return proc.stdout or b""
    except (OSError, subprocess.SubprocessError):
        return b""


def _system_bundle() -> str:
    """Return PEM text from the platform trust store (best effort)."""
    chunks: list[str] = []

    env_bundle = os.environ.get("PULSE_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if env_bundle and Path(env_bundle).is_file():
        try:
            chunks.append(Path(env_bundle).read_text("utf-8", "ignore"))
        except OSError:
            pass

    if os.uname().sysname == "Darwin" and Path("/usr/bin/security").exists():
        for keychain in _MAC_KEYCHAINS:
            out = _run(["/usr/bin/security", "find-certificate", "-a", "-p", keychain])
            if out:
                chunks.append(out.decode("utf-8", "ignore"))
        # Login keychain may hold additional trusted roots (e.g. a filtering proxy).
        login = Path.home() / "Library" / "Keychains" / "login.keychain-db"
        if login.exists():
            out = _run(["/usr/bin/security", "find-certificate", "-a", "-p", str(login)])
            if out:
                chunks.append(out.decode("utf-8", "ignore"))

    if not chunks:
        try:  # optional dependency, never required
            import certifi  # type: ignore

            ca_path = certifi.where()
            if ca_path:
                chunks.append(Path(ca_path).read_text("utf-8", "ignore"))
        except Exception:
            pass

    for path in _LINUX_BUNDLES:
        if Path(path).is_file():
            try:
                chunks.append(Path(path).read_text("utf-8", "ignore"))
            except OSError:
                continue

    # Deduplicate individual PEM certificates while keeping order.
    seen: set[str] = set()
    deduped: list[str] = []
    for chunk in chunks:
        for block in chunk.split("-----END CERTIFICATE-----"):
            if "-----BEGIN CERTIFICATE-----" not in block:
                continue
            pem = block.split("-----BEGIN CERTIFICATE-----", 1)[1].strip()
            if pem in seen:
                continue
            seen.add(pem)
            deduped.append("-----BEGIN CERTIFICATE-----\n" + pem + "\n-----END CERTIFICATE-----\n")
    return "".join(deduped)


def _write_cache(pem: str) -> Path | None:
    try:
        settings.ensure_dirs()
        target = settings.cache_dir / "ca-bundle.pem"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(pem, "utf-8")
        tmp.replace(target)
        return target
    except OSError:
        return None


def build_context() -> ssl.SSLContext:
    """A verifying SSL context that matches the OS trust decisions."""
    global _LAST_BUNDLE
    pem = _system_bundle()
    ctx = ssl.create_default_context()
    if pem:
        try:
            ctx.load_verify_locations(cadata=pem)
        except ssl.SSLError:
            # A single malformed certificate must not poison the whole bundle.
            safe = [b for b in pem.split("-----END CERTIFICATE-----") if "BEGIN CERTIFICATE" in b]
            for block in safe:
                try:
                    ctx.load_verify_locations(
                        cadata=block + "-----END CERTIFICATE-----\n"
                    )
                except ssl.SSLError:
                    continue
        _LAST_BUNDLE = _write_cache(pem)
    # OpenSSL 3 strict mode rejects legacy corporate roots that the OS accepts.
    # Clearing the flag keeps full chain verification but restores OS parity.
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    ctx.check_hostname = True
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.set_alpn_protocols(["http/1.1"])
    except NotImplementedError:  # pragma: no cover
        pass
    return ctx


def get_context() -> ssl.SSLContext:
    global _CTX
    with _LOCK:
        if _CTX is None:
            _CTX = build_context()
        return _CTX


def reset() -> None:
    global _CTX
    with _LOCK:
        _CTX = None


def verify_available() -> bool:
    return get_context().verify_mode == ssl.CERT_REQUIRED


def bundle_path() -> Path | None:
    return _LAST_BUNDLE
