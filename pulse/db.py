"""SQLite storage.

Design choices that matter here:

* **WAL + a single writer lock.** Many reader threads (the HTTP server) and a
  few worker threads (ingestion, extraction) share the same file.
* **Nothing is ever deleted.** Articles accumulate into a permanent archive so
  search over "any topic" keeps returning more results the longer the app runs.
* **FTS5 external-content index** with triggers, so full-text search stays in
  sync without copying article bodies twice.
* **Idempotent catalog seeding**: sources and feeds are metadata, articles are
  the durable data.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from .config import settings
from .logging_setup import get_logger
from .timeutil import iso, now, parse_iso

log = get_logger("db")

SCHEMA_VERSION = 10

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    domain      TEXT,
    country     TEXT,
    region      TEXT,
    lean        TEXT,
    paywall     INTEGER NOT NULL DEFAULT 0,
    audience    TEXT,
    topics      TEXT NOT NULL DEFAULT '[]',
    about       TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feeds (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    key                 TEXT NOT NULL UNIQUE,
    source_id           TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    url                 TEXT NOT NULL UNIQUE,
    topic               TEXT NOT NULL DEFAULT 'world',
    label               TEXT,
    kind                TEXT NOT NULL DEFAULT 'rss',
    etag                TEXT,
    last_modified       TEXT,
    last_fetch_at       TEXT,
    last_success_at     TEXT,
    last_status         INTEGER,
    last_error          TEXT,
    fetch_ms            INTEGER,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    total_fetches       INTEGER NOT NULL DEFAULT 0,
    item_count          INTEGER NOT NULL DEFAULT 0,
    next_fetch_at       TEXT,
    blocked             INTEGER NOT NULL DEFAULT 0,
    enabled             INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_feeds_source ON feeds(source_id);
CREATE INDEX IF NOT EXISTS idx_feeds_next ON feeds(next_fetch_at);

CREATE TABLE IF NOT EXISTS articles (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    guid               TEXT NOT NULL,
    source_id          TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    feed_id            INTEGER REFERENCES feeds(id) ON DELETE SET NULL,
    url                TEXT NOT NULL,
    canonical_url      TEXT,
    title              TEXT NOT NULL,
    summary            TEXT,
    author             TEXT,
    image_url          TEXT,
    images             TEXT,
    video_url          TEXT,
    video_id           TEXT,
    video_kind         TEXT,
    published_at       TEXT,
    published_raw      TEXT,
    date_confidence    TEXT NOT NULL DEFAULT 'unknown',
    updated_at         TEXT,
    first_seen_at      TEXT NOT NULL,
    last_seen_at       TEXT NOT NULL,
    primary_topic      TEXT NOT NULL DEFAULT 'world',
    topics             TEXT NOT NULL DEFAULT '[]',
    lang               TEXT NOT NULL DEFAULT 'en',
    word_count         INTEGER NOT NULL DEFAULT 0,
    reading_minutes    INTEGER NOT NULL DEFAULT 1,
    content_text       TEXT,
    content_blocks     TEXT,
    content_state      TEXT NOT NULL DEFAULT 'feed',
    paywalled          INTEGER NOT NULL DEFAULT 0,
    is_breaking        INTEGER NOT NULL DEFAULT 0,
    simhash            TEXT,
    story_id           INTEGER,
    source_weight      REAL NOT NULL DEFAULT 1.0,
    UNIQUE(source_id, guid)
);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_seen ON articles(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(primary_topic, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_story ON articles(story_id);
CREATE INDEX IF NOT EXISTS idx_articles_state ON articles(content_state);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, summary, content_text, author,
    content='articles', content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS articles_fts_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, summary, content_text, author)
    VALUES (new.id, new.title, new.summary, new.content_text, new.author);
END;
CREATE TRIGGER IF NOT EXISTS articles_fts_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary, content_text, author)
    VALUES ('delete', old.id, old.title, old.summary, old.content_text, old.author);
END;
CREATE TRIGGER IF NOT EXISTS articles_fts_au AFTER UPDATE OF title, summary, content_text, author ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, summary, content_text, author)
    VALUES ('delete', old.id, old.title, old.summary, old.content_text, old.author);
    INSERT INTO articles_fts(rowid, title, summary, content_text, author)
    VALUES (new.id, new.title, new.summary, new.content_text, new.author);
END;

CREATE TABLE IF NOT EXISTS stories (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    key            TEXT NOT NULL UNIQUE,
    title          TEXT NOT NULL,
    primary_topic  TEXT NOT NULL DEFAULT 'world',
    first_seen_at  TEXT NOT NULL,
    last_seen_at   TEXT NOT NULL,
    article_count  INTEGER NOT NULL DEFAULT 1,
    source_count   INTEGER NOT NULL DEFAULT 1,
    lead_article_id INTEGER,
    heat           REAL NOT NULL DEFAULT 0,
    breaking       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_stories_seen ON stories(last_seen_at DESC);

CREATE TABLE IF NOT EXISTS profiles (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    onboarded     INTEGER NOT NULL DEFAULT 0,
    survey        TEXT NOT NULL DEFAULT '{}',
    prefs         TEXT NOT NULL DEFAULT '{}',
    xp            INTEGER NOT NULL DEFAULT 0,
    level         INTEGER NOT NULL DEFAULT 1,
    streak_count  INTEGER NOT NULL DEFAULT 0,
    streak_best   INTEGER NOT NULL DEFAULT 0,
    streak_last   TEXT,
    daily_goal    INTEGER NOT NULL DEFAULT 5
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    name          TEXT,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    profile_id    TEXT REFERENCES profiles(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL,
    last_login_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_profile ON users(profile_id);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    last_seen_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    kind       TEXT NOT NULL,
    article_id INTEGER,
    story_id   INTEGER,
    topic      TEXT,
    source_id  TEXT,
    value      REAL NOT NULL DEFAULT 0,
    meta       TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_profile ON events(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(profile_id, kind, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_article ON events(profile_id, article_id);

CREATE TABLE IF NOT EXISTS saves (
    profile_id TEXT NOT NULL,
    article_id INTEGER NOT NULL,
    collection TEXT NOT NULL DEFAULT 'Saved',
    created_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, article_id)
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    article_id INTEGER NOT NULL,
    quote      TEXT,
    body       TEXT NOT NULL,
    start_offset INTEGER,
    end_offset   INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_article ON notes(profile_id, article_id);

CREATE TABLE IF NOT EXISTS follows (
    profile_id TEXT NOT NULL,
    kind       TEXT NOT NULL,
    value      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, kind, value)
);

CREATE TABLE IF NOT EXISTS searches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id  TEXT NOT NULL,
    query       TEXT NOT NULL,
    result_count INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_searches_profile ON searches(profile_id, created_at DESC);

CREATE TABLE IF NOT EXISTS sports_cache (
    key        TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_cache (
    key        TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    model      TEXT,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS translations (
    cache_key       TEXT PRIMARY KEY,
    source_lang     TEXT NOT NULL,
    target_lang     TEXT NOT NULL DEFAULT 'en',
    source_text     TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    provider        TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_translations_created ON translations(created_at DESC);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    feeds_ok      INTEGER NOT NULL DEFAULT 0,
    feeds_failed  INTEGER NOT NULL DEFAULT 0,
    new_articles  INTEGER NOT NULL DEFAULT 0,
    updated_articles INTEGER NOT NULL DEFAULT 0,
    errors        TEXT
);

CREATE TABLE IF NOT EXISTS daily_stats (
    profile_id  TEXT NOT NULL,
    day         TEXT NOT NULL,
    read_count  INTEGER NOT NULL DEFAULT 0,
    minutes     REAL NOT NULL DEFAULT 0,
    xp          INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (profile_id, day)
);

CREATE TABLE IF NOT EXISTS roadmap_votes (
    profile_id TEXT NOT NULL,
    item_id    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_roadmap_votes_item ON roadmap_votes(item_id);

CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT,
    category   TEXT NOT NULL,
    message    TEXT NOT NULL,
    email      TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at DESC);
"""


