"""Feed assembly: candidates from SQLite -> ranked, story-collapsed cards.

This module is the seam between storage and the API. It owns the shapes the
client consumes, including the date labels that keep "published" and
"first seen" honest, and the "why am I seeing this" reasons.
"""
from __future__ import annotations

import json
import random
import re
from datetime import timedelta
from urllib.parse import quote

from . import htmltext, rank, stories, translate
from .config import APP_VERSION
from .db import db
from .sources import TOPICS, TOPIC_ICONS, TOPIC_LABELS, get_source
from .timeutil import absolute, freshness, iso, now, relative, start_of_day

_CANDIDATE_SQL = """
SELECT a.id, a.title, a.summary, a.url, a.canonical_url, a.image_url, a.images, a.author,
       a.video_url, a.video_id, a.video_kind,
       a.published_at, a.published_raw, a.date_confidence, a.first_seen_at, a.last_seen_at,
       a.primary_topic, a.topics, a.reading_minutes, a.word_count, a.content_state,
       a.paywalled, a.is_breaking, a.story_id, a.source_weight,
       s.id AS source_id, s.name AS source_name, s.domain, s.lean,
       s.paywall AS source_paywall, s.country AS source_country, s.region AS source_region,
       COALESCE(st.source_count, 1) AS story_source_count,
       COALESCE(st.heat, 0) AS story_heat,
       COALESCE(st.article_count, 1) AS story_article_count,
       COALESCE(st.breaking, 0) AS story_breaking,
       st.title AS story_title
FROM articles a
JOIN sources s ON s.id = a.source_id
LEFT JOIN stories st ON st.id = a.story_id
WHERE COALESCE(a.published_at, a.first_seen_at) >= ?
"""


def load_candidates(
    *,
    days: int = 3,
    limit: int = 900,
    topic: str | None = None,
    source: str | None = None,
    breaking_only: bool = False,
    mode: str = "for-you",
    readable_only: bool = False,
) -> list:
    params: list = [iso(now() - timedelta(days=days))]
    sql = _CANDIDATE_SQL
    if topic:
        sql += " AND (a.primary_topic = ? OR a.topics LIKE ?)"
        params.extend([topic, f'%"{topic}"%'])
    if source:
        sql += " AND a.source_id = ?"
        params.append(source)
    if breaking_only:
        sql += " AND (a.is_breaking = 1 OR (COALESCE(st.breaking,0) = 1 AND COALESCE(a.published_at, a.first_seen_at) >= ?))"
        params.append(iso(now() - timedelta(hours=24)))
    if mode == "longreads":
        sql += " AND a.word_count >= 700 AND a.content_state = 'extracted'"
    if mode == "video":
        sql += (" AND a.video_kind IS NOT NULL"
                " AND NOT (a.video_kind='file' AND (a.video_url LIKE '%.m3u8%' OR a.video_url LIKE '%.mpd%'))")
    if readable_only:
        sql += " AND (a.content_state = 'extracted' OR a.word_count >= 240)"
    sql += " ORDER BY COALESCE(a.published_at, a.first_seen_at) DESC LIMIT ?"
    params.append(limit)
    return db.query(sql, params)


def collapse_stories(rows: list, *, keep: int = 1) -> list:
    """One card per story, choosing the best article as the card's face."""
    by_story: dict[int, list] = {}
    loose: list = []
    for row in rows:
        story_id = row["story_id"]
        if not story_id:
            loose.append(row)
            continue
        by_story.setdefault(story_id, []).append(row)

    def quality(row) -> float:
        value = 0.0
        if row["image_url"]:
            value += 2.0
        if row["content_state"] == "extracted":
            value += 3.0
        value += min(int(row["word_count"] or 0), 1500) / 1500
        value += (row["story_heat"] or 0) * 0.05
        return value

    output = []
    for group in by_story.values():
        group.sort(key=quality, reverse=True)
        output.append(group[0])
        output.extend(group[keep:])
    output.sort(key=lambda row: row["published_at"] or row["first_seen_at"] or "", reverse=True)
    return output


