"""Profiles, onboarding survey, XP/streaks, badges and data export.

The profile is the personalisation contract: what the survey asks, what the
ranker reads, what the reader can change later, and what they can download or
delete.  All of it lives in SQLite next to the archive.
"""
from __future__ import annotations

import json
import secrets
from datetime import timedelta

from . import rank, stories
from .db import db
from .logging_setup import get_logger
from .sources import SOURCES, TOPIC_SLUGS
from .timeutil import day_key, iso, minutes_since, now, parse_iso, start_of_day

log = get_logger("profiles")

DEFAULT_PREFS: dict = {
    "theme": "system",
    "text_size": 1,
    "font": "sans",
    "line_spacing": 1.55,
    "reduce_motion": False,
    "high_contrast": False,
    "show_images": True,
    "ai_overview": True,
    "hide_paywalled": False,
    "reading_length": "medium",
    "daily_goal": 5,
    "notify_breaking": True,
    "notify_topics": [],
    "sports_leagues": ["nba", "nfl", "mlb", "eng.1"],
    "teams": [],
    "language": "en",
    "autoplay_sports": False,
    "show_reading_streak": True,
    "content_filters": {"graphic": False},
}

DEFAULT_SURVEY: dict = {
    "topics": {},
    "sources": [],
    "keywords": [],
    "region": "",
    "grade": "",
    "goals": [],
    "avoid": [],
    "reading_length": "medium",
    "daily_goal": 5,
    "experience": "some",
    "completed_at": None,
}

GRADES = ("middle", "9", "10", "11", "12", "uni", "other")
GOALS = ("exam prep", "current events class", "writing & debate", "college apps",
         "general knowledge", "science & tech", "sports", "culture")
READING_LENGTHS = ("short", "medium", "long")
THEMES = ("system", "light", "dark", "sepia")
FONTS = ("sans", "serif", "dyslexic")

_XP = {
    "open": 2,
    "read": 6,
    "save": 4,
    "like": 3,
    "share": 5,
    "quiz_correct": 8,
    "quiz_attempt": 2,
    "brief_complete": 20,
    "note": 3,
    "streak_day": 10,
    "search": 1,
}

BADGES = (
    {"id": "first_read", "label": "First story", "icon": "📰", "hint": "Read your first article"},
    {"id": "streak_3", "label": "3-day streak", "icon": "🔥", "hint": "Read three days in a row"},
    {"id": "streak_7", "label": "Week warrior", "icon": "🗓️", "hint": "Seven days in a row"},
    {"id": "streak_30", "label": "Month of news", "icon": "🏅", "hint": "Thirty days in a row"},
    {"id": "reader_25", "label": "25 stories", "icon": "📚", "hint": "Read 25 articles"},
    {"id": "reader_100", "label": "Century club", "icon": "💯", "hint": "Read 100 articles"},
    {"id": "explorer", "label": "Explorer", "icon": "🧭", "hint": "Read across five topics"},
    {"id": "source_spelunker", "label": "Source spelunker", "icon": "🏛️", "hint": "Read from ten different outlets"},
    {"id": "quiz_5", "label": "Quiz whiz", "icon": "🧠", "hint": "Answer five quiz questions correctly"},
    {"id": "saver_10", "label": "Archivist", "icon": "🔖", "hint": "Save ten stories"},
    {"id": "note_taker", "label": "Note taker", "icon": "✍️", "hint": "Highlight and note a story"},
    {"id": "brief_5", "label": "Briefed", "icon": "⚡", "hint": "Finish five daily briefs"},
)


def new_id() -> str:
    return secrets.token_hex(12)


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def create(name: str = "Student") -> dict:
    profile_id = new_id()
    timestamp = iso()
    safe_name = (name or "Student").strip()[:40] or "Student"
    db.execute(
        """INSERT INTO profiles(id, name, created_at, updated_at, onboarded, survey, prefs, xp, level,
                               streak_count, streak_best, streak_last, daily_goal)
           VALUES(?,?,?,?,0,?,?,0,1,0,0,NULL,?)""",
        (profile_id, safe_name, timestamp, timestamp, json.dumps(DEFAULT_SURVEY), json.dumps(DEFAULT_PREFS), 5),
    )
    return get(profile_id) or {}


def get(profile_id: str) -> dict | None:
    row = db.query_one("SELECT * FROM profiles WHERE id=?", (profile_id,))
    if row is None:
        return None
    return _serialise(row)


