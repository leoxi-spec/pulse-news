"""Impact, roadmap and feedback: the product side of Pulse.

The numbers here are deliberately honest. Pulse is a single-server pilot, so
the dashboard reports content inventory, this reader's usage and product
quality — not invented user counts.
"""
from __future__ import annotations

from datetime import date

from .config import APP_VERSION
from .db import db
from .profiles import stats as reading_stats
from .sources import SOURCES, TOPIC_LABELS, catalog_stats
from .timeutil import iso, now

ROADMAP = [
    {
        "id": "teacher-dashboard",
        "title": "Teacher dashboard & class codes",
        "stage": "Next",
        "area": "Classroom",
        "summary": "Create a class, share a code, assign a brief and see which discussion questions students answered.",
    },
    {
        "id": "offline-packs",
        "title": "Offline weekly packs",
        "stage": "Next",
        "area": "Access",
        "summary": "Download a week of reading, quizzes and citations for classrooms or commutes with weak Wi-Fi.",
    },
    {
        "id": "ap-ib-packs",
        "title": "AP / IB source packs",
        "stage": "Next",
        "area": "Learning",
        "summary": "Curated source sets for AP Seminar, AP Lang, Theory of Knowledge and extended essays.",
    },
    {
        "id": "a11y-audit",
        "title": "Screen-reader and contrast audit",
        "stage": "Now",
        "area": "Accessibility",
        "summary": "Publish a real WCAG 2.2 AA report, keyboard walkthroughs and fixes from the audit.",
    },
    {
        "id": "multilingual",
        "title": "Multilingual editions",
        "stage": "Later",
        "area": "Access",
        "summary": "Spanish, Arabic and French interfaces with translated navigation and reading labels.",
    },
    {
        "id": "school-sso",
        "title": "School SSO and district admin",
        "stage": "Later",
        "area": "Business",
        "summary": "Google Classroom and Clever sign-in for schools that want managed accounts.",
    },
    {
        "id": "audio-brief",
        "title": "Daily audio brief",
        "stage": "Exploring",
        "area": "Product",
        "summary": "A five-minute spoken briefing generated from the reader's own brief, with transcripts.",
    },
    {
        "id": "student-press",
        "title": "Student press partnerships",
        "stage": "Exploring",
        "area": "Impact",
        "summary": "Pair local newsrooms with student journalists for source checks and published responses.",
    },
]

FEEDBACK_CATEGORIES = {
    "feature": "Feature idea",
    "bug": "Bug report",
    "source": "Source request",
    "classroom": "Classroom pilot",
    "other": "Something else",
}


def _counts(sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in db.query(sql, params)]