def date_labels(row) -> dict:
    published = row["published_at"]
    confidence = row["date_confidence"] or "unknown"
    if published and confidence == "day":
        # The feed only gave us a date; a fake midnight timestamp would read as
        # "22 hours ago". Show the date itself instead.
        return {
            "published_at": published,
            "published_relative": absolute(published, with_time=False),
            "published_absolute": absolute(published, with_time=False),
            "date_confidence": confidence,
            "date_label": "Date",
        }
    if published and confidence == "inferred":
        return {
            "published_at": published,
            "published_relative": relative(row["first_seen_at"]),
            "published_absolute": absolute(row["first_seen_at"]),
            "date_confidence": confidence,
            "date_label": "First seen",
        }
    if published:
        return {
            "published_at": published,
            "published_relative": relative(published),
            "published_absolute": absolute(published),
            "date_confidence": confidence,
            "date_label": "Published",
        }
    return {
        "published_at": None,
        "published_relative": relative(row["first_seen_at"]),
        "published_absolute": absolute(row["first_seen_at"]),
        "date_confidence": "unknown",
        "date_label": "First seen",
    }


def card(row, *, model: rank.ProfileModel | None = None, saved_ids: set[int] | None = None,
         read_ids: set[int] | None = None) -> dict:
    labels = date_labels(row)
    source = get_source(row["source_id"])
    topic = row["primary_topic"]
    summary = htmltext.clean_summary(row["summary"] or "", limit=600)
    payload = {
        "id": row["id"],
        "kind": "article",
        "title": row["title"],
        "summary": summary,
        "preview": _preview_of(summary),
        "url": row["url"],
        "image": proxied_image(row["image_url"]),
        "video": video_payload(row),
        "author": htmltext.clean_author(row["author"]),
        "source": {
            "id": row["source_id"],
            "name": row["source_name"],
            "domain": row["domain"],
            "initials": source.initials if source else (row["source_name"] or "?")[:2],
            "lean": row["lean"],
            "paywall": bool(row["source_paywall"]),
            "country": row["source_country"],
        },
        "topic": topic,
        "topic_label": TOPIC_LABELS.get(topic, topic.title()),
        "topics": _topics_of(row),
        "reading_minutes": int(row["reading_minutes"] or 1),
        "word_count": int(row["word_count"] or 0),
        "content_state": row["content_state"],
        "paywalled": bool(row["paywalled"]),
        "breaking": bool(row["is_breaking"] or row["story_breaking"]),
        "freshness": freshness(row["published_at"] or row["first_seen_at"]),
        "story": {
            "id": row["story_id"],
            "source_count": int(row["story_source_count"] or 1),
            "article_count": int(row["story_article_count"] or 1),
            "heat": float(row["story_heat"] or 0),
            "title": row["story_title"],
        },
        "saved": bool(saved_ids and row["id"] in saved_ids),
        "read": bool(read_ids and row["id"] in read_ids),
        "date_confidence": labels["date_confidence"],
        "has_full_text": row["content_state"] == "extracted",
    }
    try:
        stored_images = json.loads(row["images"] or "[]") if "images" in row.keys() else []
    except (ValueError, TypeError):
        stored_images = []
    if row["image_url"] and row["image_url"] not in stored_images:
        stored_images.insert(0, row["image_url"])
    payload["image_count"] = len([url for url in stored_images if url]) or (1 if row["image_url"] else 0)
    payload.update(labels)
    translate.decorate(payload)
    if model is not None:
        payload["reasons"] = rank.why_this(row, model)
    return payload


def _topics_of(row) -> list[str]:
    try:
        values = json.loads(row["topics"] or "[]")
        return [v for v in values if v][:4]
    except (ValueError, TypeError):
        return [row["primary_topic"]]