def ensure(profile_id: str | None) -> dict:
    if profile_id:
        profile = get(profile_id)
        if profile:
            return profile
    return create()


def _serialise(row) -> dict:
    survey = _merge(DEFAULT_SURVEY, _loads(row["survey"]))
    prefs = _merge(DEFAULT_PREFS, _loads(row["prefs"]))
    xp = int(row["xp"] or 0)
    level, into, needed, title = rank.level_for_xp(xp)
    profile = {
        "id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "onboarded": bool(row["onboarded"]),
        "survey": survey,
        "prefs": prefs,
        "xp": xp,
        "level": level,
        "level_title": title,
        "level_progress": {"into": into, "needed": needed, "percent": round(into / needed * 100) if needed else 0},
        "streak": {
            "count": int(row["streak_count"] or 0),
            "best": int(row["streak_best"] or 0),
            "last": row["streak_last"],
            "active_today": row["streak_last"] == day_key(now()),
        },
        "daily_goal": int(row["daily_goal"] or 5),
    }
    profile["today"] = _today_stats(row["id"], profile)
    profile["badges"] = badges(profile)
    return profile


def _loads(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def sanitise_survey(survey: dict) -> dict:
    clean = _merge(DEFAULT_SURVEY, {})
    topics: dict[str, int] = {}
    for topic, value in (survey.get("topics") or {}).items():
        if topic in TOPIC_SLUGS:
            try:
                topics[topic] = max(0, min(3, int(value)))
            except (TypeError, ValueError):
                continue
    clean["topics"] = topics
    clean["sources"] = [s for s in (survey.get("sources") or []) if s in SOURCES][:60]
    clean["keywords"] = [str(k).strip()[:40] for k in (survey.get("keywords") or []) if str(k).strip()][:12]
    clean["region"] = str(survey.get("region") or "")[:3].upper()
    clean["grade"] = survey.get("grade") if survey.get("grade") in GRADES else ""
    clean["goals"] = [g for g in (survey.get("goals") or []) if g in GOALS][:6]
    clean["avoid"] = [t for t in (survey.get("avoid") or []) if t in TOPIC_SLUGS]
    if survey.get("reading_length") in READING_LENGTHS:
        clean["reading_length"] = survey["reading_length"]
    try:
        clean["daily_goal"] = max(1, min(30, int(survey.get("daily_goal", 5))))
    except (TypeError, ValueError):
        clean["daily_goal"] = 5
    clean["experience"] = str(survey.get("experience") or "some")[:20]
    if survey.get("completed_at"):
        clean["completed_at"] = str(survey["completed_at"])[:40]
    return clean


def sanitise_prefs(prefs: dict) -> dict:
    clean = _merge(DEFAULT_PREFS, {})
    if prefs.get("theme") in THEMES:
        clean["theme"] = prefs["theme"]
    if prefs.get("font") in FONTS:
        clean["font"] = prefs["font"]
    if prefs.get("reading_length") in READING_LENGTHS:
        clean["reading_length"] = prefs["reading_length"]
    for key in ("text_size", "daily_goal"):
        if key in prefs:
            try:
                clean[key] = int(prefs[key])
            except (TypeError, ValueError):
                pass
    clean["text_size"] = max(0, min(4, int(clean.get("text_size", 1))))
    clean["daily_goal"] = max(1, min(30, int(clean.get("daily_goal", 5))))
    for key in ("reduce_motion", "high_contrast", "show_images", "ai_overview", "hide_paywalled",
                "notify_breaking", "autoplay_sports", "show_reading_streak"):
        if key in prefs:
            clean[key] = bool(prefs[key])
    clean["notify_topics"] = [t for t in (prefs.get("notify_topics") or []) if t in TOPIC_SLUGS][:8]
    clean["sports_leagues"] = [str(s)[:20] for s in (prefs.get("sports_leagues") or [])][:12]
    clean["teams"] = [str(t)[:40] for t in (prefs.get("teams") or [])][:12]
    if isinstance(prefs.get("content_filters"), dict):
        clean["content_filters"] = {"graphic": bool(prefs["content_filters"].get("graphic"))}
    return clean


def update(profile_id: str, *, name: str | None = None, survey: dict | None = None,
           prefs: dict | None = None, onboarded: bool | None = None) -> dict | None:
    profile = get(profile_id)
    if profile is None:
        return None
    new_survey = sanitise_survey({**profile["survey"], **(survey or {})}) if survey else profile["survey"]
    new_prefs = sanitise_prefs({**profile["prefs"], **(prefs or {})}) if prefs else profile["prefs"]
    new_name = (name or profile["name"]).strip()[:40] or profile["name"]
    is_onboarded = profile["onboarded"] if onboarded is None else bool(onboarded)
    daily_goal = int(new_prefs.get("daily_goal") or new_survey.get("daily_goal") or 5)
    db.execute(
        """UPDATE profiles SET name=?, survey=?, prefs=?, onboarded=?, daily_goal=?, updated_at=? WHERE id=?""",
        (new_name, json.dumps(new_survey), json.dumps(new_prefs), int(is_onboarded), daily_goal, iso(), profile_id),
    )
    # Keep the follow table in sync with the survey so ranking sees one source of truth.
    if survey:
        with db.writer() as conn:
            conn.execute("DELETE FROM follows WHERE profile_id=? AND kind='topic'", (profile_id,))
            for topic, weight in new_survey.get("topics", {}).items():
                if int(weight) >= 2:
                    conn.execute(
                        "INSERT OR IGNORE INTO follows(profile_id, kind, value, created_at) VALUES(?,?,?,?)",
                        (profile_id, "topic", topic, iso()),
                    )
            conn.execute("DELETE FROM follows WHERE profile_id=? AND kind='source'", (profile_id,))
            for source in new_survey.get("sources", [])[:60]:
                conn.execute(
                    "INSERT OR IGNORE INTO follows(profile_id, kind, value, created_at) VALUES(?,?,?,?)",
                    (profile_id, "source", source, iso()),
                )
    return get(profile_id)


def follow(profile_id: str, kind: str, value: str, *, on: bool = True) -> None:
    if kind not in ("topic", "source", "team", "keyword"):
        raise ValueError("bad follow kind")
    if on:
        db.execute(
            "INSERT OR IGNORE INTO follows(profile_id, kind, value, created_at) VALUES(?,?,?,?)",
            (profile_id, kind, value[:80], iso()),
        )
    else:
        db.execute("DELETE FROM follows WHERE profile_id=? AND kind=? AND value=?", (profile_id, kind, value[:80]))


def _today_stats(profile_id: str, profile: dict) -> dict:
    row = db.query_one(
        "SELECT read_count, minutes, xp FROM daily_stats WHERE profile_id=? AND day=?",
        (profile_id, day_key(now())),
    )
    goal = int(profile.get("daily_goal") or 5)
    read = int(row["read_count"]) if row else 0
    return {
        "read": read,
        "minutes": round(float(row["minutes"]), 1) if row else 0.0,
        "xp": int(row["xp"]) if row else 0,
        "goal": goal,
        "percent": min(100, round(read / goal * 100)) if goal else 0,
    }


def article_meta(article_id: int | None) -> tuple[str | None, str | None]:
    if not article_id:
        return None, None
    row = db.query_one("SELECT primary_topic, source_id FROM articles WHERE id=?", (article_id,))
    if row is None:
        return None, None
    return row["primary_topic"], row["source_id"]


def record_event(
    profile_id: str,
    kind: str,
    *,
    article_id: int | None = None,
    story_id: int | None = None,
    value: float = 0.0,
    meta: dict | None = None,
    count_xp: bool = True,
) -> dict:
    profile = get(profile_id)
    if profile is None:
        raise ValueError("unknown profile")
    topic, source_id = article_meta(article_id)
    xp_awarded = 0
    base_xp = _XP.get(kind, 0)
    if count_xp and base_xp:
        if kind in ("open", "read", "like", "share", "quiz_correct") and article_id:
            already = db.query_one(
                """SELECT 1 FROM events WHERE profile_id=? AND kind=? AND article_id=?
                   AND created_at >= ? LIMIT 1""",
                (profile_id, kind, article_id, start_of_day()),
            )
            if already:
                base_xp = 0
        xp_awarded = base_xp

    db.execute(
        """INSERT INTO events(profile_id, kind, article_id, story_id, topic, source_id, value, meta, created_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (profile_id, kind[:40], article_id, story_id, topic, source_id, float(value or 0),
         json.dumps(meta or {})[:2000], iso()),
    )

    read_increment = 1 if kind == "read" else 0
    minutes = float(value) / 60.0 if kind == "read" and value else (5.0 if kind == "read" else 0.0)
    if kind == "read" and not value:
        minutes = 2.5
    user_day = day_key(now())
    with db.writer() as conn:
        conn.execute(
            """INSERT INTO daily_stats(profile_id, day, read_count, minutes, xp) VALUES(?,?,?,?,?)
               ON CONFLICT(profile_id, day) DO UPDATE SET
                 read_count = daily_stats.read_count + excluded.read_count,
                 minutes = daily_stats.minutes + excluded.minutes,
                 xp = daily_stats.xp + excluded.xp""",
            (profile_id, user_day, read_increment, round(minutes, 2), xp_awarded),
        )

    streak_update = {}
    if kind == "read":
        streak_update = _touch_streak(profile_id, profile)
        xp_awarded += streak_update.pop("bonus", 0)

    if xp_awarded:
        db.execute("UPDATE profiles SET xp = xp + ?, updated_at=? WHERE id=?", (xp_awarded, iso(), profile_id))

    refreshed = get(profile_id) or profile
    return {
        "xp_awarded": xp_awarded,
        "xp": refreshed["xp"],
        "level": refreshed["level"],
        "level_title": refreshed["level_title"],
        "level_progress": refreshed["level_progress"],
        "streak": refreshed["streak"],
        "today": refreshed["today"],
        "badges": refreshed["badges"],
        "new_badges": streak_update.get("new_badges", []),
    }


def _touch_streak(profile_id: str, profile: dict) -> dict:
    today = day_key(now())
    last = profile["streak"]["last"]
    count = profile["streak"]["count"]
    bonus = 0
    new_day = last != today
    if last == today:
        return {"bonus": 0, "new_badges": []}
    if last:
        last_dt = parse_iso(last + "T00:00:00Z") if "T" not in last else parse_iso(last)
        yesterday = (now() - timedelta(days=1)).date().isoformat()
        if last == yesterday:
            count += 1
        else:
            count = 1
    else:
        count = 1
    if new_day:
        bonus = _XP["streak_day"]
    best = max(profile["streak"]["best"], count)
    db.execute(
        "UPDATE profiles SET streak_count=?, streak_best=?, streak_last=? WHERE id=?",
        (count, best, today, profile_id),
    )
    return {"bonus": bonus, "new_badges": []}


def badges(profile: dict) -> list[dict]:
    profile_id = profile["id"]
    reads = int(db.scalar("SELECT COUNT(*) FROM events WHERE profile_id=? AND kind='read'", (profile_id,), default=0) or 0)
    topics_read = int(db.scalar(
        "SELECT COUNT(DISTINCT topic) FROM events WHERE profile_id=? AND kind='read' AND topic IS NOT NULL",
        (profile_id,), default=0) or 0)
    sources_read = int(db.scalar(
        "SELECT COUNT(DISTINCT source_id) FROM events WHERE profile_id=? AND kind='read' AND source_id IS NOT NULL",
        (profile_id,), default=0) or 0)
    saves = int(db.scalar("SELECT COUNT(*) FROM saves WHERE profile_id=?", (profile_id,), default=0) or 0)
    quiz_correct = int(db.scalar(
        "SELECT COUNT(*) FROM events WHERE profile_id=? AND kind='quiz_correct'", (profile_id,), default=0) or 0)
    notes = int(db.scalar("SELECT COUNT(*) FROM notes WHERE profile_id=?", (profile_id,), default=0) or 0)
    briefs = int(db.scalar(
        "SELECT COUNT(*) FROM events WHERE profile_id=? AND kind='brief_complete'", (profile_id,), default=0) or 0)
    streak = profile["streak"]

    earned = []
    def award(badge_id: str) -> None:
        earned.append(badge_id)

    if reads >= 1:
        award("first_read")
    if streak["count"] >= 3:
        award("streak_3")
    if streak["count"] >= 7 or streak["best"] >= 7:
        award("streak_7")
    if streak["best"] >= 30:
        award("streak_30")
    if reads >= 25:
        award("reader_25")
    if reads >= 100:
        award("reader_100")
    if topics_read >= 5:
        award("explorer")
    if sources_read >= 10:
        award("source_spelunker")
    if quiz_correct >= 5:
        award("quiz_5")
    if saves >= 10:
        award("saver_10")
    if notes >= 1:
        award("note_taker")
    if briefs >= 5:
        award("brief_5")

    return [
        {**badge, "earned": badge["id"] in earned}
        for badge in BADGES
    ]


def stats(profile_id: str) -> dict:
    profile = get(profile_id)
    if profile is None:
        return {}
    totals = db.query_one(
        """SELECT
             COUNT(*) FILTER (WHERE kind='read') AS reads,
             COUNT(DISTINCT article_id) FILTER (WHERE kind='read') AS articles,
             COUNT(DISTINCT topic) FILTER (WHERE kind='read' AND topic IS NOT NULL) AS topics,
             COUNT(DISTINCT source_id) FILTER (WHERE kind='read' AND source_id IS NOT NULL) AS sources
           FROM events WHERE profile_id=?""",
        (profile_id,),
    )
    minutes = float(db.scalar(
        "SELECT COALESCE(SUM(minutes),0) FROM daily_stats WHERE profile_id=?", (profile_id,), default=0) or 0)
    weekly = db.query(
        "SELECT day, read_count, minutes, xp FROM daily_stats WHERE profile_id=? AND day >= ? ORDER BY day",
        (profile_id, day_key(now() - timedelta(days=6))),
    )
    topic_rows = db.query(
        """SELECT topic, COUNT(*) AS n FROM events
           WHERE profile_id=? AND kind='read' AND topic IS NOT NULL
           GROUP BY topic ORDER BY n DESC""",
        (profile_id,),
    )
    source_rows = db.query(
        """SELECT source_id, COUNT(*) AS n FROM events
           WHERE profile_id=? AND kind='read' AND source_id IS NOT NULL
           GROUP BY source_id ORDER BY n DESC LIMIT 8""",
        (profile_id,),
    )
    return {
        "reads": int(totals["reads"] or 0) if totals else 0,
        "articles": int(totals["articles"] or 0) if totals else 0,
        "topics": int(totals["topics"] or 0) if totals else 0,
        "sources": int(totals["sources"] or 0) if totals else 0,
        "minutes": round(minutes),
        "weekly": [dict(row) for row in weekly],
        "topic_breakdown": [{"topic": row["topic"], "count": row["n"]} for row in topic_rows],
        "source_breakdown": [
            {"source_id": row["source_id"], "name": (SOURCES.get(row["source_id"]).name if SOURCES.get(row["source_id"]) else row["source_id"]),
             "count": row["n"]}
            for row in source_rows
        ],
        "badges": profile["badges"],
        "streak": profile["streak"],
        "xp": profile["xp"],
        "level": profile["level"],
        "level_title": profile["level_title"],
    }


def daily_brief(profile_id: str, *, size: int = 5) -> dict:
    """A 2-minute briefing: the day's most important stories, diversified."""
    from .feed import card as make_card, load_candidates  # local import to avoid a cycle

    profile = get(profile_id)
    if profile is None:
        return {"stories": [], "minutes": 0}
    model = rank.build_model(profile_id, profile["survey"], profile["prefs"])
    rows = load_candidates(days=1, limit=400)
    if not rows:
        rows = load_candidates(days=4, limit=400)
    picked = rank.rank(rows, model, limit=size, diversity=True)
    items = []
    words = 0
    for row, score_value, reasons in picked:
        payload = make_card(row, model=model)
        payload["reasons"] = reasons
        payload["brief_score"] = round(score_value, 2)
        items.append(payload)
        # A brief is skimming summaries and overviews, not reading everything.
        words += len((payload.get("preview") or "").split()) + 45
    return {
        "stories": items,
        "minutes": max(2, round(words / 220)),
        "generated_at": iso(),
        "greeting": _greeting(profile),
    }


def _greeting(profile: dict) -> str:
    hour = now().hour
    if hour < 12:
        part = "Morning"
    elif hour < 18:
        part = "Afternoon"
    else:
        part = "Evening"
    name = (profile.get("name") or "").strip()
    return f"Good {part}, {name}" if name and name != "Student" else f"Good {part}"


def export(profile_id: str) -> dict:
    profile = get(profile_id)
    if profile is None:
        return {}
    saves = db.query(
        """SELECT s.collection, s.created_at, a.id, a.title, a.url, a.published_at,
                  a.primary_topic, src.name AS source_name
           FROM saves s JOIN articles a ON a.id=s.article_id JOIN sources src ON src.id=a.source_id
           WHERE s.profile_id=? ORDER BY s.created_at DESC""",
        (profile_id,),
    )
    notes = db.query("SELECT * FROM notes WHERE profile_id=? ORDER BY created_at DESC", (profile_id,))
    follows = db.query("SELECT kind, value, created_at FROM follows WHERE profile_id=?", (profile_id,))
    events = db.query(
        "SELECT kind, article_id, topic, source_id, value, created_at FROM events WHERE profile_id=? ORDER BY id DESC LIMIT 2000",
        (profile_id,),
    )
    stats_row = db.query("SELECT * FROM daily_stats WHERE profile_id=? ORDER BY day DESC", (profile_id,))
    return {
        "exported_at": iso(),
        "app": "Pulse",
        "profile": profile,
        "saved": [dict(row) for row in saves],
        "notes": [dict(row) for row in notes],
        "follows": [dict(row) for row in follows],
        "activity": [dict(row) for row in events],
        "daily_stats": [dict(row) for row in stats_row],
        "note": "Articles themselves live in the shared archive and are not personal data.",
    }


def delete(profile_id: str) -> None:
    with db.writer() as conn:
        for table in ("events", "saves", "notes", "follows", "searches", "daily_stats"):
            conn.execute(f"DELETE FROM {table} WHERE profile_id=?", (profile_id,))
        conn.execute("DELETE FROM profiles WHERE id=?", (profile_id,))


def saved(profile_id: str, collection: str | None = None) -> list[dict]:
    clause = " AND s.collection = ?" if collection else ""
    params = (profile_id, collection) if collection else (profile_id,)
    rows = db.query(
        f"""
        SELECT s.collection, s.created_at AS saved_at, a.*, src.name AS source_name, src.domain, src.lean,
               COALESCE(st.source_count, 1) AS story_source_count, COALESCE(st.heat, 0) AS story_heat,
               COALESCE(st.article_count, 1) AS story_article_count
        FROM saves s JOIN articles a ON a.id = s.article_id
        JOIN sources src ON src.id = a.source_id
        LEFT JOIN stories st ON st.id = a.story_id
        WHERE s.profile_id = ? {clause}
        ORDER BY s.created_at DESC
        """,
        params,
    )
    return [dict(row) for row in rows]


def collections(profile_id: str) -> list[dict]:
    rows = db.query(
        "SELECT collection, COUNT(*) AS n FROM saves WHERE profile_id=? GROUP BY collection ORDER BY n DESC",
        (profile_id,),
    )
    return [dict(row) for row in rows]


def save(profile_id: str, article_id: int, collection: str = "Saved") -> dict:
    exists = db.query_one("SELECT 1 FROM articles WHERE id=?", (article_id,))
    if not exists:
        raise ValueError("unknown article")
    db.execute(
        """INSERT INTO saves(profile_id, article_id, collection, created_at) VALUES(?,?,?,?)
           ON CONFLICT(profile_id, article_id) DO UPDATE SET collection=excluded.collection""",
        (profile_id, article_id, (collection or "Saved")[:60], iso()),
    )
    return {"saved": True, "collection": collection}


def unsave(profile_id: str, article_id: int) -> None:
    db.execute("DELETE FROM saves WHERE profile_id=? AND article_id=?", (profile_id, article_id))


def add_note(profile_id: str, article_id: int, body: str, *, quote: str = "",
             start: int | None = None, end: int | None = None) -> dict:
    cur = db.execute(
        """INSERT INTO notes(profile_id, article_id, quote, body, start_offset, end_offset, created_at)
           VALUES(?,?,?,?,?,?,?)""",
        (profile_id, article_id, quote[:800], body.strip()[:4000], start, end, iso()),
    )
    return {"id": cur.lastrowid, "created_at": iso()}


def notes(profile_id: str, article_id: int) -> list[dict]:
    rows = db.query(
        "SELECT * FROM notes WHERE profile_id=? AND article_id=? ORDER BY created_at DESC",
        (profile_id, article_id),
    )
    return [dict(row) for row in rows]


def delete_note(profile_id: str, note_id: int) -> None:
    db.execute("DELETE FROM notes WHERE profile_id=? AND id=?", (profile_id, note_id))
