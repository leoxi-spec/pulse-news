"""JSON API.

Conventions:
  * every handler returns ``(status, payload)`` and errors are JSON
  * profile identity comes from a signed-by-entropy cookie issued by the server
  * mutating requests must carry ``X-Pulse-Client`` (CSRF defence in depth,
    alongside SameSite=Lax) unless an access token is configured
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import timedelta

from . import ai, auth, citations, daily, feed, impact, ingest, profiles, rank, search, sports, stories, translate, weather
from .config import APP_NAME, APP_TAGLINE, APP_VERSION, settings
from .db import db
from .httpclient import FetchError, FetchResult, HttpClient, validate_url
from .logging_setup import get_logger
from .sources import (
    SOURCES, TOPICS, TOPIC_ICONS, TOPIC_LABELS, catalog_stats, get_source,
)
from .timeutil import absolute, iso, now, relative

log = get_logger("api")
_client = HttpClient()

MAX_BODY = 1_000_000


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    profile_id: str | None = None
    client_id: str | None = None
    remote: str = ""
    account: dict | None = None

    def json(self) -> dict:
        if not self.body:
            return {}
        if len(self.body) > MAX_BODY:
            raise ValueError("body too large")
        try:
            data = json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid JSON body") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def int_param(self, name: str, default: int, *, minimum: int = 0, maximum: int = 1000) -> int:
        try:
            value = int(self.query.get(name, default))
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, value))


class ApiError(Exception):
    def __init__(self, status: int, message: str, *, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


def handle(request: Request) -> tuple[int, dict, dict]:
    """Return (status, payload, extra_headers)."""
    try:
        profile = profiles.ensure(request.profile_id)
    except Exception:
        log.exception("profile bootstrap failed")
        profile = profiles.create()

    account = auth.session_user(request)
    request.account = account
    if account and account.get("profile_id"):
        linked = profiles.get(account["profile_id"])
        if linked:
            profile = linked
    request.profile_id = profile["id"]

    path = request.path
    method = request.method

    try:
        if path == "/api/bootstrap" and method == "GET":
            return 200, _bootstrap(profile, request), {}
        if path == "/api/auth/signup" and method == "POST":
            payload = request.json()
            try:
                result = auth.signup(
                    str(payload.get("email", "")),
                    str(payload.get("password", "")),
                    str(payload.get("name", "")),
                    request.profile_id,
                    request.remote,
                )
            except auth.AuthError as exc:
                raise ApiError(exc.status, exc.message) from exc
            return 201, {"account": result["account"], "profile": result["profile"]}, {
                "Set-Profile": result["profile"]["id"],
                "Set-Cookie": auth.cookie(result["token"], secure=_secure_request(request)),
            }
        if path == "/api/auth/login" and method == "POST":
            payload = request.json()
            try:
                result = auth.login(
                    str(payload.get("email", "")),
                    str(payload.get("password", "")),
                    request.remote,
                )
            except auth.AuthError as exc:
                raise ApiError(exc.status, exc.message) from exc
            return 200, {"account": result["account"], "profile": result["profile"]}, {
                "Set-Profile": result["profile"]["id"],
                "Set-Cookie": auth.cookie(result["token"], secure=_secure_request(request)),
            }
        if path == "/api/auth/logout" and method == "POST":
            auth.logout(request)
            guest = profiles.create()
            return 200, {"ok": True, "profile": guest}, {
                "Set-Profile": guest["id"],
                "Set-Cookie": auth.clear_cookie(secure=_secure_request(request)),
            }
        if path == "/api/auth/delete" and method == "POST":
            if not request.account:
                raise ApiError(401, "Sign in first")
            payload = request.json()
            try:
                auth.delete_account(request.account["id"], str(payload.get("password", "")))
            except auth.AuthError as exc:
                raise ApiError(exc.status, exc.message) from exc
            guest = profiles.create()
            return 200, {"ok": True, "profile": guest}, {
                "Set-Profile": guest["id"],
                "Set-Cookie": auth.clear_cookie(secure=_secure_request(request)),
            }
        if path == "/api/auth/me" and method == "GET":
            return 200, {"account": auth.public(request.account)}, {}
        if path == "/api/admin/users" and method == "GET":
            if not request.account or not request.account.get("is_admin"):
                raise ApiError(403, "Admin access only")
            users = auth.all_users()
            return 200, {"users": users, "count": len(users)}, {}
        if path == "/api/admin/users.csv" and method == "GET":
            if not request.account or not request.account.get("is_admin"):
                raise ApiError(403, "Admin access only")
            return 200, auth.users_csv(), {
                "Content-Type": "text/csv; charset=utf-8",
                "Content-Disposition": 'attachment; filename="pulse-users.csv"',
            }
        if path == "/api/health" and method == "GET":
            return 200, _health(), {}
        if path == "/api/profiles" and method == "POST":
            payload = request.json()
            created = profiles.create(str(payload.get("name") or "Student"))
            return 201, {"profile": created}, {"Set-Profile": created["id"]}
        if path == "/api/profile" and method in ("PATCH", "POST", "PUT"):
            payload = request.json()
            updated = profiles.update(
                profile["id"],
                name=payload.get("name"),
                survey=payload.get("survey"),
                prefs=payload.get("prefs"),
                onboarded=payload.get("onboarded"),
            )
            if request.account and payload.get("name") is not None:
                auth.rename(request.account["id"], updated.get("name") or "Student")
            return 200, {"profile": updated}, {}
        if path == "/api/profile" and method == "GET":
            return 200, {"profile": profiles.get(profile["id"])}, {}
        if path == "/api/profile/stats" and method == "GET":
            return 200, {"stats": profiles.stats(profile["id"]), "profile": profiles.get(profile["id"])}, {}
        if path == "/api/profile/export" and method == "GET":
            return 200, profiles.export(profile["id"]), {}
        if path == "/api/profile/reset" and method == "POST":
            profiles.delete(profile["id"])
            new_profile = profiles.create()
            if request.account:
                auth.link_profile(request.account["id"], new_profile["id"])
            return 200, {"profile": new_profile}, {"Set-Profile": new_profile["id"]}
        if path == "/api/profile/follows" and method == "POST":
            payload = request.json()
            profiles.follow(profile["id"], str(payload.get("kind", "")), str(payload.get("value", "")), on=bool(payload.get("on", True)))
            return 200, {"ok": True, "profile": profiles.get(profile["id"])}, {}
        if path == "/api/events" and method == "POST":
            payload = request.json()
            result = profiles.record_event(
                profile["id"],
                str(payload.get("kind", "view"))[:40],
                article_id=_optional_int(payload.get("article_id")),
                story_id=_optional_int(payload.get("story_id")),
                value=float(payload.get("value") or 0),
                meta=payload.get("meta") if isinstance(payload.get("meta"), dict) else None,
            )
            return 200, {"progress": result, "profile": profiles.get(profile["id"])}, {}
        if path == "/api/feed" and method == "GET":
            mode = (request.query.get("mode") or "for-you").lower()
            topic = request.query.get("topic") or None
            source = _source_or_none(request.query.get("source"))
            offset = request.int_param("offset", 0, minimum=0, maximum=5000)
            limit = request.int_param("limit", 24, minimum=1, maximum=60)
            days = request.int_param("days", 3, minimum=1, maximum=365)
            payload = feed.feed_page(profile, mode=mode, topic=topic, source=source, offset=offset, limit=limit, days=days)
            return 200, payload, {}
        if path == "/api/weather" and method == "GET":
            return 200, weather.current(), {}
        if path == "/api/impact" and method == "GET":
            return 200, impact.metrics(profile), {}
        if path == "/api/impact/report" and method == "GET":
            data = impact.metrics(profile)
            return 200, {"markdown": impact.report_markdown(data), "filename": "pulse-impact-report.md"}, {}
        if path == "/api/press-kit" and method == "GET":
            data = impact.metrics(profile)
            return 200, {"markdown": impact.press_kit_markdown(data), "filename": "pulse-press-kit.md"}, {}
        if path == "/api/roadmap" and method == "GET":
            return 200, {"items": impact.roadmap(profile["id"]), "categories": impact.FEEDBACK_CATEGORIES}, {}
        if path == "/api/roadmap/vote" and method == "POST":
            payload = request.json()
            try:
                item = impact.vote(profile["id"], str(payload.get("id") or ""), on=bool(payload.get("on", True)))
            except ValueError as exc:
                raise ApiError(400, str(exc)) from exc
            return 200, {"item": item}, {}
        if path == "/api/feedback" and method == "POST":
            payload = request.json()
            try:
                result = impact.add_feedback(
                    profile["id"],
                    str(payload.get("category") or "other"),
                    str(payload.get("message") or ""),
                    str(payload.get("email") or ""),
                )
            except ValueError as exc:
                raise ApiError(400, str(exc)) from exc
            return 201, result, {}
        if path == "/api/videos" and method == "GET":
            topic = request.query.get("topic") or None
            offset = request.int_param("offset", 0, minimum=0, maximum=5000)
            limit = request.int_param("limit", 24, minimum=1, maximum=60)
            days = request.int_param("days", 60, minimum=1, maximum=365)
            return 200, feed.video_feed(profile, topic=topic, offset=offset, limit=limit, days=days), {}
        if path == "/api/discover" and method == "GET":
            return 200, feed.discover(profile), {}
        if path == "/api/brief" and method == "GET":
            return 200, profiles.daily_brief(profile["id"], size=request.int_param("size", 5, minimum=3, maximum=10)), {}
        if path == "/api/daily" and method == "GET":
            return 200, daily.payload(profile["id"]), {}
        if path == "/api/random" and method == "GET":
            row = db.query_one(
                """SELECT id FROM articles
                   WHERE content_state='extracted' AND length(COALESCE(content_text,'')) > 1200
                   ORDER BY RANDOM() LIMIT 1"""
            )
            if row is None:
                row = db.query_one("SELECT id FROM articles ORDER BY RANDOM() LIMIT 1")
            if row is None:
                raise ApiError(404, "The archive is empty")
            return 200, {"id": int(row["id"])}, {}
        if path == "/api/brief/complete" and method == "POST":
            result = profiles.record_event(profile["id"], "brief_complete", value=1)
            return 200, {"progress": result}, {}
        if path == "/api/saved" and method == "GET":
            collection = request.query.get("collection") or None
            items = profiles.saved(profile["id"], collection)
            return 200, {
                "items": translate.localize_items([feed.card(row, saved_ids={row["id"]}) for row in items], sync_limit=4),
                "collections": profiles.collections(profile["id"]),
                "collection": collection,
            }, {}
        if path == "/api/keyword" and method == "GET":
            query = (request.query.get("q") or "").strip()
            if not query:
                raise ApiError(400, "Add a keyword to browse.")
            sort = request.query.get("sort") or "relevance"
            if sort not in ("relevance", "newest", "latest"):
                sort = "relevance"
            if sort == "latest":
                sort = "newest"
            offset = request.int_param("offset", 0, minimum=0, maximum=5000)
            limit = request.int_param("limit", 24, minimum=1, maximum=60)
            return 200, feed.keyword_page(profile, query, offset=offset, limit=limit, sort=sort), {}
        if path == "/api/search" and method == "GET":
            query = request.query.get("q", "")
            result = search.search(
                query,
                topic=request.query.get("topic") or None,
                source=request.query.get("source") or None,
                since=request.query.get("since") or None,
                until=request.query.get("until") or None,
                sort=request.query.get("sort") or "relevance",
                limit=request.int_param("limit", 24, minimum=1, maximum=80),
                offset=request.int_param("offset", 0, minimum=0, maximum=5000),
            )
            if query.strip():
                try:
                    search.record_search(profile["id"], query, result["total"])
                except Exception:
                    pass
            return 200, result, {}
        if path == "/api/search/suggest" and method == "GET":
            return 200, search.suggestions(request.query.get("q", ""), limit=8), {}
        if path == "/api/research/bibliography" and method == "GET":
            style = (request.query.get("style") or "mla").lower()
            include_notes = request.query.get("include_notes") == "1"
            return 200, _bibliography(profile, style, include_notes), {}
        if path == "/api/research/cite" and method == "POST":
            payload = request.json()
            title = str(payload.get("title") or "").strip()
            if len(title) < 2:
                raise ApiError(400, "A title is required")
            article = {
                "title": title[:300],
                "author": str(payload.get("author") or "").strip()[:200] or None,
                "source_name": str(payload.get("outlet") or payload.get("source_name") or "").strip()[:200] or None,
                "url": str(payload.get("url") or "").strip()[:1200],
                "published_at": str(payload.get("published_at") or "").strip()[:40] or None,
            }
            return 200, {
                "citations": citations.all_citations(article),
                "styles": citations.available_styles(),
            }, {}
        if path == "/api/archive" and method == "GET":
            return 200, {
                "months": search.archive_index(request.query.get("topic") or None, limit=36),
                "summary": feed.archive_summary(),
            }, {}
        if path == "/api/sports" and method == "GET":
            leagues = [s for s in (request.query.get("leagues") or "").split(",") if s]
            payload = sports.all_scoreboards(force=request.query.get("force") == "1", leagues=leagues or None)
            return 200, payload, {}
        if path == "/api/sources" and method == "GET":
            return 200, _sources_index(request), {}
        if path == "/api/source-health" and method == "GET":
            return 200, {"feeds": db.source_health(), "summary": _feed_summary()}, {}
        if path == "/api/ai/status" and method == "GET":
            return 200, ai.status(), {}
        if path == "/api/ai/test" and method == "POST":
            return 200, ai.provider_test(), {}
        if path == "/api/ingest/status" and method == "GET":
            return 200, {**ingest.ingest.status(), "db": db.stats()}, {}
        if path == "/api/ingest/refresh" and method == "POST":
            started = ingest.ingest.trigger()
            return 202, {"started": started, "status": ingest.ingest.status()}, {}
        if path == "/api/img" and method == "GET":
            return _proxy_image(request)

        # ---------------------------------------------------------- articles
        match = re.fullmatch(r"/api/articles/(\d+)", path)
        if match and method == "GET":
            article = feed.article_detail(int(match.group(1)), profile)
            if article is None:
                raise ApiError(404, "Article not found")
            overview = ai.overview(article, kind="overview") if request.query.get("overview") != "0" else None
            article["overview"] = overview
            article["jargon"] = ai.decode_jargon(article.get("content_text") or article.get("summary") or "")
            return 200, {"article": article}, {}

        match = re.fullmatch(r"/api/articles/(\d+)/translation", path)
        if match and method == "GET":
            article = feed.article_detail(int(match.group(1)), profile)
            if article is None:
                raise ApiError(404, "Article not found")
            return 200, translate.full_article_translation(article, article.get("language")), {}

        match = re.fullmatch(r"/api/articles/(\d+)/overview", path)
        if match and method == "GET":
            row = _article_row(int(match.group(1)))
            payload = ai.overview(row, force=request.query.get("force") == "1")
            return 200, payload, {}

        match = re.fullmatch(r"/api/articles/(\d+)/explain", path)
        if match and method == "GET":
            row = _article_row(int(match.group(1)))
            return 200, ai.explain(row), {}

        match = re.fullmatch(r"/api/articles/(\d+)/quiz", path)
        if match and method == "GET":
            row = _article_row(int(match.group(1)))
            quiz = ai.quiz(row, count=request.int_param("count", 4, minimum=2, maximum=8))
            quiz["attempt_token"] = hashlib.sha1(f"{row['id']}:{quiz['generated_at']}".encode()).hexdigest()[:16]
            return 200, quiz, {}

        match = re.fullmatch(r"/api/articles/(\d+)/quiz-result", path)
        if match and method == "POST":
            payload = request.json()
            correct = bool(payload.get("correct"))
            article_id = int(match.group(1))
            result = profiles.record_event(
                profile["id"],
                "quiz_correct" if correct else "quiz_attempt",
                article_id=article_id,
                meta={"question": str(payload.get("question", ""))[:200], "selected": payload.get("selected")},
            )
            return 200, {"progress": result, "correct": correct}, {}

        match = re.fullmatch(r"/api/articles/(\d+)/citations", path)
        if match and method == "GET":
            article = feed.article_detail(int(match.group(1)), profile)
            if article is None:
                raise ApiError(404, "Article not found")
            return 200, {
                "citations": citations.all_citations(article),
                "styles": citations.available_styles(),
            }, {}

        match = re.fullmatch(r"/api/articles/(\d+)/notes", path)
        if match and method in ("GET", "POST"):
            article_id = int(match.group(1))
            if method == "GET":
                return 200, {"notes": profiles.notes(profile["id"], article_id)}, {}
            payload = request.json()
            note = profiles.add_note(
                profile["id"], article_id, str(payload.get("body", "")),
                quote=str(payload.get("quote", ""))[:800],
                start=_optional_int(payload.get("start")),
                end=_optional_int(payload.get("end")),
            )
            profiles.record_event(profile["id"], "note", article_id=article_id)
            return 201, {"note": note}, {}

        match = re.fullmatch(r"/api/notes/(\d+)", path)
        if match and method == "DELETE":
            profiles.delete_note(profile["id"], int(match.group(1)))
            return 200, {"ok": True}, {}

        match = re.fullmatch(r"/api/articles/(\d+)/save", path)
        if match:
            article_id = int(match.group(1))
            if method == "POST":
                payload = request.json()
                profiles.save(profile["id"], article_id, str(payload.get("collection") or "Saved"))
                profiles.record_event(profile["id"], "save", article_id=article_id)
                return 200, {"saved": True, "collections": profiles.collections(profile["id"])}, {}
            if method == "DELETE":
                profiles.unsave(profile["id"], article_id)
                return 200, {"saved": False, "collections": profiles.collections(profile["id"])}, {}

        match = re.fullmatch(r"/api/stories/(\d+)", path)
        if match and method == "GET":
            story = feed.story_detail(int(match.group(1)), profile)
            if story is None:
                raise ApiError(404, "Story not found")
            return 200, {"story": story}, {}

        match = re.fullmatch(r"/api/sources/([\w.-]+)", path)
        if match and method == "GET":
            return 200, _source_detail(match.group(1), profile), {}

        match = re.fullmatch(r"/api/sports/([\w.]+)/summary/(\d+)", path)
        if match and method == "GET":
            return 200, sports.game_summary(match.group(1), match.group(2)), {}
        match = re.fullmatch(r"/api/sports/([a-z0-9.]+)", path)
        if match and method == "GET":
            return 200, sports.league_scores(match.group(1)), {}

        raise ApiError(404, f"No route for {method} {path}")
    except ApiError:
        raise
    except ValueError as exc:
        raise ApiError(400, str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        log.exception("API error on %s %s", method, path)
        raise ApiError(500, "Internal server error") from exc


# ------------------------------------------------------------------ handlers
def _secure_request(request: Request) -> bool:
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    return proto == "https"


def _bootstrap(profile: dict, request: Request) -> dict:
    stats = db.stats()
    health = _feed_summary()
    return {
        "app": {
            "name": APP_NAME,
            "tagline": APP_TAGLINE,
            "version": APP_VERSION,
            "server_time": iso(),
            "server_tz": now().strftime("%Z"),
            "utm": None,
        },
        "catalog": {**catalog_stats(), "countries_list": _countries()},
        "topics": [{"slug": slug, "label": label, "icon": icon} for slug, label, icon in TOPICS],
        "sources": _compact_sources(),
        "profile": profile,
        "account": auth.public(request.account),
        "ai": ai.status(),
        "ingest": ingest.ingest.status(),
        "sports": {"leagues": sports.LEAGUES_PAYLOAD() if hasattr(sports, "LEAGUES_PAYLOAD") else [
            {"slug": l.slug, "label": l.label, "emoji": l.emoji, "group": l.group} for l in sports.LEAGUES
        ]},
        "stats": stats,
        "feed_health": health,
        "collections": profiles.collections(profile["id"]),
        "archive": feed.archive_summary(),
        "citation_styles": citations.available_styles(),
        "streams": _streams(),
        "server": {
            "csrf_header": "X-Pulse-Client",
            "token_required": bool(settings.access_token),
            "data_dir_hint": settings.data_dir.name,
        },
    }


def _health() -> dict:
    stats = db.stats()
    return {
        "ok": True,
        "app": {"name": APP_NAME, "version": APP_VERSION, "time": iso()},
        "articles": stats.get("articles", 0),
        "videos": stats.get("videos", 0),
        "sources": stats.get("sources", 0),
        "feeds_ok": stats.get("feeds_ok", 0),
        "last_ingest": stats.get("last_ingest"),
        "ai": ai.status()["enabled"],
        "sports": settings.sports_enabled,
        "archive": feed.archive_summary(),
        "ingest": ingest.ingest.status(),
    }


def _streams() -> list[dict]:
    return [
        {"id": "for-you", "label": "For you", "hint": "Ranked by your interests, follows and reading"},
        {"id": "top", "label": "Top", "hint": "The stories the most outlets are covering"},
        {"id": "breaking", "label": "Breaking", "hint": "Fast-moving stories from the last 24 hours"},
        {"id": "latest", "label": "Latest", "hint": "Strict reverse-chronological"},
        {"id": "longreads", "label": "Long reads", "hint": "Deep pieces worth the time"},
    ]


def _countries() -> list[dict]:
    counts: dict[str, int] = {}
    for source in SOURCES.values():
        counts[source.country] = counts.get(source.country, 0) + 1
    return sorted(
        ({"code": code, "count": count} for code, count in counts.items() if code and code != "INT"),
        key=lambda item: item["count"],
        reverse=True,
    )


def _compact_sources() -> list[dict]:
    return [
        {
            "id": source.id,
            "name": source.name,
            "domain": source.domain,
            "country": source.country,
            "region": source.region,
            "lean": source.lean,
            "paywall": source.paywall,
            "audience": source.audience,
            "topics": list(source.topics),
            "initials": source.initials,
            "teen_friendly": source.teen_friendly,
        }
        for source in sorted(SOURCES.values(), key=lambda s: s.name.lower())
    ]


def _sources_index(request: Request) -> dict:
    topic = request.query.get("topic") or None
    country = (request.query.get("country") or "").upper() or None
    query = (request.query.get("q") or "").lower()
    items = []
    for source in SOURCES.values():
        if topic and topic not in source.topics:
            continue
        if country and source.country != country:
            continue
        if query and query not in source.name.lower() and query not in source.domain.lower():
            continue
        items.append(
            {
                **source.to_dict(),
                "teen_friendly": source.teen_friendly,
            }
        )
    items.sort(key=lambda item: (-(len(item["topics"])), item["name"].lower()))
    return {"sources": items, "count": len(items)}


def _source_detail(source_id: str, profile: dict) -> dict:
    source = get_source(source_id)
    if source is None:
        raise ApiError(404, "Source not found")
    feeds = db.query(
        """SELECT url, topic, last_fetch_at, last_success_at, last_status, last_error,
                  consecutive_failures, item_count FROM feeds WHERE source_id=? ORDER BY topic""",
        (source_id,),
    )
    rows = feed.load_candidates(days=30, limit=24, source=source_id)
    model = rank.build_model(profile["id"], profile["survey"], profile["prefs"])
    saved_ids = {int(r["article_id"]) for r in db.query("SELECT article_id FROM saves WHERE profile_id=?", (profile["id"],))}
    articles = [feed.card(row, model=model, saved_ids=saved_ids) for row in rows]
    count = db.scalar("SELECT COUNT(*) FROM articles WHERE source_id=?", (source_id,), default=0)
    return {
        "source": {**source.to_dict(), "teen_friendly": source.teen_friendly},
        "feeds": [dict(row) for row in feeds],
        "articles": articles,
        "archive_count": int(count or 0),
    }


def _bibliography(profile: dict, style: str, include_notes: bool) -> dict:
    """A student's saved sources, formatted as a bibliography."""
    style = style if style in {item["id"] for item in citations.available_styles()} else "mla"
    rows = db.query(
        """
        SELECT a.id, a.title, a.url, a.author, a.published_at, a.first_seen_at,
               a.date_confidence, src.name AS source_name, s.collection, s.created_at AS saved_at
        FROM saves s
        JOIN articles a ON a.id = s.article_id
        JOIN sources src ON src.id = a.source_id
        WHERE s.profile_id = ?
        ORDER BY COALESCE(NULLIF(a.author, ''), src.name) COLLATE NOCASE, a.title COLLATE NOCASE
        """,
        (profile["id"],),
    )
    entries = []
    for row in rows:
        article = {
            "title": row["title"],
            "author": row["author"],
            "source_name": row["source_name"],
            "url": row["url"],
            "published_at": row["published_at"] or row["first_seen_at"],
        }
        entries.append(
            {
                "article_id": row["id"],
                "title": row["title"],
                "source": row["source_name"],
                "author": row["author"],
                "published_at": row["published_at"],
                "url": row["url"],
                "collection": row["collection"],
                "citation": citations.format_citation(article, style),
            }
        )
    notes = []
    if include_notes:
        note_rows = db.query(
            """
            SELECT n.id, n.quote, n.body, n.created_at, a.id AS article_id, a.title, a.url,
                   a.author, a.published_at, a.first_seen_at, src.name AS source_name
            FROM notes n
            JOIN articles a ON a.id = n.article_id
            JOIN sources src ON src.id = a.source_id
            WHERE n.profile_id = ?
            ORDER BY n.created_at DESC
            """,
            (profile["id"],),
        )
        for row in note_rows:
            article = {
                "title": row["title"], "author": row["author"], "source_name": row["source_name"],
                "url": row["url"], "published_at": row["published_at"] or row["first_seen_at"],
            }
            notes.append(
                {
                    "id": row["id"],
                    "quote": row["quote"],
                    "body": row["body"],
                    "created_at": row["created_at"],
                    "article_id": row["article_id"],
                    "title": row["title"],
                    "citation": citations.format_citation(article, style),
                }
            )
    combined = "\n\n".join(entry["citation"] for entry in entries)
    return {
        "style": style,
        "styles": citations.available_styles(),
        "count": len(entries),
        "entries": entries,
        "notes": notes,
        "combined": combined,
        "generated_at": iso(),
        "note": "Ordered by author, then title. Check each entry against your school's citation guide before submitting.",
    }