def _preview_of(summary: str, limit: int = 260) -> str:
    if not summary:
        return ""
    if len(summary) <= limit:
        return summary
    cut = summary[:limit]
    # Prefer a real sentence boundary over a mid-clause cut.
    boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if boundary >= int(limit * 0.55):
        return cut[: boundary + 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


_CHILD_BLOCK = re.compile(
    r"\b(kill(?:ed|ing|s)?|shoot(?:ing|er|ers)?|shot|stab(?:bed|bing)?|war|bomb(?:ing|ed|s)?|"
    r"attack(?:ed|ing|s)?|assault|rape|suicide|dead|death|murder(?:ed|er|ers)?|hostage|"
    r"missile|airstrike|massacre|abuse|gun(?:man|men|s)?|terror(?:ist|ists|ism)?|corpse|"
    r"behead|execution|torture|genocide|fatal|casualt(?:y|ies)|wounded|injured|prisoners?|"
    r"dies|died|dying|fallec\w*|muere|muerto|muerte|threat(?:en|ens|ened)?|strikes?|military|"
    r"weapons?|drone|invasion|troops|combat|conflict|clashes?|violence|violent|punch(?:ed)?|"
    r"explosion|riot|kicked)\b",
    re.I,
)


def child_safe(row, age: int = 13) -> bool:
    if int(age or 13) > 9:
        return True
    text = f"{row['title'] or ''} {row['summary'] or ''}"
    return not _CHILD_BLOCK.search(text)


def video_payload(row) -> dict | None:
    try:
        kind = row["video_kind"]
        video_id = row["video_id"]
        url = row["video_url"]
    except (KeyError, IndexError):
        return None
    if not kind:
        return None
    if kind == "youtube" and video_id:
        return {
            "kind": "youtube",
            "id": video_id,
            "url": url or f"https://www.youtube.com/watch?v={video_id}",
            "embed": f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0",
            "thumbnail": proxied_image(f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"),
            "provider": "YouTube",
        }
    if kind == "vimeo" and video_id:
        return {
            "kind": "vimeo",
            "id": video_id,
            "url": url or f"https://vimeo.com/{video_id}",
            "embed": f"https://player.vimeo.com/video/{video_id}?dnt=1",
            "thumbnail": None,
            "provider": "Vimeo",
        }
    if kind == "file" and url:
        url = str(url).replace("\\/", "/")
        if url.lower().split("?")[0].endswith((".m3u8", ".mpd")):
            return None
        return {"kind": "file", "id": None, "url": url, "embed": None, "thumbnail": None, "provider": "Video"}
    return None


def proxied_image(url: str | None) -> str | None:
    if not url:
        return None
    return "/api/img?u=" + quote(url, safe="")


def _seeded_head(ranked: list, seed: str | None, pool_size: int) -> list:
    """Shuffle only the leading quality pool, not the whole archive.

    A new app load gets a new seed, so the top of the front page changes while
    still drawing from the highest-heat stories. The rest of the ranking stays
    stable, which keeps "Load more" coherent.
    """
    if not seed or pool_size < 2 or len(ranked) < 2:
        return ranked
    pool = list(ranked[: min(pool_size, len(ranked))])
    random.Random(str(seed)).shuffle(pool)
    return pool + list(ranked[len(pool):])


def feed_page(
    profile: dict,
    *,
    mode: str = "for-you",
    topic: str | None = None,
    source: str | None = None,
    offset: int = 0,
    limit: int = 24,
    days: int = 3,
    seed: str | None = None,
) -> dict:
    profile_id = profile["id"]
    model = rank.build_model(profile_id, profile["survey"], profile["prefs"])
    saved_ids = {int(r["article_id"]) for r in db.query("SELECT article_id FROM saves WHERE profile_id=?", (profile_id,))}
    read_ids = {
        int(r["article_id"]) for r in db.query(
            "SELECT DISTINCT article_id FROM events WHERE profile_id=? AND kind='read' AND article_id IS NOT NULL",
            (profile_id,),
        )
    }

    if mode == "breaking":
        rows = load_candidates(days=2, limit=400, breaking_only=True)
        ranked = [(row, 0.0, ["Breaking"]) for row in rows]
    elif mode == "latest":
        rows = load_candidates(days=days, limit=400, topic=topic, source=source)
        ranked = [(row, 0.0, []) for row in rows]
    elif mode == "top":
        rows = load_candidates(days=days, limit=600, topic=topic, source=source)
        ranked = [(row, row["story_heat"] or 0.0, rank.why_this(row, model)) for row in rows]
        ranked.sort(key=lambda item: item[1], reverse=True)
    elif mode == "longreads":
        rows = load_candidates(days=14, limit=400, topic=topic, source=source, mode="longreads")
        ranked = rank.rank(rows, model, limit=len(rows) or 1)
    elif mode == "readable":
        rows = load_candidates(days=days, limit=600, topic=topic, source=source, readable_only=True)
        ranked = rank.rank(rows, model, limit=len(rows) or 1)
    elif mode == "video":
        rows = load_candidates(days=days, limit=600, topic=topic, source=source, mode="video")
        ranked = rank.rank(rows, model, limit=len(rows) or 1)
    else:  # for-you and topic/source views use personalisation
        rows = load_candidates(days=days, limit=900, topic=topic, source=source)
        ranked = rank.rank(rows, model, limit=len(rows) or 1)

    age = int(profile["survey"].get("age") or 13)
    if age <= 9:
        ranked = [entry for entry in ranked if child_safe(entry[0], age)]

    if mode not in ("breaking", "latest"):
        seen_story: set[int] = set()
        deduped = []
        for row, value, reasons in ranked:
            story_id = row["story_id"]
            if story_id and story_id in seen_story:
                continue
            if story_id:
                seen_story.add(story_id)
            deduped.append((row, value, reasons))
        ranked = deduped

    if seed:
        if mode == "top":
            ranked = _seeded_head(ranked, seed, 10 if topic else 16)
        elif mode == "for-you":
            ranked = _seeded_head(ranked, seed, 8)

    total = len(ranked)
    window = ranked[offset : offset + limit]
    items = [
        {**card(row, model=model, saved_ids=saved_ids, read_ids=read_ids), "score": round(value, 2), "reasons": reasons}
        for row, value, reasons in window
    ]
    translate.localize_items(items, sync_limit=6)
    return {
        "items": items,
        "mode": mode,
        "topic": topic,
        "source": source,
        "offset": offset,
        "limit": limit,
        "total": total,
        "has_more": offset + limit < total,
        "next_offset": offset + limit if offset + limit < total else None,
        "generated_at": iso(),
        "archive_days": days,
        "reading_mix": [
            {"topic": topic, "label": TOPIC_LABELS.get(topic, topic.title()), "percent": round(percent * 100)}
            for topic, percent in sorted(model.topic_mix.items(), key=lambda item: item[1], reverse=True)[:6]
            if percent >= 0.02
        ] if mode == "for-you" else [],
    }


def video_feed(
    profile: dict,
    *,
    topic: str | None = None,
    offset: int = 0,
    limit: int = 24,
    days: int = 60,
) -> dict:
    """A video-first stream: publisher clips and YouTube newsroom uploads."""
    since = iso(now() - timedelta(days=days))
    where = [
        "a.video_kind IS NOT NULL",
        "a.video_url IS NOT NULL",
        "NOT (a.video_kind='file' AND (a.video_url LIKE '%.m3u8%' OR a.video_url LIKE '%.mpd%'))",
        "COALESCE(a.published_at, a.first_seen_at) >= ?",
    ]
    params: list = [since]
    if topic == "news":
        where.append("a.primary_topic IN ('world', 'us', 'politics', 'business')")
    elif topic == "science":
        where.append("a.primary_topic IN ('science', 'space', 'climate', 'health')")
    elif topic:
        where.append("(a.primary_topic = ? OR a.topics LIKE ?)")
        params.extend([topic, f'%"{topic}"%'])
    clause = " AND ".join(where)
    total_row = db.query_one(f"SELECT COUNT(*) AS n FROM articles a WHERE {clause}", tuple(params))
    total = int(total_row["n"] if total_row else 0)
    rows = db.query(
        f"""
        SELECT a.id, a.title, a.summary, a.url, a.canonical_url, a.image_url, a.images, a.author,
               a.video_url, a.video_id, a.video_kind,
               a.published_at, a.published_raw, a.date_confidence, a.first_seen_at, a.last_seen_at,
               a.primary_topic, a.topics, a.reading_minutes, a.word_count, a.content_state,
               a.paywalled, a.is_breaking, a.story_id, a.source_weight,
               s.id AS source_id, s.name AS source_name, s.domain, s.lean,
               s.paywall AS source_paywall, s.country AS source_country, s.region AS source_region,
               COALESCE(st.source_count, 1) AS story_source_count,
               COALESCE(st.heat, 0) AS story_heat,
               COALESCE(st.article_count, 1) AS story_article_count,
               COALESCE(st.breaking, 0) AS story_breaking,
               st.title AS story_title
        FROM articles a
        JOIN sources s ON s.id = a.source_id
        LEFT JOIN stories st ON st.id = a.story_id
        WHERE {clause}
        ORDER BY COALESCE(a.published_at, a.first_seen_at) DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [limit, offset]),
    )
    age = int((profile.get("survey") or {}).get("age") or 13)
    if age <= 8:
        allowed = {"science", "space", "culture", "sports", "motorsport", "tech", "health", "education"}
        rows = [row for row in rows if row["primary_topic"] in allowed and child_safe(row, age)]
    elif age <= 9:
        rows = [row for row in rows if child_safe(row, age)]
    items = []
    seen: set = set()
    for row in rows:
        key = row["story_id"] or (row["title"] or "").strip().lower()
        if key in seen:
            continue
        payload = card(row)
        if not payload.get("video"):
            continue
        seen.add(key)
        items.append(payload)
    translate.localize_items(items, sync_limit=6)
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
        "next_offset": offset + limit if offset + limit < total else None,
        "generated_at": iso(),
    }


def keyword_page(
    profile: dict,
    query: str,
    *,
    offset: int = 0,
    limit: int = 24,
    sort: str = "relevance",
) -> dict:
    """A feed-style archive page for one keyword.

    Search ranks/filters; the result ids are hydrated through the normal card
    query so keyword pages get the same images, labels and video metadata as
    every other feed.
    """
    from collections import Counter
    from . import search as search_module

    result = search_module.search(query, sort=sort, limit=limit, offset=offset)
    ids = [int(row["id"]) for row in result.get("results", [])]
    if not ids:
        return {
            "query": query,
            "items": [],
            "total": 0,
            "offset": offset,
            "limit": limit,
            "has_more": False,
            "next_offset": None,
            "sort": sort,
            "generated_at": iso(),
            "facets": {"topics": [], "sources": []},
        }
    placeholders = ",".join("?" for _ in ids)
    base = _CANDIDATE_SQL[: _CANDIDATE_SQL.index("WHERE")]
    rows = db.query(
        base + f"WHERE a.id IN ({placeholders})",
        tuple(ids),
    )
    by_id = {int(row["id"]): row for row in rows}
    model = rank.build_model(profile["id"], profile["survey"], profile["prefs"])
    saved_ids = {int(r["article_id"]) for r in db.query("SELECT article_id FROM saves WHERE profile_id=?", (profile["id"],))}
    read_ids = {
        int(r["article_id"]) for r in db.query(
            "SELECT DISTINCT article_id FROM events WHERE profile_id=? AND kind='read' AND article_id IS NOT NULL",
            (profile["id"],),
        )
    }
    items = [
        card(by_id[article_id], model=model, saved_ids=saved_ids, read_ids=read_ids)
        for article_id in ids
        if article_id in by_id
    ]
    translate.localize_items(items, sync_limit=8)
    topic_counts = Counter(item["topic"] for item in items)
    source_counts = Counter((item["source"]["id"], item["source"]["name"]) for item in items)
    facets = {
        "topics": [
            {"id": topic, "label": TOPIC_LABELS.get(topic, topic), "count": count}
            for topic, count in topic_counts.most_common(5)
        ],
        "sources": [
            {"id": source_id, "name": name, "count": count}
            for (source_id, name), count in source_counts.most_common(5)
        ],
    }
    total = int(result.get("total", 0) or 0)
    return {
        "query": query,
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
        "next_offset": offset + limit if offset + limit < total else None,
        "sort": sort,
        "generated_at": iso(),
        "facets": facets,
    }


def article_detail(article_id: int, profile: dict) -> dict | None:
    row = db.query_one(
        """
        SELECT a.*, s.name AS source_name, s.domain, s.lean, s.paywall AS source_paywall,
               s.country AS source_country, s.about AS source_about,
               COALESCE(st.source_count, 1) AS story_source_count,
               COALESCE(st.heat, 0) AS story_heat,
               COALESCE(st.article_count, 1) AS story_article_count,
               COALESCE(st.breaking, 0) AS story_breaking,
               st.title AS story_title, st.first_seen_at AS story_first_seen
        FROM articles a
        JOIN sources s ON s.id = a.source_id
        LEFT JOIN stories st ON st.id = a.story_id
        WHERE a.id = ?
        """,
        (article_id,),
    )
    if row is None:
        return None
    profile_id = profile["id"]
    model = rank.build_model(profile_id, profile["survey"], profile["prefs"])
    saved_row = db.query_one(
        "SELECT collection, created_at FROM saves WHERE profile_id=? AND article_id=?",
        (profile_id, article_id),
    )
    payload = card(row, model=model, saved_ids={article_id} if saved_row else set())
    blocks = []
    if row["content_blocks"]:
        try:
            blocks = json.loads(row["content_blocks"])
        except (ValueError, TypeError):
            blocks = []
    # Only show a body when we actually have one. A feed summary repeated under
    # the dek and the overview is noise, not content.
    if not blocks and row["content_text"] and int(row["word_count"] or 0) >= 250:
        blocks = [{"type": "p", "text": para} for para in row["content_text"].split("\n\n") if para.strip()]

    blocks = [
        block for block in blocks
        if not (len(block.get("text", "")) < 160 and "preferred source" in block.get("text", "").lower())
    ]
    blocks = htmltext.clean_blocks(blocks)
    try:
        stored_images = json.loads(row["images"] or "[]") if "images" in row.keys() else []
    except (ValueError, TypeError):
        stored_images = []
    if row["image_url"] and row["image_url"] not in stored_images:
        stored_images.insert(0, row["image_url"])
    gallery = [proxied_image(url) for url in stored_images[:24] if url]
    payload.update(
        {
            "images": gallery,
            "image_count": len(gallery),
            "blocks": blocks[:120],
            "text_length": len(row["content_text"] or ""),
            "source_about": row["source_about"],
            "story_first_seen": row["story_first_seen"],
            "canonical_url": row["canonical_url"] or row["url"],
            "content_state": row["content_state"],
            "saved_collection": saved_row["collection"] if saved_row else None,
            "notes": [
                dict(note) for note in db.query(
                    "SELECT id, quote, body, start_offset, end_offset, created_at FROM notes "
                    "WHERE profile_id=? AND article_id=? ORDER BY created_at DESC",
                    (profile_id, article_id),
                )
            ],
            "citation_styles": [
                {"id": "mla", "label": "MLA 9"},
                {"id": "apa", "label": "APA 7"},
                {"id": "chicago", "label": "Chicago"},
                {"id": "harvard", "label": "Harvard"},
                {"id": "bibtex", "label": "BibTeX"},
            ],
            "coverage": story_coverage(row["story_id"], article_id),
            "related": related_cards(row["id"], limit=6),
        }
    )
    payload["read_url"] = row["url"]
    payload["archive"] = True
    translate.localize_payload(payload, sync=True)
    return payload


def story_coverage(story_id: int | None, exclude_id: int | None = None) -> dict:
    if not story_id:
        return {"articles": [], "sources": 0, "leans": {}}
    rows = db.query(
        """
        SELECT a.id, a.title, a.url, a.published_at, a.first_seen_at, a.reading_minutes,
               s.id AS source_id, s.name AS source_name, s.lean, s.country, s.paywall
        FROM articles a JOIN sources s ON s.id = a.source_id
        WHERE a.story_id=? AND a.id <> ?
        ORDER BY COALESCE(a.published_at, a.first_seen_at) DESC
        LIMIT 24
        """,
        (story_id, exclude_id or 0),
    )
    leans = {"left": 0, "center-left": 0, "center": 0, "center-right": 0, "right": 0, "state": 0}
    seen_sources = set()
    articles = []
    for row in rows:
        leans[row["lean"]] = leans.get(row["lean"], 0) + 1
        seen_sources.add(row["source_id"])
        articles.append(
            {
                "id": row["id"],
                "title": row["title"],
                "source": row["source_name"],
                "source_id": row["source_id"],
                "lean": row["lean"],
                "country": row["country"],
                "paywall": bool(row["paywall"]),
                "published_relative": relative(row["published_at"] or row["first_seen_at"]),
                "reading_minutes": int(row["reading_minutes"] or 1),
                "url": row["url"],
            }
        )
    return {
        "articles": articles,
        "sources": len(seen_sources),
        "leans": {k: v for k, v in leans.items() if v},
        "note": "Editorial perspective is an approximate classification, not a verdict on accuracy.",
    }


def related_cards(article_id: int, limit: int = 6) -> list[dict]:
    from .search import related_articles

    rows = related_articles(article_id, limit=limit)
    output = []
    for row in rows:
        output.append(
            {
                "id": row["id"],
                "title": row["title"],
                "image": proxied_image(row.get("image_url")),
                "source": row.get("source_name"),
                "published_relative": relative(row.get("published_at") or row.get("first_seen_at")),
                "reading_minutes": int(row.get("reading_minutes") or 1),
                "topic": row.get("primary_topic"),
            }
        )
    translate.localize_items(output, sync_limit=2)
    return output


def story_detail(story_id: int, profile: dict) -> dict | None:
    story = db.query_one("SELECT * FROM stories WHERE id=?", (story_id,))
    if story is None:
        return None
    rows = db.query(
        """
        SELECT a.id, a.title, a.summary, a.url, a.image_url, a.author, a.published_at,
               a.first_seen_at, a.date_confidence, a.primary_topic, a.topics, a.reading_minutes,
               a.word_count, a.content_state, a.paywalled, a.is_breaking, a.story_id,
               s.id AS source_id, s.name AS source_name, s.domain, s.lean,
               s.paywall AS source_paywall, s.country AS source_country,
               ? AS story_source_count, ? AS story_heat, ? AS story_article_count, ? AS story_breaking,
               ? AS story_title
        FROM articles a JOIN sources s ON s.id = a.source_id
        WHERE a.story_id=? ORDER BY COALESCE(a.published_at, a.first_seen_at) ASC
        """,
        (
            story["source_count"], story["heat"], story["article_count"], story["breaking"],
            story["title"], story_id,
        ),
    )
    if not rows:
        return None
    profile_id = profile["id"]
    saved_ids = {int(r["article_id"]) for r in db.query("SELECT article_id FROM saves WHERE profile_id=?", (profile_id,))}
    cards = [card(row, saved_ids=saved_ids) for row in rows]
    translate.localize_items(cards, sync_limit=4)
    return {
        "id": story_id,
        "title": story["title"],
        "topic": story["primary_topic"],
        "topic_label": TOPIC_LABELS.get(story["primary_topic"], story["primary_topic"].title()),
        "source_count": story["source_count"],
        "article_count": story["article_count"],
        "breaking": bool(story["breaking"]),
        "heat": story["heat"],
        "first_seen_at": story["first_seen_at"],
        "last_seen_at": story["last_seen_at"],
        "relative": relative(story["last_seen_at"]),
        "articles": cards,
        "leans": story_coverage(story_id, None)["leans"],
    }


def trending_stories(limit: int = 8, *, days: int = 2, profile: dict | None = None) -> list[dict]:
    since = iso(now() - timedelta(days=days))
    rows = db.query(
        """
        SELECT st.id, st.title, st.primary_topic, st.source_count, st.article_count,
               st.heat, st.breaking, st.last_seen_at, st.first_seen_at,
               a.id AS lead_id, a.title AS lead_title, a.summary, a.image_url,
               a.published_at, a.first_seen_at AS lead_first_seen, a.reading_minutes,
               s.id AS source_id, s.name AS source_name, s.domain, s.lean
        FROM stories st
        JOIN articles a ON a.id = st.lead_article_id
        JOIN sources s ON s.id = a.source_id
        WHERE st.last_seen_at >= ? AND a.paywalled = 0
        ORDER BY st.heat DESC, st.source_count DESC, st.last_seen_at DESC
        LIMIT ?
        """,
        (since, limit * 3),
    )
    output = []
    seen_topics: dict[str, int] = {}
    for row in rows:
        topic = row["primary_topic"]
        if seen_topics.get(topic, 0) >= 3:
            continue
        seen_topics[topic] = seen_topics.get(topic, 0) + 1
        output.append(
            {
                "id": row["id"],
                "title": row["title"],
                "topic": topic,
                "topic_label": TOPIC_LABELS.get(topic, topic.title()),
                "source_count": row["source_count"],
                "article_count": row["article_count"],
                "heat": row["heat"],
                "breaking": bool(row["breaking"]),
                "relative": relative(row["last_seen_at"]),
                "lead": {
                    "id": row["lead_id"],
                    "title": row["lead_title"],
                    "summary": _preview_of(row["summary"] or "", 180),
                    "image": proxied_image(row["image_url"]),
                    "source": row["source_name"],
                    "published_relative": relative(row["published_at"] or row["lead_first_seen"]),
                    "reading_minutes": int(row["reading_minutes"] or 1),
                    "domain": row["domain"],
                },
            }
        )
        if len(output) >= limit:
            break
    return output


def topic_overview(days: int = 7) -> list[dict]:
    since = iso(now() - timedelta(days=days))
    counts = db.query(
        """
        SELECT primary_topic AS topic, COUNT(*) AS n, MAX(COALESCE(published_at, first_seen_at)) AS latest
        FROM articles WHERE COALESCE(published_at, first_seen_at) >= ?
        GROUP BY primary_topic
        """,
        (since,),
    )
    by_topic = {row["topic"]: row for row in counts}
    output = []
    for slug, label, icon in TOPICS:
        row = by_topic.get(slug)
        output.append(
            {
                "slug": slug,
                "label": label,
                "icon": icon,
                "count": int(row["n"]) if row else 0,
                "latest": row["latest"] if row else None,
                "relative": relative(row["latest"]) if row and row["latest"] else "",
            }
        )
    output.sort(key=lambda item: item["count"], reverse=True)
    return output


def source_spotlight(limit: int = 10) -> list[dict]:
    rows = db.query(
        """
        SELECT s.id, s.name, s.domain, s.country, s.region, s.topics, s.about, s.audience,
               COUNT(a.id) AS recent, MAX(a.first_seen_at) AS latest
        FROM sources s JOIN articles a ON a.source_id = s.id
        WHERE a.first_seen_at >= ?
        GROUP BY s.id ORDER BY recent DESC LIMIT ?
        """,
        (iso(now() - timedelta(days=2)), limit * 3),
    )
    out = []
    for row in rows:
        source = get_source(row["id"])
        if source is None:
            continue
        out.append(
            {
                "id": row["id"],
                "name": row["name"],
                "domain": row["domain"],
                "country": row["country"],
                "region": row["region"],
                "about": row["about"],
                "topics": json.loads(row["topics"] or "[]"),
                "initials": source.initials,
                "recent": row["recent"],
                "teen_friendly": source.teen_friendly,
                "paywall": source.paywall,
            }
        )
        if len(out) >= limit:
            break
    return out


def discover(profile: dict) -> dict:
    model = rank.build_model(profile["id"], profile["survey"], profile["prefs"])
    age = int(profile["survey"].get("age") or 13)
    safe_topics = {"science", "culture", "sports", "motorsport", "tech", "health"}

    def keep(row):
        if not child_safe(row, age):
            return False
        return age > 8 or row["primary_topic"] in safe_topics

    topics = topic_overview(days=7)
    trending = trending_stories(limit=6)
    longreads = [
        card(row, model=model)
        for row in load_candidates(days=10, limit=12, mode="longreads")
        if keep(row)
    ]
    picks = db.query(
        """
        SELECT a.id, a.title, a.summary, a.url, a.image_url, a.author, a.published_at,
               a.first_seen_at, a.date_confidence, a.primary_topic, a.topics, a.reading_minutes,
               a.word_count, a.content_state, a.paywalled, a.is_breaking, a.story_id,
               s.id AS source_id, s.name AS source_name, s.domain, s.lean,
               s.paywall AS source_paywall, s.country AS source_country,
               COALESCE(st.source_count, 1) AS story_source_count, COALESCE(st.heat, 0) AS story_heat,
               COALESCE(st.article_count, 1) AS story_article_count, COALESCE(st.breaking, 0) AS story_breaking,
               st.title AS story_title
        FROM articles a JOIN sources s ON s.id = a.source_id
        LEFT JOIN stories st ON st.id = a.story_id
        WHERE a.content_state='extracted' AND a.paywalled=0 AND a.image_url IS NOT NULL
          AND COALESCE(a.published_at, a.first_seen_at) >= ?
        ORDER BY a.reading_minutes DESC, COALESCE(a.published_at, a.first_seen_at) DESC
        LIMIT 40
        """,
        (iso(now() - timedelta(days=4)),),
    )
    seen_topic: dict[str, int] = {}
    editors = []
    for row in picks:
        if not keep(row):
            continue
        topic = row["primary_topic"]
        if seen_topic.get(topic, 0) >= 2:
            continue
        seen_topic[topic] = seen_topic.get(topic, 0) + 1
        editors.append(card(row, model=model))
        if len(editors) >= 6:
            break
    translate.localize_items(longreads, sync_limit=3)
    translate.localize_items(editors, sync_limit=3)
    return {
        "topics": topics,
        "trending": trending,
        "longreads": longreads,
        "editors_picks": editors,
        "sources": source_spotlight(limit=10),
        "archive": archive_summary(),
        "generated_at": iso(),
    }


def archive_summary() -> dict:
    row = db.query_one(
        """
        SELECT COUNT(*) AS total, MIN(COALESCE(published_at, first_seen_at)) AS earliest,
               MAX(COALESCE(published_at, first_seen_at)) AS latest,
               COUNT(DISTINCT source_id) AS sources
        FROM articles
        """
    )
    months = db.query(
        """
        SELECT strftime('%Y-%m', COALESCE(published_at, first_seen_at)) AS month, COUNT(*) AS n
        FROM articles GROUP BY month ORDER BY month DESC LIMIT 18
        """
    )
    return {
        "total": int(row["total"] or 0) if row else 0,
        "earliest": row["earliest"] if row else None,
        "latest": row["latest"] if row else None,
        "sources": int(row["sources"] or 0) if row else 0,
        "months": [dict(m) for m in months],
        "note": "Every article ever ingested stays searchable. Nothing is deleted.",
    }