class Database:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or settings.db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self._initialised = False
        self._init_lock = threading.Lock()

    # ------------------------------------------------------------------ setup
    def init(self) -> None:
        with self._init_lock:
            if self._initialised:
                return
            conn = self.connect()
            conn.executescript(_SCHEMA)
            # Lightweight migrations for databases created before a column existed.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
            if "images" not in columns:
                conn.execute("ALTER TABLE articles ADD COLUMN images TEXT")
            for column in ("video_url", "video_id", "video_kind"):
                if column not in columns:
                    conn.execute(f"ALTER TABLE articles ADD COLUMN {column} TEXT")
            # JSON-LD sometimes stores escaped slashes (https:\/\/...); repair
            # them once so the browser receives a real URL.
            conn.execute(
                "UPDATE articles SET video_url = REPLACE(video_url, ?, '/') "
                "WHERE instr(video_url, ?) > 0",
                ("\\/", "\\/"),
            )
            conn.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            conn.commit()
            self._initialised = True
            log.info("database ready at %s", self.path)

    def connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        conn = sqlite3.connect(
            self.path,
            timeout=30.0,
            isolation_level=None,  # explicit transactions
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-32000")
        self._local.conn = conn
        return conn

    def close_thread_connection(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            self._local.conn = None

    @contextmanager
    def writer(self) -> Iterator[sqlite3.Connection]:
        """Serialised write transaction."""
        conn = self.connect()
        with self._write_lock:
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError:
                # Another thread holds the write lock; retry once after a beat.
                import time

                time.sleep(0.2)
                conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    @contextmanager
    def reader(self) -> Iterator[sqlite3.Connection]:
        yield self.connect()

    # ------------------------------------------------------------------ utils
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return list(self.connect().execute(sql, params))

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        return self.connect().execute(sql, params).fetchone()

    def scalar(self, sql: str, params: Sequence[Any] = (), default: Any = None) -> Any:
        row = self.query_one(sql, params)
        if row is None or row[0] is None:
            return default
        return row[0]

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self.writer() as conn:
            return conn.execute(sql, params)

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        with self.writer() as conn:
            conn.executemany(sql, rows)

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.query_one("SELECT value FROM meta WHERE key=?", (key,))
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    # --------------------------------------------------------------- catalog
    def seed_catalog(self, sources: dict, feeds: Iterable) -> None:
        """Insert/update source + feed metadata without touching article data."""
        timestamp = iso()
        with self.writer() as conn:
            for source in sources.values():
                conn.execute(
                    """
                    INSERT INTO sources(id, name, domain, country, region, lean, paywall, audience, topics, about, created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name, domain=excluded.domain, country=excluded.country,
                        region=excluded.region, lean=excluded.lean, paywall=excluded.paywall,
                        audience=excluded.audience, topics=excluded.topics, about=excluded.about
                    """,
                    (
                        source.id, source.name, source.domain, source.country, source.region,
                        source.lean, int(source.paywall), source.audience,
                        json.dumps(list(source.topics)), source.about, timestamp,
                    ),
                )
            for feed in feeds:
                conn.execute(
                    """
                    INSERT INTO feeds(key, source_id, url, topic, label, kind)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(url) DO UPDATE SET
                        source_id=excluded.source_id, topic=excluded.topic,
                        label=excluded.label, kind=excluded.kind,
                        enabled=1
                    """,
                    (feed.id, feed.source_id, feed.url, feed.topic, feed.label, feed.kind),
                )
            # Feeds that disappeared from the catalog stop being polled.
            known = {feed.url for feed in feeds}
            if known:
                placeholders = ",".join("?" for _ in known)
                conn.execute(
                    f"UPDATE feeds SET enabled=0 WHERE url NOT IN ({placeholders})",
                    tuple(known),
                )

    # ------------------------------------------------------------- reporting
    def stats(self) -> dict:
        row = self.query_one(
            """
            SELECT
              (SELECT COUNT(*) FROM articles) AS articles,
              (SELECT COUNT(*) FROM stories) AS stories,
              (SELECT COUNT(*) FROM sources) AS sources,
              (SELECT COUNT(*) FROM feeds WHERE enabled=1) AS feeds,
              (SELECT COUNT(*) FROM feeds WHERE enabled=1 AND last_success_at IS NOT NULL) AS feeds_ok,
              (SELECT COUNT(*) FROM feeds WHERE enabled=1 AND consecutive_failures >= 3) AS feeds_failing,
              (SELECT COUNT(*) FROM articles WHERE content_text IS NOT NULL AND length(content_text) > 400) AS full_text,
              (SELECT COUNT(*) FROM articles WHERE video_kind IS NOT NULL) AS videos,
              (SELECT MIN(published_at) FROM articles WHERE published_at IS NOT NULL) AS earliest,
              (SELECT MAX(published_at) FROM articles WHERE published_at IS NOT NULL) AS latest,
              (SELECT MAX(first_seen_at) FROM articles) AS last_article
            """
        )
        data = dict(row) if row else {}
        last_run = self.query_one(
            "SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 1"
        )
        data["last_ingest"] = dict(last_run) if last_run else None
        data["db_bytes"] = self.path.stat().st_size if self.path.exists() else 0
        data["archive_earliest"] = data.get("earliest")
        return data

    def topic_counts(self, since: str | None = None) -> dict[str, int]:
        sql = "SELECT primary_topic AS t, COUNT(*) AS n FROM articles"
        params: tuple = ()
        if since:
            sql += " WHERE first_seen_at >= ?"
            params = (since,)
        sql += " GROUP BY primary_topic"
        return {row["t"]: row["n"] for row in self.query(sql, params)}

    def source_health(self) -> list[dict]:
        rows = self.query(
            """
            SELECT f.id, f.url, f.topic, f.kind, f.last_fetch_at, f.last_success_at,
                   f.last_status, f.last_error, f.fetch_ms, f.consecutive_failures,
                   f.total_fetches, f.item_count, f.blocked, f.enabled,
                   s.id AS source_id, s.name AS source_name, s.domain, s.country
            FROM feeds f JOIN sources s ON s.id = f.source_id
            ORDER BY f.consecutive_failures DESC, s.name
            """
        )
        return [dict(row) for row in rows]

    def cleanup(self) -> None:
        """Housekeeping that never touches the article archive."""
        from datetime import timedelta

        self._cleanup_image_cache(days=30, max_files=4000)

        cutoff = iso(now() - timedelta(days=14))
        old = now() - timedelta(days=45)
        with self.writer() as conn:
            conn.execute("DELETE FROM ai_cache WHERE created_at < ?", (iso(old),))
            conn.execute("DELETE FROM ingest_runs WHERE started_at < ?", (iso(now() - timedelta(days=60)),))
            conn.execute("DELETE FROM events WHERE created_at < ?", (iso(now() - timedelta(days=365)),))
            conn.execute("DELETE FROM searches WHERE created_at < ?", (iso(now() - timedelta(days=180)),))
        log.debug("cleanup done (cutoff %s)", cutoff)

    def _cleanup_image_cache(self, *, days: int, max_files: int) -> None:
        """Keep the image proxy cache bounded without touching articles."""
        from datetime import timedelta

        import time

        folder = settings.cache_dir / "img"
        if not folder.is_dir():
            return
        cutoff = time.time() - days * 86400
        try:
            entries = sorted(folder.iterdir(), key=lambda path: path.stat().st_mtime)
        except OSError:
            return
        removed = 0
        for path in entries:
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        while len(entries) - removed > max_files:
            victim = entries.pop(0) if entries else None
            if victim is None:
                break
            try:
                victim.unlink()
                removed += 1
            except OSError:
                continue
        if removed:
            log.debug("image cache: removed %d files", removed)


db = Database()


def last_seen_label(value: str | None) -> str:
    dt = parse_iso(value)
    return dt.isoformat() if dt else ""