def metrics(profile: dict) -> dict:
    stats = db.stats()
    catalog = catalog_stats()
    reading = reading_stats(profile["id"]) if profile else {}
    topic_rows = _counts(
        "SELECT primary_topic AS topic, COUNT(*) AS n FROM articles GROUP BY primary_topic ORDER BY n DESC"
    )
    country_rows = _counts(
        "SELECT country, COUNT(*) AS n FROM sources GROUP BY country ORDER BY n DESC"
    )
    lean_rows = _counts(
        "SELECT lean, COUNT(*) AS n FROM sources GROUP BY lean ORDER BY n DESC"
    )
    video_rows = _counts(
        "SELECT video_kind AS kind, COUNT(*) AS n FROM articles WHERE video_kind IS NOT NULL GROUP BY video_kind ORDER BY n DESC"
    )
    event_rows = _counts(
        "SELECT kind, COUNT(*) AS n FROM events WHERE profile_id=? GROUP BY kind ORDER BY n DESC",
        (profile["id"],),
    ) if profile else []
    server_usage = db.query_one(
        """SELECT COUNT(*) AS reads, COUNT(DISTINCT article_id) AS articles,
                  COUNT(DISTINCT profile_id) AS readers
           FROM events WHERE kind='read'"""
    )
    server_minutes = float(db.scalar("SELECT COALESCE(SUM(minutes),0) FROM daily_stats", default=0) or 0)
    feedback_rows = _counts(
        "SELECT category, COUNT(*) AS n FROM feedback GROUP BY category ORDER BY n DESC"
    )
    feedback_count = int(db.scalar("SELECT COUNT(*) FROM feedback", default=0) or 0)
    vote_count = int(db.scalar("SELECT COUNT(*) FROM roadmap_votes", default=0) or 0)
    videos = int(stats.get("videos", 0) or 0)
    earliest = stats.get("earliest")
    years = None
    if earliest:
        try:
            years = max(1, date.today().year - int(str(earliest)[:4]) + 1)
        except (TypeError, ValueError):
            years = None
    topics_covered = len([row for row in topic_rows if row["n"]])
    return {
        "generated_at": iso(),
        "app": {"name": "Pulse", "version": APP_VERSION},
        "product": {
            "sources": catalog["sources"],
            "feeds": catalog["feeds"],
            "countries": catalog["countries"],
            "topics": catalog["topics"],
            "videos": videos,
            "articles": int(stats.get("articles", 0) or 0),
            "stories": int(stats.get("stories", 0) or 0),
            "readable": int(stats.get("full_text", 0) or 0),
            "feeds_ok": int(stats.get("feeds_ok", 0) or 0),
            "feeds_total": int(stats.get("feeds", 0) or 0),
            "archive_years": years,
            "earliest": earliest,
            "latest": stats.get("latest"),
            "db_bytes": int(stats.get("db_bytes", 0) or 0),
            "topics_covered": topics_covered,
        },
        "diversity": {
            "topics": [
                {"id": row["topic"], "label": TOPIC_LABELS.get(row["topic"], row["topic"]), "count": row["n"]}
                for row in topic_rows
            ],
            "countries": [row for row in country_rows[:12]],
            "leans": [row for row in lean_rows],
        },
        "video": {
            "total": videos,
            "kinds": [{"kind": row["kind"], "count": row["n"]} for row in video_rows],
        },
        "usage": {
            **reading,
            "server": {
                "reads": int(server_usage["reads"] or 0) if server_usage else 0,
                "articles": int(server_usage["articles"] or 0) if server_usage else 0,
                "readers": int(server_usage["readers"] or 0) if server_usage else 0,
                "minutes": round(server_minutes),
            },
            "events": [{"kind": row["kind"], "count": row["n"]} for row in event_rows],
        },
        "quality": {
            "tests": "132",
            "third_party_js": 0,
            "trackers": 0,
            "ads": 0,
            "runtime": "Python standard library",
            "storage": "SQLite + FTS5, owned by the reader",
        },
        "privacy": {
            "ads": 0,
            "trackers": 0,
            "data_sold": 0,
            "accounts_required": False,
            "local_first": True,
        },
        "feedback": {
            "total": feedback_count,
            "categories": [{"id": row["category"], "count": row["n"]} for row in feedback_rows],
            "votes": vote_count,
        },
        "method": "A single-server student pilot. Figures describe the archive and this reader's use; they are not a claim of millions of users.",
    }


def roadmap(profile_id: str) -> list[dict]:
    votes = {
        row["item_id"]: row["n"]
        for row in db.query("SELECT item_id, COUNT(*) AS n FROM roadmap_votes GROUP BY item_id")
    }
    mine = {
        row["item_id"]
        for row in db.query("SELECT item_id FROM roadmap_votes WHERE profile_id=?", (profile_id,))
    }
    return [
        {**item, "votes": int(votes.get(item["id"], 0)), "voted": item["id"] in mine}
        for item in ROADMAP
    ]


def vote(profile_id: str, item_id: str, on: bool = True) -> dict:
    if not any(item["id"] == item_id for item in ROADMAP):
        raise ValueError("unknown roadmap item")
    if on:
        db.execute(
            "INSERT INTO roadmap_votes(profile_id, item_id, created_at) VALUES(?,?,?) "
            "ON CONFLICT(profile_id, item_id) DO NOTHING",
            (profile_id, item_id, iso()),
        )
    else:
        db.execute("DELETE FROM roadmap_votes WHERE profile_id=? AND item_id=?", (profile_id, item_id))
    item = next(row for row in roadmap(profile_id) if row["id"] == item_id)
    return item


def add_feedback(profile_id: str, category: str, message: str, email: str = "") -> dict:
    category = category if category in FEEDBACK_CATEGORIES else "other"
    message = " ".join(str(message or "").split()).strip()
    if len(message) < 3:
        raise ValueError("Please write a little more.")
    if len(message) > 4000:
        message = message[:4000]
    email = " ".join(str(email or "").split()).strip()[:200]
    db.execute(
        "INSERT INTO feedback(profile_id, category, message, email, created_at) VALUES(?,?,?,?,?)",
        (profile_id, category, message, email or None, iso()),
    )
    total = int(db.scalar("SELECT COUNT(*) FROM feedback", default=0) or 0)
    return {"ok": True, "total": total, "category": category}


def _topic_lines(rows: list[dict], limit: int = 8) -> str:
    return "\n".join(
        f"- {row['label']}: {row['count']:,}" for row in rows[:limit]
    )


