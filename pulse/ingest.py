"""Ingestion: pull every feed, store everything, cluster, then extract bodies.

The loop is deliberately boring and restart-safe:

1. fetch feeds concurrently (conditional GET where the server supports it)
2. parse -> normalise -> classify -> upsert into the permanent archive
3. cluster new articles into stories
4. extract readable text for the newest articles so previews get better over time
5. record a run report and feed health, then sleep

Everything is idempotent: killing the process mid-run loses at most one batch.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import random
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import timedelta

from . import feedparse, htmltext, sports, stories, topics
from .config import settings
from .db import db
from .httpclient import FetchError, HttpClient, robots_allowed, validate_url
from .logging_setup import get_logger
from .sources import FEEDS, FEEDS_BY_SOURCE, SOURCES, FeedSpec
from .timeutil import iso, minutes_since, now, parse_date, parse_iso

log = get_logger("ingest")

_FLAGSHIP = {
    "bbc", "ap", "reuters", "nyt", "wapo", "wsj", "guardian", "economist", "npr", "cnn",
    "aljazeera", "ft", "bloomberg", "cbc", "abcau", "jpost", "toi", "hindu", "scmp",
    "lemonde", "elpais", "spiegel", "cna", "straitstimes", "nikkei", "japantimes",
}


@dataclass
class FeedOutcome:
    feed: FeedSpec
    ok: bool = False
    status: int | None = None
    error: str | None = None
    blocked: bool = False
    items: int = 0
    new: int = 0
    updated: int = 0
    elapsed_ms: int = 0
    etag: str | None = None
    last_modified: str | None = None


@dataclass
class RunReport:
    started_at: str = field(default_factory=iso)
    finished_at: str | None = None
    feeds_ok: int = 0
    feeds_failed: int = 0
    new_articles: int = 0
    updated_articles: int = 0
    extracted: int = 0
    story_count: int = 0
    errors: list[dict] = field(default_factory=list)

    def duration_seconds(self) -> float:
        return round(minutes_since(self.started_at) * 60, 1)

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "feeds_ok": self.feeds_ok,
            "feeds_failed": self.feeds_failed,
            "new_articles": self.new_articles,
            "updated_articles": self.updated_articles,
            "extracted": self.extracted,
            "story_count": self.story_count,
            "errors": self.errors[:25],
            "duration_seconds": round(minutes_since(self.started_at) * 60, 1),
        }


class IngestService:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._run_lock = threading.Lock()
        self._status_lock = threading.Lock()
        self.running = False
        self.progress = 0.0
        self.progress_label = ""
        self.last_report: dict | None = None
        self.next_run_at: str | None = None
        self.client = HttpClient()
        self.started_at: str | None = None

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if not settings.ingest_enabled:
            log.info("ingestion disabled by configuration")
            return
        db.init()
        db.seed_catalog(SOURCES, FEEDS)
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="pulse-ingest", daemon=True)
        self._thread.start()
        self.started_at = iso()
        log.info("ingest worker started (%d feeds, every %ss)", len(FEEDS), settings.ingest_interval_seconds)

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        # First run: immediately if the archive is empty, otherwise give the UI
        # a moment to come up before spending bandwidth.
        has_articles = (db.scalar("SELECT COUNT(*) FROM articles", default=0) or 0) > 0
        initial_delay = 5 if not has_articles else 45
        if self._stop.wait(initial_delay):
            return
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                log.exception("ingest run crashed")
            try:
                db.cleanup()
            except Exception:
                log.exception("cleanup failed")
            delay = max(60, settings.ingest_interval_seconds)
            self.next_run_at = iso(now() + timedelta(seconds=delay))
            if self._stop.wait(delay):
                break

    def trigger(self) -> bool:
        """Start a background run if one is not already in flight."""
        if self.running:
            return False
        threading.Thread(target=self._safe_run, name="pulse-ingest-trigger", daemon=True).start()
        return True

    def _safe_run(self) -> None:
        try:
            self.run_once()
        except Exception:
            log.exception("manual ingest run failed")

    # ------------------------------------------------------------------- run
    def run_once(self, *, only_source: str | None = None, extract: bool = True) -> dict:
        with self._run_lock:
            self.running = True
            self.progress = 0.0
            report = RunReport()
            try:
                feeds = self._select_feeds(only_source)
                self._set_progress(0.0, f"Fetching {len(feeds)} feeds")
                clusterer = stories.Clusterer(stories.load_recent(days=5))
                outcomes, affected = self._fetch_all(feeds, report, clusterer)
                self._set_progress(0.94, "Updating stories")
                for story_id in affected:
                    try:
                        self._update_story(story_id)
                    except Exception:
                        log.debug("story update failed for %s", story_id, exc_info=True)
                if extract and settings.extract_bodies:
                    self._set_progress(0.94, "Extracting article text")
                    report.extracted = self._extract_pending()
                report.story_count = db.scalar("SELECT COUNT(*) FROM stories", default=0) or 0
            finally:
                report.finished_at = iso()
                self.last_report = report.to_dict()
                self.running = False
                self.progress = 1.0
                self._set_progress(1.0, "")
                self._record_run(report)
            log.info(
                "ingest done: %d ok / %d failed, %d new, %d updated, %d extracted in %.1fs",
                report.feeds_ok, report.feeds_failed, report.new_articles,
                report.updated_articles, report.extracted, report.duration_seconds(),
            )
            return self.last_report or {}

    def _select_feeds(self, only_source: str | None) -> list[FeedSpec]:
        if only_source:
            return [feed for feed in FEEDS_BY_SOURCE.get(only_source, [])]
        rows = db.query("SELECT url, next_fetch_at, consecutive_failures FROM feeds WHERE enabled=1")
        due: dict[str, object] = {}
        for row in rows:
            next_at = parse_iso(row["next_fetch_at"])
            if next_at is None or next_at <= now():
                due[row["url"]] = row
        # New feeds (not yet in DB) are always due.
        known_urls = {row["url"] for row in rows}
        selected = [
            feed for feed in FEEDS
            if feed.url in due or feed.url not in known_urls
        ]
        if not selected:  # everything is backing off; sweep anyway
            selected = list(FEEDS)
        random.shuffle(selected)
        return selected

    def _fetch_all(self, feeds: list[FeedSpec], report: RunReport, clusterer: stories.Clusterer):
        """Fetch concurrently and store each feed as soon as it arrives.

        Storing incrementally means a fresh install shows its first stories
        within seconds instead of waiting for a 400-feed sweep to finish.
        """
        outcomes: list[FeedOutcome] = []
        affected: set[int] = set()
        total = max(len(feeds), 1)
        lock = threading.Lock()
        storage_lock = threading.Lock()

        def work(feed: FeedSpec) -> FeedOutcome:
            return self._fetch_one(feed)

        with concurrent.futures.ThreadPoolExecutor(max_workers=settings.ingest_workers) as pool:
            futures = {pool.submit(work, feed): feed for feed in feeds}
            for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
                outcome = future.result()
                outcomes.append(outcome)
                if outcome.ok:
                    report.feeds_ok += 1
                    items = getattr(outcome, "items_payload", [])
                    if items:
                        with storage_lock:
                            try:
                                new, updated, story_ids = self._store_feed(outcome.feed, items, clusterer)
                                with lock:
                                    report.new_articles += new
                                    report.updated_articles += updated
                                    affected.update(story_ids)
                            except Exception:
                                log.exception("storing feed %s failed", outcome.feed.url)
                                outcome.ok = False
                                outcome.error = "database error while storing items"
                if not outcome.ok:
                    report.feeds_failed += 1
                    if len(report.errors) < 40:
                        report.errors.append(
                            {
                                "source": outcome.feed.source_id,
                                "url": outcome.feed.url,
                                "error": outcome.error,
                                "blocked": outcome.blocked,
                            }
                        )
                with lock:
                    self._set_progress(index / total * 0.9, f"Fetching feeds ({index}/{total})")
        return outcomes, affected

    def _fetch_one(self, feed: FeedSpec) -> FeedOutcome:
        outcome = FeedOutcome(feed=feed)
        started = time.monotonic()
        try:
            if feed.kind == "espn":
                items = self._espn_items(feed)
                outcome.ok = True
                outcome.items = len(items)
                outcome.items_payload = items  # type: ignore[attr-defined]
                return outcome
            row = db.query_one("SELECT etag, last_modified FROM feeds WHERE url=?", (feed.url,))
            etag = row["etag"] if row else None
            last_modified = row["last_modified"] if row else None
            result = self.client.get_text(feed.url, etag=etag, last_modified=last_modified,
                                          timeout=settings.feed_timeout_seconds)
            outcome.status = result.status
            outcome.elapsed_ms = result.elapsed_ms
            if result.not_modified:
                outcome.ok = True
                return outcome
            if result.status in (401, 402):
                outcome.error = f"HTTP {result.status} (subscription required)"
                outcome.blocked = True
                return outcome
            if result.status in (403, 451):
                outcome.error = f"HTTP {result.status} (access blocked)"
                outcome.blocked = True
                return outcome
            if not result.ok:
                outcome.error = f"HTTP {result.status}"
                return outcome
            parsed = feedparse.parse_feed(result.text, feed.url)
            outcome.etag = result.etag
            outcome.last_modified = result.last_modified
            items = parsed.items[: settings.max_articles_per_feed]
            outcome.items = len(items)
            outcome.items_payload = items  # type: ignore[attr-defined]
            outcome.ok = True
            self._mark_feed_success(feed, outcome, parsed)
            return outcome
        except FetchError as exc:
            outcome.error = str(exc)
            return outcome
        except feedparse.FeedError as exc:
            outcome.error = str(exc)
            outcome.blocked = exc.blocked
            return outcome
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("feed %s crashed", feed.url)
            outcome.error = f"{type(exc).__name__}: {exc}"
            return outcome
        finally:
            if not outcome.ok:
                self._mark_feed_failure(feed, outcome)
            outcome.elapsed_ms = outcome.elapsed_ms or int((time.monotonic() - started) * 1000)

    def _espn_items(self, feed: FeedSpec) -> list[feedparse.FeedItem]:
        league = feed.url.split(":", 1)[1]
        raw = sports.news(league, limit=settings.max_articles_per_feed)
        items: list[feedparse.FeedItem] = []
        for entry in raw:
            items.append(
                feedparse.FeedItem(
                    guid=entry["guid"],
                    title=entry["title"],
                    link=entry["link"],
                    summary_html=entry.get("summary") or "",
                    content_html="",
                    author=entry.get("byline"),
                    published_raw=entry.get("published"),
                    image=entry.get("image"),
                    categories=[entry.get("league_label") or league],
                )
            )
        return items

    # --------------------------------------------------------------- storage
    def _store_feed(
        self, feed: FeedSpec, items: list[feedparse.FeedItem], clusterer: stories.Clusterer
    ) -> tuple[int, int, set[int]]:
        source = SOURCES.get(feed.source_id)
        if source is None:
            return 0, 0, set()
        weight = 1.15 if source.id in _FLAGSHIP else (0.92 if source.paywall else 1.0)
        feed_row = db.query_one("SELECT id FROM feeds WHERE url=?", (feed.url,))
        feed_id = feed_row["id"] if feed_row else None
        seen_at = iso()
        new_count = 0
        updated_count = 0
        story_ids: set[int] = set()

        with db.writer() as conn:
            for item in items:
                link = (item.link or "").strip()
                if link and not link.startswith("http"):
                    link = urllib.parse.urljoin(feed.url, link)
                if not link.startswith("http"):
                    continue
                title = htmltext.clean_title(item.title)
                if len(title) < 6:
                    continue
                published, confidence, raw_date = parse_date(item.published_raw)
                if published is None and item.updated_raw:
                    published, confidence, raw_date = parse_date(item.updated_raw)
                summary_html = item.best_html
                summary = htmltext.clean_summary(summary_html, limit=600)
                primary, topic_list = topics.classify(title, summary, feed.topic, source.topics)
                image = _safe_image(item.image or htmltext.first_image(summary_html))
                video_kind, video_id, video_url = _safe_video(item.video_kind, item.video_id, item.video_url)
                if video_kind == "youtube" and video_id and not image:
                    image = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                if video_kind == "youtube":
                    summary = _video_summary(summary)
                guid = (item.guid or link)[:900]
                signature = hashlib.sha1(" ".join(sorted(stories.tokens_for(title))).encode()).hexdigest()[:20]
                # first_seen_at is when *we* saw it, never the publisher's date.
                first_seen = seen_at
                content_text = htmltext.text_of(summary_html)[:20000] if summary_html else None
                words = htmltext.word_count(content_text or "")
                minutes = htmltext.reading_minutes(content_text or "")
                paywalled = int(bool(item.is_paywalled or (source.paywall and words < 120)))
                params = (
                    guid, source.id, feed_id, link, link, title[:500], summary or None,
                    (item.author or None), image, video_url, video_id, video_kind,
                    iso(published) if published else None, raw_date,
                    confidence, iso(published) if published else None, first_seen, seen_at,
                    primary, json.dumps(topic_list), "en", words, minutes,
                    content_text or None, None, "feed", paywalled, 0, signature, weight,
                )
                cur = conn.execute(
                    """
                    INSERT INTO articles(
                        guid, source_id, feed_id, url, canonical_url, title, summary, author,
                        image_url, video_url, video_id, video_kind, published_at, published_raw,
                        date_confidence, updated_at, first_seen_at, last_seen_at, primary_topic,
                        topics, lang, word_count, reading_minutes, content_text, content_blocks,
                        content_state, paywalled, is_breaking, simhash, source_weight
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(source_id, guid) DO NOTHING
                    RETURNING id
                    """,
                    params,
                ).fetchone()
                if cur is not None:
                    article_id = cur["id"]
                    new_count += 1
                    match = clusterer.match(title, primary)
                    if match is not None:
                        story_id = match.id
                        conn.execute("UPDATE articles SET story_id=? WHERE id=?", (story_id, article_id))
                        match.last_seen_at = seen_at
                        clusterer.extend(match, title)
                        if len(title) < len(match.title) and len(title.split()) >= 5:
                            match.title = title
                        story_ids.add(story_id)
                    else:
                        story_id = self._create_story(conn, title, primary, article_id, published or seen_at, seen_at)
                        # Link the seed article too, otherwise the story would
                        # look like it had one fewer article than it does.
                        conn.execute("UPDATE articles SET story_id=? WHERE id=?", (story_id, article_id))
                        story_ids.add(story_id)
                        clusterer.add(stories.StoryRef(id=story_id, title=title, topic=primary, last_seen_at=seen_at))
                else:
                    row = conn.execute(
                        "SELECT id, story_id FROM articles WHERE source_id=? AND guid=?",
                        (source.id, guid),
                    ).fetchone()
                    if row is None:
                        continue
                    article_id = row["id"]
                    if row["story_id"]:
                        story_ids.add(row["story_id"])
                    conn.execute("UPDATE articles SET last_seen_at=? WHERE id=?", (seen_at, article_id))
                    updated_count += 1
                    # Fill in fields a thinner first sighting may have missed.
                    conn.execute(
                        """
                        UPDATE articles SET
                            summary = CASE WHEN (summary IS NULL OR length(summary) < 40) AND ? IS NOT NULL THEN ? ELSE summary END,
                            image_url = COALESCE(image_url, ?),
                            video_url = COALESCE(video_url, ?),
                            video_id = COALESCE(video_id, ?),
                            video_kind = COALESCE(video_kind, ?),
                            author = COALESCE(author, ?),
                            published_at = COALESCE(published_at, ?),
                            date_confidence = CASE WHEN published_at IS NULL AND ? IS NOT NULL THEN ? ELSE date_confidence END,
                            content_text = CASE WHEN content_text IS NULL OR length(content_text) < 40 THEN COALESCE(?, content_text) ELSE content_text END
                        WHERE id = ?
                        """,
                        (
                            summary or None, summary or None, image, video_url, video_id, video_kind,
                            item.author or None, iso(published) if published else None,
                            iso(published) if published else None, confidence,
                            content_text or None, article_id,
                        ),
                    )
        return new_count, updated_count, story_ids

    def _create_story(self, conn, title: str, topic: str, article_id: int,
                      published_at: str | None, seen_at: str) -> int:
        key = stories.story_key(title)
        existing = conn.execute("SELECT id FROM stories WHERE key=?", (key,)).fetchone()
        if existing:
            key = f"{key}-{article_id}"
        cur = conn.execute(
            """
            INSERT INTO stories(key, title, primary_topic, first_seen_at, last_seen_at,
                                article_count, source_count, lead_article_id, heat, breaking)
            VALUES(?,?,?,?,?,1,1,?,?,0)
            RETURNING id
            """,
            (key, title[:400], topic, published_at or seen_at, seen_at, article_id, 1.0),
        ).fetchone()
        return int(cur["id"])

    def _update_story(self, story_id: int) -> None:
        with db.writer() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS articles, COUNT(DISTINCT source_id) AS sources,
                       MIN(first_seen_at) AS first_seen, MAX(COALESCE(published_at, first_seen_at)) AS last_seen
                FROM articles WHERE story_id=?
                """,
                (story_id,),
            ).fetchone()
            if row is None or not row["articles"]:
                return
            lead = conn.execute(
                """
                SELECT id, url, title FROM articles
                WHERE story_id=?
                ORDER BY (image_url IS NOT NULL) DESC, (content_state='extracted') DESC,
                         length(COALESCE(content_text,'')) DESC, COALESCE(published_at, first_seen_at) DESC
                LIMIT 1
                """,
                (story_id,),
            ).fetchone()
            titles = [r["title"] for r in conn.execute(
                "SELECT title FROM articles WHERE story_id=? ORDER BY COALESCE(published_at, first_seen_at) DESC LIMIT 6",
                (story_id,),
            )]
            best = stories.best_title(titles) or (lead["title"] if lead else "")
            heat = stories.heat_score(row["sources"], row["articles"], iso(now()))
            breaking = stories.is_breaking(row["sources"], row["first_seen"])
            conn.execute(
                """
                UPDATE stories SET title=COALESCE(NULLIF(?, ''), title), article_count=?, source_count=?,
                    last_seen_at=?, lead_article_id=?, heat=?, breaking=?
                WHERE id=?
                """,
                (best, row["articles"], row["sources"], iso(now()), lead["id"] if lead else None,
                 heat, int(breaking), story_id),
            )
            if breaking:
                conn.execute(
                    "UPDATE articles SET is_breaking=1 WHERE story_id=? AND COALESCE(published_at, first_seen_at) >= ?",
                    (story_id, iso(now() - timedelta(hours=8))),
                )

    # ------------------------------------------------------------ extraction
    def _extract_pending(self) -> int:
        limit = settings.extract_per_cycle
        if limit <= 0:
            return 0
        cutoff = iso(now() - timedelta(days=4))
        rows = db.query(
            """
            SELECT a.id, a.url, a.source_id, a.published_at, a.first_seen_at
            FROM articles a LEFT JOIN stories s ON s.id = a.story_id
            WHERE a.content_state IN ('feed', 'linkonly') AND a.paywalled=0
              AND a.video_kind IS NULL
              AND (a.content_state='feed' OR a.url LIKE '%/video/%' OR a.url LIKE '%/videos/%' OR a.url LIKE '%/watch/%')
              AND COALESCE(a.published_at, a.first_seen_at) >= ?
            ORDER BY COALESCE(s.heat, 0) DESC, COALESCE(a.published_at, a.first_seen_at) DESC
            LIMIT ?
            """,
            (cutoff, limit),
        )
        if not rows:
            return 0
        extracted = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=settings.extract_workers) as pool:
            futures = [pool.submit(self._extract_one, row) for row in rows]
            for future in concurrent.futures.as_completed(futures):
                try:
                    if future.result():
                        extracted += 1
                except Exception:
                    log.exception("article extraction crashed")
        return extracted

    def _extract_one(self, row) -> bool:
        url = row["url"]
        try:
            if not robots_allowed(url, self.client):
                self._set_content_state(row["id"], "linkonly")
                return False
            result = self.client.fetch(
                url,
                accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
                timeout=settings.article_timeout_seconds,
                retries=1,
            )
            if result.status in (401, 402):
                self._set_content_state(row["id"], "paywalled")
                return False
            if not result.ok or not result.body:
                self._set_content_state(row["id"], "linkonly")
                return False
            content_type = result.headers.get("content-type", "")
            if content_type and "html" not in content_type and "xml" not in content_type:
                self._set_content_state(row["id"], "linkonly")
                return False
            parsed = htmltext.extract_article(result.text, url)
            if parsed.video_kind:
                self._save_video(row["id"], parsed)
            if parsed.paywall and parsed.word_count < 200:
                self._set_content_state(row["id"], "paywalled")
                return False
            if parsed.word_count < 60 or not parsed.blocks:
                self._set_content_state(row["id"], "linkonly")
                return False

            blocks = htmltext.clean_blocks([b.to_dict() for b in parsed.blocks])
            text = "\n\n".join(b.get("text", "") for b in blocks)[:60000]
            if not settings.archive_full_text:
                text = text[:1500]
            words = htmltext.word_count(" ".join(b.get("text", "") for b in blocks))
            minutes = htmltext.reading_minutes(" ".join(b.get("text", "") for b in blocks))
            published, confidence, raw = parse_date(parsed.published_hint)
            with db.writer() as conn:
                conn.execute(
                    """
                    UPDATE articles SET content_blocks=?, content_text=?, word_count=?, reading_minutes=?,
                        content_state=?, image_url=COALESCE(image_url, ?), images=?, author=COALESCE(author, ?),
                        video_url=COALESCE(video_url, ?), video_id=COALESCE(video_id, ?), video_kind=COALESCE(video_kind, ?),
                        published_at=COALESCE(published_at, ?),
                        date_confidence=CASE WHEN published_at IS NULL AND ? IS NOT NULL THEN ? ELSE date_confidence END,
                        summary=CASE WHEN (summary IS NULL OR length(summary) < 120) AND ? <> '' THEN ? ELSE summary END
                    WHERE id=?
                    """,
                    (
                        json.dumps(blocks), text, words, minutes, "extracted",
                        _safe_image(parsed.image), json.dumps(parsed.images[:24]),
                        parsed.author or None,
                        parsed.video_url, parsed.video_id, parsed.video_kind,
                        iso(published) if published else None,
                        iso(published) if published else None, confidence,
                        htmltext.summarize(text, 2, 420), htmltext.summarize(text, 2, 420),
                        row["id"],
                    ),
                )
            return True
        except FetchError as exc:
            log.debug("extract failed for %s: %s", url, exc)
            self._set_content_state(row["id"], "linkonly")
            return False
        except Exception:
            log.exception("extract crashed for %s", url)
            self._set_content_state(row["id"], "linkonly")
            return False

    def _save_video(self, article_id: int, parsed: htmltext.ExtractedArticle) -> None:
        """Store a clip even when the page has no readable article body."""
        kind, video_id, video_url = _safe_video(parsed.video_kind, parsed.video_id, parsed.video_url)
        if not kind:
            return
        image = _safe_image(parsed.image)
        if kind == "youtube" and video_id and not image:
            image = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        try:
            with db.writer() as conn:
                conn.execute(
                    """
                    UPDATE articles SET
                        video_url=COALESCE(video_url, ?),
                        video_id=COALESCE(video_id, ?),
                        video_kind=COALESCE(video_kind, ?),
                        image_url=COALESCE(image_url, ?)
                    WHERE id=?
                    """,
                    (video_url, video_id, kind, image, article_id),
                )
        except Exception:
            log.exception("could not save video for article %s", article_id)

    def _set_content_state(self, article_id: int, state: str) -> None:
        try:
            db.execute("UPDATE articles SET content_state=? WHERE id=?", (state, article_id))
        except Exception:
            pass

    # ----------------------------------------------------------- feed health
    def _mark_feed_success(self, feed: FeedSpec, outcome: FeedOutcome, parsed: feedparse.ParsedFeed) -> None:
        try:
            with db.writer() as conn:
                conn.execute(
                    """
                    UPDATE feeds SET last_fetch_at=?, last_success_at=?, last_status=?, last_error=NULL,
                        fetch_ms=?, consecutive_failures=0, item_count=?, blocked=0,
                        etag=COALESCE(?, etag), last_modified=COALESCE(?, last_modified),
                        total_fetches=total_fetches+1, next_fetch_at=?
                    WHERE url=?
                    """,
                    (
                        iso(), iso(), outcome.status, outcome.elapsed_ms, outcome.items,
                        outcome.etag, outcome.last_modified,
                        iso(now() + timedelta(seconds=settings.ingest_interval_seconds)), feed.url,
                    ),
                )
        except Exception:
            log.exception("could not record feed success")

    def _mark_feed_failure(self, feed: FeedSpec, outcome: FeedOutcome) -> None:
        try:
            with db.writer() as conn:
                row = conn.execute(
                    "SELECT consecutive_failures FROM feeds WHERE url=?", (feed.url,)
                ).fetchone()
                failures = (row["consecutive_failures"] if row else 0) + 1
                base = settings.ingest_interval_seconds
                backoff = min(base * (2 ** min(failures, 6)), 6 * 3600)
                if outcome.blocked:
                    backoff = max(backoff, 3 * 3600)
                conn.execute(
                    """
                    UPDATE feeds SET last_fetch_at=?, last_status=?, last_error=?, fetch_ms=?,
                        consecutive_failures=?, blocked=?, total_fetches=total_fetches+1,
                        next_fetch_at=?
                    WHERE url=?
                    """,
                    (
                        iso(), outcome.status, (outcome.error or "unknown error")[:400],
                        outcome.elapsed_ms, failures, int(outcome.blocked),
                        iso(now() + timedelta(seconds=int(backoff) + random.randint(0, 60))), feed.url,
                    ),
                )
        except Exception:
            log.exception("could not record feed failure")

    # --------------------------------------------------------------- reports
    def _record_run(self, report: RunReport) -> None:
        try:
            with db.writer() as conn:
                conn.execute(
                    """
                    INSERT INTO ingest_runs(started_at, finished_at, feeds_ok, feeds_failed,
                                            new_articles, updated_articles, errors)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        report.started_at, report.finished_at, report.feeds_ok, report.feeds_failed,
                        report.new_articles, report.updated_articles,
                        json.dumps(report.errors[:25]),
                    ),
                )
                conn.execute(
                    "DELETE FROM ingest_runs WHERE id NOT IN (SELECT id FROM ingest_runs ORDER BY id DESC LIMIT 60)"
                )
        except Exception:
            pass

    def _set_progress(self, value: float, label: str) -> None:
        with self._status_lock:
            self.progress = round(max(0.0, min(1.0, value)), 3)
            self.progress_label = label

    def status(self) -> dict:
        last = self.last_report or {}
        return {
            "running": self.running,
            "progress": self.progress,
            "label": self.progress_label,
            "next_run_at": self.next_run_at,
            "interval_seconds": settings.ingest_interval_seconds,
            "enabled": settings.ingest_enabled,
            "last_run": last,
            "started_at": self.started_at,
            "feeds_total": len(FEEDS),
            "sources_total": len(SOURCES),
        }


def _video_summary(text: str) -> str:
    """Keep the news, drop the YouTube housekeeping."""
    if not text:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    keep: list[str] = []
    for sentence in sentences:
        low = sentence.lower()
        if any(marker in low for marker in (
            "subscribe", "watch pbs", "watch the full", "watch more", "watch live",
            "follow us", "listen to", "read more", "full episode", "sign up",
            "download the", "get the latest", "watch our", "watch now",
        )):
            continue
        keep.append(sentence.strip())
        if len(" ".join(keep)) > 320:
            break
    return " ".join(keep)[:420].strip() or text[:420]


def _safe_video(kind: str | None, video_id: str | None, url: str | None) -> tuple[str | None, str | None, str | None]:
    if kind not in ("youtube", "vimeo", "file"):
        return (None, None, None)
    if kind in ("youtube", "vimeo"):
        if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
            return (None, None, None)
        if kind == "youtube":
            return (kind, video_id, f"https://www.youtube.com/watch?v={video_id}")
        return (kind, video_id, f"https://vimeo.com/{video_id}")
    if not url or not url.startswith(("http://", "https://")):
        return (None, None, None)
    return (kind, None, url[:1500])


def _safe_image(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return None
    lowered = url.lower()
    if any(bad in lowered for bad in ("pixel", "spacer", "1x1", "transparent.gif", "feedburner.com/~ff", "doubleclick")):
        return None
    if len(url) > 1500:
        return None
    return url


ingest = IngestService()