def _article_row(article_id: int) -> dict:
    row = db.query_one(
        """SELECT a.id, a.title, a.summary, a.url, a.published_at, a.first_seen_at, a.content_text,
                  a.content_state, a.paywalled, a.primary_topic, a.reading_minutes, a.word_count,
                  s.name AS source_name, COALESCE(st.source_count,1) AS story_source_count
           FROM articles a JOIN sources s ON s.id=a.source_id
           LEFT JOIN stories st ON st.id=a.story_id WHERE a.id=?""",
        (article_id,),
    )
    if row is None:
        raise ApiError(404, "Article not found")
    return dict(row)


def _feed_summary() -> dict:
    row = db.query_one(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN last_success_at IS NOT NULL AND consecutive_failures < 3 THEN 1 ELSE 0 END) AS healthy,
                  SUM(CASE WHEN consecutive_failures >= 3 THEN 1 ELSE 0 END) AS failing,
                  SUM(CASE WHEN blocked = 1 THEN 1 ELSE 0 END) AS blocked
           FROM feeds WHERE enabled=1"""
    )
    return {
        "total": int(row["total"] or 0) if row else 0,
        "healthy": int(row["healthy"] or 0) if row else 0,
        "failing": int(row["failing"] or 0) if row else 0,
        "blocked": int(row["blocked"] or 0) if row else 0,
    }


_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"}


def _proxy_image(request: Request) -> tuple[int, bytes | dict, dict]:
    raw = request.query.get("u", "")
    if not raw:
        raise ApiError(400, "Missing image URL")
    try:
        url = validate_url(raw)
    except FetchError as exc:
        raise ApiError(400, str(exc)) from exc
    digest = hashlib.sha1(url.encode()).hexdigest()
    cache_dir = settings.cache_dir / "img"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / digest
    if cached.exists():
        content_type = _read_sidecar(cache_dir, digest, "image/jpeg")
        return 200, cached.read_bytes(), {
            "Content-Type": content_type,
            "Cache-Control": "public, max-age=86400, immutable",
            "X-Content-Type-Options": "nosniff",
        }
    try:
        result: FetchResult = _client.fetch(
            url, accept="image/avif,image/webp,image/*;q=0.8,*/*;q=0.2", timeout=12, retries=1
        )
    except FetchError as exc:
        raise ApiError(502, f"Image fetch failed: {exc}") from exc
    if not result.ok or not result.body:
        raise ApiError(502, "Image unavailable")
    content_type = (result.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise ApiError(415, "Unsupported image type")
    if len(result.body) > 4_000_000:
        raise ApiError(413, "Image too large")
    # 1x1 tracking pixels and blank images render as empty boxes; treat them as
    # missing so the card falls back to its banner.
    if len(result.body) < 1200 and not content_type.endswith("svg+xml"):
        raise ApiError(404, "Image is too small to display")
    try:
        cached.write_bytes(result.body)
        _write_sidecar(cache_dir, digest, content_type)
    except OSError:
        pass
    return 200, result.body, {
        "Content-Type": content_type,
        "Cache-Control": "public, max-age=86400, immutable",
        "X-Content-Type-Options": "nosniff",
    }


def _sidecar(cache_dir, digest: str, suffix: str):
    return cache_dir / f"{digest}.{suffix}"


def _read_sidecar(cache_dir, digest: str, default: str) -> str:
    path = _sidecar(cache_dir, digest, "type")
    try:
        return path.read_text("utf-8").strip() or default
    except OSError:
        return default


def _write_sidecar(cache_dir, digest: str, content_type: str) -> None:
    try:
        _sidecar(cache_dir, digest, "type").write_text(content_type, "utf-8")
    except OSError:
        pass


def _source_or_none(value: str | None) -> str | None:
    if not value:
        return None
    return value if value in SOURCES else None


def _optional_int(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