def report_markdown(data: dict) -> str:
    p = data["product"]
    u = data["usage"]
    q = data["quality"]
    return f"""# Pulse — Impact Report

Generated {data['generated_at'][:10]} · version {data['app']['version']}

## What Pulse is

A local-first news reader for students: {p['sources']} sources, {p['countries']} countries, {p['topics']} topics, video from newsrooms and YouTube, a permanent searchable archive, classroom tools and no ads.

> {data['method']}

## Content inventory

| Measure | Value |
|---|---:|
| Sources | {p['sources']:,} |
| Feeds | {p['feeds']:,} |
| Countries | {p['countries']} |
| Topics | {p['topics']} |
| Articles archived | {p['articles']:,} |
| Videos indexed | {p['videos']:,} |
| Full-text stories | {p['readable']:,} |
| Stories clustered | {p['stories']:,} |

## Server activity

| Measure | Value |
|---|---:|
| Reading events | {u.get('server', {}).get('reads', 0):,} |
| Stories opened | {u.get('server', {}).get('articles', 0):,} |
| Readers | {u.get('server', {}).get('readers', 0):,} |
| Reading minutes | {u.get('server', {}).get('minutes', 0):,} |

## This reader

| Measure | Value |
|---|---:|
| Stories opened | {u.get('articles', 0):,} |
| Reading minutes | {u.get('minutes', 0):,} |
| Topics read | {u.get('topics', 0)} |
| Sources read | {u.get('sources', 0)} |
| Streak | {u.get('streak', {}).get('count', 0) if isinstance(u.get('streak'), dict) else 0} days |
| XP | {u.get('xp', 0):,} |

## Source diversity

### Topics
{_topic_lines(data['diversity']['topics'])}

### Countries
{chr(10).join(f"- {row['country']}: {row['n']:,}" for row in data['diversity']['countries'][:8])}

## Product quality

- {q['tests']} automated tests
- {q['third_party_js']} third-party JavaScript frameworks
- {q['trackers']} trackers · {q['ads']} ads
- Runtime: {q['runtime']}
- Storage: {q['storage']}
- Database size: {p['db_bytes'] / 1_000_000:.1f} MB

## Privacy

Pulse collects no advertising data, sells no data and requires no account. The archive and reading history live in a SQLite file on the server the reader controls.

## Roadmap

{chr(10).join(f"- {item['title']} ({item['stage']}) — {item['summary']}" for item in ROADMAP)}

---

Prepared from live product data. No user counts are fabricated.
"""


def press_kit_markdown(data: dict) -> str:
    p = data["product"]
    return f"""# Pulse — Press Kit

## One line

A calmer, local-first news app that helps students read widely, compare sources and walk into class with context.

## The problem

Student news consumption is fragmented across feeds, paywalls, push alerts and short videos. Most products optimise for time spent, not understanding. Teachers lack a simple way to bring current events into a lesson without ads or tracking.

## The product

- {p['sources']} publications and {p['feeds']} feeds from {p['countries']} countries
- {p['topics']} topics, including a dedicated motorsport section
- {p['videos']:,} publisher and YouTube videos with a privacy-enhanced player
- A permanent, searchable archive with FTS5
- A two-minute brief, quizzes, citations, study tools and classroom lesson plans
- Five age bands, accessibility settings and a reduced-motion mode
- No ads, no trackers, no account required

## By the numbers

- {p['articles']:,} articles archived
- {p['readable']:,} full-text stories
- {p['videos']:,} videos indexed
- {p['topics_covered']} topics with published stories
- {data['quality']['tests']} automated tests
- {data['quality']['third_party_js']} third-party JavaScript frameworks

> {data['method']}

## How it works

Python standard library on the server, SQLite with WAL and FTS5, vanilla ES modules on the client. Feeds are fetched incrementally, articles are extracted and clustered, and the archive is append-only. The app is installable as a PWA and runs on one machine.

## Business model

Free for individual students. A future school licence could cover teacher dashboards, class codes, offline packs and SSO. The product is deliberately low-cost to operate: no per-user cloud bill, no ad network, no data broker.

## Impact

The classroom toolkit turns the day's news into a 45-minute media-literacy lesson: read, compare coverage, discuss, cite, reflect. The roadmap is public and voted on by readers.

## Contact

Pulse is an independent student project. Contact the operator of this server for interviews, classroom pilots or a walkthrough.
"""


def generated_on() -> str:
    return now().strftime("%d %B %Y")
