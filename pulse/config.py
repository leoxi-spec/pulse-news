"""Runtime configuration for Pulse.

Everything is environment-driven with safe local defaults so the app can be
started with `python3 run.py` and no configuration at all.
"""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "Pulse"
APP_TAGLINE = "News that keeps up with you"
APP_VERSION = "2.7.0"

ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _default_data_dir() -> Path:
    override = os.environ.get("PULSE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif os.uname().sysname == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "pulse-news"


@dataclass(frozen=True)
class Settings:
    host: str = os.environ.get("PULSE_HOST", "127.0.0.1")
    port: int = _env_int("PULSE_PORT", 8787, 1, 65535)
    data_dir: Path = field(default_factory=_default_data_dir)
    static_dir: Path = ROOT / "pulse" / "static"

    # Server hardening
    access_token: str | None = os.environ.get("PULSE_ACCESS_TOKEN") or None
    allow_origin: str | None = os.environ.get("PULSE_ALLOW_ORIGIN") or None

    # Ingestion
    ingest_enabled: bool = _env_bool("PULSE_INGEST", True)
    ingest_interval_seconds: int = _env_int("PULSE_INGEST_INTERVAL", 300, 60)
    ingest_workers: int = _env_int("PULSE_INGEST_WORKERS", 12, 1, 48)
    feed_timeout_seconds: int = _env_int("PULSE_FEED_TIMEOUT", 20, 5, 90)
    article_timeout_seconds: int = _env_int("PULSE_ARTICLE_TIMEOUT", 20, 5, 90)
    max_articles_per_feed: int = _env_int("PULSE_MAX_PER_FEED", 40, 5, 200)
    extract_bodies: bool = _env_bool("PULSE_EXTRACT_BODIES", True)
    extract_workers: int = _env_int("PULSE_EXTRACT_WORKERS", 8, 1, 16)
    extract_per_cycle: int = _env_int("PULSE_EXTRACT_PER_CYCLE", 150, 0, 500)
    archive_full_text: bool = _env_bool("PULSE_ARCHIVE_FULLTEXT", True)
    # Some publishers (and ESPN's scoreboard API) reject obvious bot user
    # agents, so the default is a normal desktop browser string. Set
    # PULSE_USER_AGENT to identify yourself if you prefer, and PULSE_HONEST_UA=1
    # to use an explicit bot string instead.
    user_agent: str = os.environ.get(
        "PULSE_USER_AGENT",
        (
            f"PulseNewsBot/{APP_VERSION} (+personal news reader; contact: local-user)"
            if _env_bool("PULSE_HONEST_UA", False)
            else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    )

    # AI overview provider (OpenAI-compatible, incl. Ollama / LM Studio / vLLM)
    ai_base_url: str | None = os.environ.get("PULSE_AI_BASE_URL") or None
    ai_api_key: str | None = os.environ.get("PULSE_AI_API_KEY") or None
    ai_model: str = os.environ.get("PULSE_AI_MODEL", "gpt-4o-mini")
    ai_timeout_seconds: int = _env_int("PULSE_AI_TIMEOUT", 45, 5, 180)
    ai_max_requests_per_hour: int = _env_int("PULSE_AI_RATE", 120, 1)

    # Sports
    sports_enabled: bool = _env_bool("PULSE_SPORTS", True)
    sports_cache_seconds: int = _env_int("PULSE_SPORTS_CACHE", 20, 5, 300)
    espn_base: str = os.environ.get("PULSE_ESPN_BASE", "https://site.api.espn.com")

    # Limits
    max_body_bytes: int = _env_int("PULSE_MAX_BODY", 4_000_000, 100_000)
    cors_extra: tuple[str, ...] = ()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "pulse.sqlite3"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_base_url)

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.cache_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()


def hostname() -> str:
    return socket.gethostname()
