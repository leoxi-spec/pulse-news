"""Full-text search over the permanent archive.

FTS5 with field weights (headline > summary > body), plus the small filter
language people expect from a professional reader: ``topic:tech``,
``source:bbc``, ``after:2024-06-01``, ``before:``, ``is:breaking``.
Queries never fail on punctuation — they degrade to a sensible term search.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from .db import db
from .sources import SOURCES, TOPICS, TOPIC_LABELS, TOPIC_SLUGS
from .timeutil import iso

_TOKEN = re.compile(r"[^\s]+")
_FILTER = re.compile(r"^(-)?(source|topic|after|before|is|author):(.+)$", re.I)
_BM25_WEIGHTS = "6.0, 2.5, 1.0, 1.2"


@dataclass
class ParsedQuery:
    terms: list[str] = field(default_factory=list)
    phrases: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    after: str | None = None
    before: str | None = None
    flags: list[str] = field(default_factory=list)
    raw: str = ""

    @property
    def fts(self) -> str:
        parts: list[str] = []
        if self.phrases:
            parts.extend(f'"{p}"' for p in self.phrases)
        if self.terms:
            prefix = " ".join(f"{t}" for t in self.terms)
            parts.append(prefix)
        if not parts:
            return ""
        expression = " AND ".join(parts)
        for term in self.excluded:
            expression += f" NOT {term}"
        return expression


def parse_query(raw: str) -> ParsedQuery:
    parsed = ParsedQuery(raw=raw or "")
    text = (raw or "").strip()
    if not text:
        return parsed
    # Pull quoted phrases out first so "student loans" stays one phrase.
    for phrase in re.findall(r'"([^"]+)"', text):
        cleaned = _clean(phrase)
        if cleaned:
            parsed.phrases.append(cleaned)
    text = re.sub(r'"[^"]*"', " ", text)
    for token in _TOKEN.findall(text):
        negated_filter = False
        match = _FILTER.match(token)
        if match:
            negated_filter = bool(match.group(1))
            key = match.group(2).lower()
            value = match.group(3).strip().strip('"')
            if key == "source":
                resolved = _resolve_source(value)
                if resolved:
                    (parsed.excluded if negated_filter else parsed.sources).append(resolved)
                continue
            if key == "topic":
                if value.lower() in TOPIC_SLUGS:
                    (parsed.excluded if negated_filter else parsed.topics).append(value.lower())
                continue
            if key in ("after", "before"):
                parsed.after = value if key == "after" else parsed.after
                parsed.before = value if key == "before" else parsed.before
                continue
            if key == "is":
                parsed.flags.append(value.lower())
                continue
            if key == "author":
                parsed.terms.append(value)
                continue
        if token.startswith("-") and len(token) > 1:
            parsed.excluded.append(_clean(token[1:]))
        elif token.lower() in ("and", "or", "not"):
            continue
        else:
            parsed.terms.append(_clean(token))
    return parsed


def _clean(token: str) -> str:
    cleaned = re.sub(r'["\'()*:^]', " ", token).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _resolve_source(value: str) -> str | None:
    lowered = value.lower()
    if lowered in SOURCES:
        return lowered
    for source in SOURCES.values():
        if source.domain.lower().startswith(lowered) or lowered in source.name.lower():
            return source.id
    return None


def _fts_expression(parsed: ParsedQuery) -> str:
    expression = parsed.fts
    if not expression:
        return ""
    if parsed.terms:
        terms = []
        for term in parsed.terms:
            if " " in term:
                terms.append('"' + term + '"')
            else:
                terms.append(term)
        if len(parsed.terms) == 1 and len(parsed.terms[0]) >= 3:
            terms = [f"{parsed.terms[0]}*"]
        prefix = " AND ".join(terms)
        parts = []
        if parsed.phrases:
            parts.extend(f'"{p}"' for p in parsed.phrases)
        parts.append(prefix)
        expression = " AND ".join(parts)
        for term in parsed.excluded:
            expression += f" NOT {term}"
    return expression


def search(
    raw_query: str,
    *,
    topic: str | None = None,
    source: str | None = None,
    since: str | None = None,
    until: str | None = None,
    sort: str = "relevance",
    limit: int = 30,
    offset: int = 0,
) -> dict:
    parsed = parse_query(raw_query)
    if topic:
        parsed.topics.append(topic)
    if source:
        resolved = _resolve_source(source)
        if resolved:
            parsed.sources.append(resolved)
    if since:
        parsed.after = since
    if until:
        parsed.before = until

    expression = _fts_expression(parsed)
    where: list[str] = []
    params: list = []
    if parsed.sources:
        where.append("a.source_id IN (" + ",".join("?" for _ in parsed.sources) + ")")
        params.extend(parsed.sources)
    elif parsed.excluded and any(s for s in parsed.excluded if s in SOURCES):
        excluded_sources = [s for s in parsed.excluded if s in SOURCES]
        where.append("a.source_id NOT IN (" + ",".join("?" for _ in excluded_sources) + ")")
        params.extend(excluded_sources)
    if parsed.topics:
        where.append("a.primary_topic IN (" + ",".join("?" for _ in parsed.topics) + ")")
        params.extend(parsed.topics)
    if parsed.after:
        where.append("COALESCE(a.published_at, a.first_seen_at) >= ?")
        params.append(parsed.after)
    if parsed.before:
        where.append("COALESCE(a.published_at, a.first_seen_at) <= ?")
        params.append(parsed.before)
    if "breaking" in parsed.flags:
        where.append("a.is_breaking = 1")

    clauses = " AND ".join(where) if where else "1=1"

    if expression:
        order = (
            f"bm25(articles_fts, {_BM25_WEIGHTS}) + "
            "(julianday('now') - julianday(COALESCE(a.published_at, a.first_seen_at))) * 0.035"
            if sort == "relevance"
            else "COALESCE(a.published_at, a.first_seen_at) DESC"
        )
        sql = f"""
            SELECT a.id, a.title, a.summary, a.source_id, a.url, a.image_url, a.video_url, a.video_id, a.video_kind, a.author,
                   a.published_at, a.first_seen_at, a.date_confidence, a.primary_topic,
                   a.reading_minutes, a.word_count, a.content_state, a.paywalled, a.is_breaking,
                   a.story_id, s.name AS source_name, s.domain, s.lean,
                   COALESCE(st.source_count, 1) AS story_source_count,
                   COALESCE(st.heat, 0) AS story_heat,
                   COALESCE(st.article_count, 1) AS story_article_count,
                   bm25(articles_fts, {_BM25_WEIGHTS}) AS rank,
                   snippet(articles_fts, 2, '[[', ']]', ' … ', 28) AS snippet_body,
                   snippet(articles_fts, 1, '[[', ']]', ' … ', 28) AS snippet_summary
            FROM articles_fts
            JOIN articles a ON a.id = articles_fts.rowid
            JOIN sources s ON s.id = a.source_id
            LEFT JOIN stories st ON st.id = a.story_id
            WHERE articles_fts MATCH ? AND {clauses}
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """
        full_params = [expression, *params, limit + 1, offset]
        try:
            rows = db.query(sql, full_params)
        except sqlite3.OperationalError:
            rows = _fallback_search(parsed, clauses, params, sort, limit + 1, offset)
    else:
        order = "COALESCE(a.published_at, a.first_seen_at) DESC"
        sql = f"""
            SELECT a.id, a.title, a.summary, a.source_id, a.url, a.image_url, a.video_url, a.video_id, a.video_kind, a.author,
                   a.published_at, a.first_seen_at, a.date_confidence, a.primary_topic,
                   a.reading_minutes, a.word_count, a.content_state, a.paywalled, a.is_breaking,
                   a.story_id, s.name AS source_name, s.domain, s.lean,
                   COALESCE(st.source_count, 1) AS story_source_count,
                   COALESCE(st.heat, 0) AS story_heat,
                   COALESCE(st.article_count, 1) AS story_article_count,
                   0 AS rank,
                   '' AS snippet_body, '' AS snippet_summary
            FROM articles a
            JOIN sources s ON s.id = a.source_id
            LEFT JOIN stories st ON st.id = a.story_id
            WHERE {clauses}
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """
        rows = db.query(sql, [*params, limit + 1, offset])

    has_more = len(rows) > limit
    rows = rows[:limit]
    from .feed import video_payload

    results = []
    for row in rows:
        item = dict(row)
        item["video"] = video_payload(row)
        snippet = (row["snippet_body"] or row["snippet_summary"] or "").strip()
        item["snippet"] = snippet or (row["summary"] or "")[:240]
        item["topic_label"] = TOPIC_LABELS.get(row["primary_topic"], row["primary_topic"].title())
        results.append(item)

    total = _count(expression, clauses, params) if expression else _count(None, clauses, params)
    return {
        "query": raw_query,
        "expression": expression,
        "filters": {
            "topics": parsed.topics,
            "sources": parsed.sources,
            "after": parsed.after,
            "before": parsed.before,
            "flags": parsed.flags,
        },
        "results": results,
        "count": len(results),
        "total": total,
        "has_more": has_more,
        "offset": offset,
        "limit": limit,
        "sort": sort,
        "took_ms": 0,
    }


def _count(expression: str | None, clauses: str, params: list) -> int:
    if expression:
        sql = f"""
            SELECT COUNT(*) FROM articles_fts
            JOIN articles a ON a.id = articles_fts.rowid
            WHERE articles_fts MATCH ? AND {clauses}
        """
        try:
            return int(db.scalar(sql, [expression, *params], default=0) or 0)
        except sqlite3.OperationalError:
            return 0
    sql = f"SELECT COUNT(*) FROM articles a WHERE {clauses}"
    return int(db.scalar(sql, params, default=0) or 0)


def _fallback_search(parsed: ParsedQuery, clauses: str, params: list, sort: str, limit: int, offset: int):
    """If FTS rejects the expression, fall back to LIKE on the terms."""
    terms = parsed.terms or parsed.phrases
    # `clauses` is a SQL fragment, not an iterable; wrapping it in list()
    # split it into single characters and produced invalid SQL.
    like_clauses = [clauses] if clauses else []
    like_params = list(params)
    for term in terms[:4]:
        like_clauses.append("(a.title LIKE ? OR a.summary LIKE ?)")
        like_params.extend([f"%{term}%", f"%{term}%"])
    order = "COALESCE(a.published_at, a.first_seen_at) DESC" if sort != "relevance" else "a.title"
    sql = f"""
        SELECT a.id, a.title, a.summary, a.source_id, a.url, a.image_url, a.video_url, a.video_id, a.video_kind, a.author,
               a.published_at, a.first_seen_at, a.date_confidence, a.primary_topic,
               a.reading_minutes, a.word_count, a.content_state, a.paywalled, a.is_breaking,
               a.story_id, s.name AS source_name, s.domain, s.lean,
               COALESCE(st.source_count, 1) AS story_source_count,
               COALESCE(st.heat, 0) AS story_heat,
               COALESCE(st.article_count, 1) AS story_article_count,
               0 AS rank, '' AS snippet_body, '' AS snippet_summary
        FROM articles a
        JOIN sources s ON s.id = a.source_id
        LEFT JOIN stories st ON st.id = a.story_id
        WHERE {" AND ".join(like_clauses) if like_clauses else "1=1"}
        ORDER BY {order}
        LIMIT ? OFFSET ?
    """
    return db.query(sql, [*like_params, limit, offset])


def suggestions(raw_query: str, *, limit: int = 8) -> dict:
    query = (raw_query or "").strip()
    if len(query) < 2:
        return {"headlines": [], "topics": [], "sources": [], "recent": recent_searches()}
    cleaned = re.sub(r'["*^():]', " ", query).strip()
    headlines: list[dict] = []
    if cleaned:
        try:
            rows = db.query(
                """
                SELECT a.id, a.title, a.primary_topic, s.name AS source_name
                FROM articles_fts
                JOIN articles a ON a.id = articles_fts.rowid
                JOIN sources s ON s.id = a.source_id
                WHERE articles_fts MATCH ?
                ORDER BY bm25(articles_fts, 6.0, 2.0, 0.6, 1.0)
                LIMIT ?
                """,
                (f'"{cleaned}"*', limit * 3),
            )
            headlines = []
            seen_titles: set[str] = set()
            for row in rows:
                key = re.sub(r"\W+", " ", (row["title"] or "").lower()).strip()
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                headlines.append(
                    {"id": row["id"], "title": row["title"], "topic": row["primary_topic"], "source": row["source_name"]}
                )
        except sqlite3.OperationalError:
            pass
    lowered = query.lower()
    topic_hits = [
        {"slug": slug, "label": label, "icon": icon}
        for slug, label, icon in TOPICS
        if lowered in label.lower()
    ][:4]
    source_hits = [
        {"id": s.id, "name": s.name, "domain": s.domain}
        for s in SOURCES.values()
        if lowered in s.name.lower() or lowered in s.domain.lower()
    ][:4]
    return {
        "headlines": headlines,
        "topics": topic_hits,
        "sources": source_hits,
        "recent": recent_searches(),
    }


def recent_searches(profile_id: str | None = None, limit: int = 6) -> list[str]:
    if not profile_id:
        return []
    rows = db.query(
        "SELECT query, MAX(created_at) AS ts FROM searches WHERE profile_id=? GROUP BY lower(query) ORDER BY ts DESC LIMIT ?",
        (profile_id, limit),
    )
    return [row["query"] for row in rows]


def record_search(profile_id: str, query: str, result_count: int) -> None:
    if not query or len(query) < 2:
        return
    db.execute(
        "INSERT INTO searches(profile_id, query, result_count, created_at) VALUES(?,?,?,?)",
        (profile_id, query[:200], result_count, iso()),
    )


def trending_searches(limit: int = 8) -> list[dict]:
    rows = db.query(
        """
        SELECT lower(query) AS q, COUNT(*) AS n
        FROM searches WHERE created_at >= datetime('now', '-14 days')
        GROUP BY lower(query) ORDER BY n DESC LIMIT ?
        """,
        (limit,),
    )
    return [{"query": row["q"], "count": row["n"]} for row in rows]


def archive_index(topic: str | None = None, limit: int = 24) -> list[dict]:
    """Month-by-month counts, so old stories stay discoverable forever."""
    clause = "WHERE primary_topic = ?" if topic else ""
    params = (topic,) if topic else ()
    rows = db.query(
        f"""
        SELECT strftime('%Y-%m', COALESCE(published_at, first_seen_at)) AS month,
               COUNT(*) AS n, MIN(COALESCE(published_at, first_seen_at)) AS sample
        FROM articles {clause}
        GROUP BY month ORDER BY month DESC LIMIT ?
        """,
        (*params, limit),
    )
    return [dict(row) for row in rows]


def related_articles(article_id: int, limit: int = 6) -> list[dict]:
    article = db.query_one(
        "SELECT title, primary_topic, story_id FROM articles WHERE id=?", (article_id,)
    )
    if article is None:
        return []
    from .stories import tokens_for

    tokens = [t for t in tokens_for(article["title"]) if len(t) > 4][:6]
    rows: list[dict] = []
    seen: set[int] = {article_id}
    if tokens:
        expression = " OR ".join(f'"{t}"' for t in tokens)
        try:
            for row in db.query(
                """
                SELECT a.id, a.title, a.image_url, a.published_at, a.first_seen_at,
                       a.primary_topic, a.reading_minutes, s.name AS source_name,
                       bm25(articles_fts, 6.0, 2.0, 0.5, 1.0) AS rank
                FROM articles_fts
                JOIN articles a ON a.id = articles_fts.rowid
                JOIN sources s ON s.id = a.source_id
                WHERE articles_fts MATCH ? AND a.id <> ?
                ORDER BY rank LIMIT ?
                """,
                (expression, article_id, limit * 2),
            ):
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                rows.append(dict(row))
                if len(rows) >= limit:
                    break
        except sqlite3.OperationalError:
            pass
    if len(rows) < limit and article["story_id"]:
        for row in db.query(
            """
            SELECT a.id, a.title, a.image_url, a.published_at, a.first_seen_at,
                   a.primary_topic, a.reading_minutes, s.name AS source_name
            FROM articles a JOIN sources s ON s.id = a.source_id
            WHERE a.story_id=? AND a.id<>? LIMIT ?
            """,
            (article["story_id"], article_id, limit - len(rows)),
        ):
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            rows.append(dict(row))
    return rows
