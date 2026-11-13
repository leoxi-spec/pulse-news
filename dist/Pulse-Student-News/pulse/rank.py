"""Personalisation.

A transparent, tunable scorer rather than a black box. Every ranked card can
explain itself ("You follow Tech", "6 outlets covering this"), which matters a
lot for a news product aimed at students learning to think about why they see
what they see.

Signals:
  * the onboarding survey (explicit topic/source choices)
  * followed topics, sources and teams
  * engagement events (opens, reads, saves, likes, hides) with 21-day decay
  * keywords from saved stories
  * freshness, story heat (how many outlets), and reading-time fit
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import timedelta

from .db import db
from .sources import TOPIC_LABELS, get_source
from .timeutil import iso, minutes_since, now, parse_iso

_ENGAGEMENT_WEIGHTS = {
    "view": 0.5,
    "open": 0.7,
    "read": 1.6,
    "dwell": 0.028,     # per second, capped later
    "save": 3.0,
    "like": 3.0,
    "share": 2.0,
    "quiz_pass": 2.5,
    "brief_open": 1.2,
    "dislike": -3.0,
    "hide": -6.0,
    "unsave": -1.0,
}

_AFFINITY_HALF_LIFE_DAYS = 21.0


@dataclass
class ProfileModel:
    profile_id: str
    topic_weights: dict[str, float] = field(default_factory=dict)
    source_weights: dict[str, float] = field(default_factory=dict)
    keyword_weights: dict[str, float] = field(default_factory=dict)
    followed_topics: set[str] = field(default_factory=set)
    followed_sources: set[str] = field(default_factory=set)
    hidden_topics: set[str] = field(default_factory=set)
    read_ids: set[int] = field(default_factory=set)
    saved_ids: set[int] = field(default_factory=set)
    dwell_topics: dict[str, float] = field(default_factory=dict)
    region: str = ""
    reading_pref: str = "medium"
    daily_goal: int = 5
    ai_enabled: bool = True
    hide_paywalled: bool = False
    interests_text: str = ""

    def topic_weight(self, topic: str) -> float:
        return self.topic_weights.get(topic, 0.12)


def _decay(created_at: str | None) -> float:
    age_days = max(0.0, minutes_since(created_at) / 1440)
    return 0.5 ** (age_days / _AFFINITY_HALF_LIFE_DAYS)


def build_model(profile_id: str, survey: dict | None = None, prefs: dict | None = None) -> ProfileModel:
    survey = survey or {}
    prefs = prefs or {}
    model = ProfileModel(profile_id=profile_id)
    model.region = (survey.get("region") or "").strip()
    model.reading_pref = prefs.get("reading_length") or survey.get("reading_length") or "medium"
    model.daily_goal = int(prefs.get("daily_goal") or survey.get("daily_goal") or 5)
    model.ai_enabled = bool(prefs.get("ai_overview", True))
    model.hide_paywalled = bool(prefs.get("hide_paywalled", False))
    model.interests_text = " ".join(survey.get("keywords") or [])

    # Explicit survey weights (0-3) land on a 0.15 .. 1.0 scale.
    raw_topics = survey.get("topics") or {}
    if isinstance(raw_topics, list):
        raw_topics = {t: 2 for t in raw_topics}
    for topic, weight in raw_topics.items():
        try:
            value = float(weight)
        except (TypeError, ValueError):
            continue
        model.topic_weights[topic] = min(1.0, 0.15 + value / 3.0 * 0.85)
        if value >= 2:
            model.followed_topics.add(topic)

    for source_id in survey.get("sources") or []:
        model.source_weights[source_id] = model.source_weights.get(source_id, 0) + 0.9
        model.followed_sources.add(source_id)

    for topic in survey.get("avoid") or []:
        model.hidden_topics.add(topic)

    # Follows currently in the DB win over the survey snapshot.
    for row in db.query("SELECT kind, value FROM follows WHERE profile_id=?", (profile_id,)):
        if row["kind"] == "topic":
            model.followed_topics.add(row["value"])
            model.topic_weights[row["value"]] = max(model.topic_weights.get(row["value"], 0.2), 0.85)
        elif row["kind"] == "source":
            model.followed_sources.add(row["value"])
            model.source_weights[row["value"]] = max(model.source_weights.get(row["value"], 0), 0.9)

    since = iso(now() - timedelta(days=120))
    rows = db.query(
        """
        SELECT kind, topic, source_id, article_id, value, created_at, meta
        FROM events WHERE profile_id=? AND created_at >= ?
        """,
        (profile_id, since),
    )
    for row in rows:
        weight = _ENGAGEMENT_WEIGHTS.get(row["kind"], 0.0)
        if row["kind"] == "dwell":
            weight = min(weight * float(row["value"] or 0), 2.4)
        if not weight:
            continue
        decayed = weight * _decay(row["created_at"])
        topic = row["topic"]
        if topic:
            model.topic_weights[topic] = model.topic_weights.get(topic, 0.12) + decayed * 0.055
            if row["kind"] == "dwell":
                model.dwell_topics[topic] = model.dwell_topics.get(topic, 0.0) + float(row["value"] or 0) * _decay(row["created_at"])
        if row["source_id"]:
            model.source_weights[row["source_id"]] = model.source_weights.get(row["source_id"], 0.0) + decayed * 0.05
        if row["kind"] in ("view", "open", "read") and row["article_id"]:
            model.read_ids.add(int(row["article_id"]))

    # Keywords from saved + liked stories.
    keyword_rows = db.query(
        """
        SELECT a.title FROM saves s JOIN articles a ON a.id = s.article_id
        WHERE s.profile_id=? ORDER BY s.created_at DESC LIMIT 40
        """,
        (profile_id,),
    ) + db.query(
        """
        SELECT a.title FROM events e JOIN articles a ON a.id = e.article_id
        WHERE e.profile_id=? AND e.kind IN ('like','share') ORDER BY e.created_at DESC LIMIT 40
        """,
        (profile_id,),
    )
    from .stories import tokens_for

    counts: dict[str, int] = {}
    for row in keyword_rows:
        for token in tokens_for(row["title"]):
            counts[token] = counts.get(token, 0) + 1
    for token, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:24]:
        if count >= 2:
            model.keyword_weights[token] = min(1.4, count * 0.22)

    for row in db.query("SELECT article_id FROM saves WHERE profile_id=?", (profile_id,)):
        model.saved_ids.add(int(row["article_id"]))

    # Clamp topic weights so engagement cannot run away.
    for topic, weight in list(model.topic_weights.items()):
        model.topic_weights[topic] = max(-0.4, min(1.6, weight))
    return model


def _reading_fit(pref: str, minutes: int) -> float:
    minutes = max(1, int(minutes or 1))
    if pref == "short":
        return 1.0 if minutes <= 4 else (-0.5 if minutes > 8 else 0.2)
    if pref == "long":
        return 1.0 if minutes >= 6 else 0.15
    return 1.0 if 2 <= minutes <= 9 else 0.2


def score(row, model: ProfileModel) -> tuple[float, list[str]]:
    """Return (score, human-readable reasons)."""
    reasons: list[str] = []
    topic = row["primary_topic"]
    extra_topics = []
    try:
        extra_topics = json.loads(row["topics"] or "[]")
    except (ValueError, TypeError):
        pass

    weight = model.topic_weight(topic)
    value = weight * 7.0
    if topic in model.followed_topics:
        reasons.append(f"You follow {TOPIC_LABELS.get(topic, topic.title())}")
    elif model.dwell_topics.get(topic, 0) >= 12:
        reasons.append(f"You watch {TOPIC_LABELS.get(topic, topic.title())} shorts")
    for extra in extra_topics[:3]:
        if extra != topic:
            value += model.topic_weights.get(extra, 0.12) * 1.1

    age = minutes_since(row["published_at"] or row["first_seen_at"])
    recency = math.exp(-max(age, 0) / (60 * 20))
    value += recency * 6.5
    if age <= 90:
        reasons.append("Just published")
    elif age > 60 * 24 * 3:
        value -= 1.4

    source_affinity = model.source_weights.get(row["source_id"], 0.0)
    if source_affinity:
        value += min(source_affinity, 2.2) * 2.6
        if source_affinity > 0.7:
            reasons.append("From a source you read")
    if row["source_id"] in model.followed_sources and not source_affinity:
        value += 1.6

    if row["is_breaking"]:
        value += 3.2
        reasons.append("Breaking")
    story_sources = row["story_source_count"] or 1
    if story_sources >= 3:
        value += min(story_sources, 12) * 0.42
        reasons.append(f"{story_sources} outlets covering")

    if row["content_state"] == "extracted":
        value += 0.9
    elif row["content_state"] == "linkonly":
        value -= 0.5
    if row["image_url"]:
        value += 0.85
    else:
        value -= 0.45
    if row["paywalled"]:
        value -= 0.7
        if not reasons:
            reasons.append("Paywalled at the source")
    value += _reading_fit(model.reading_pref, row["reading_minutes"]) * 0.9

    title_lower = (row["title"] or "").lower()
    keyword_hit = False
    for keyword, kw_weight in model.keyword_weights.items():
        if keyword in title_lower:
            value += min(kw_weight, 1.2) * 1.6
            keyword_hit = True
    if keyword_hit:
        reasons.append("Matches topics you save")

    for keyword in model.interests_text.lower().split():
        if len(keyword) > 3 and keyword in title_lower:
            value += 0.55

    if model.region:
        country = (row["source_country"] or "").upper()
        if country and country == model.region.upper():
            value += 0.45

    if int(row["id"]) in model.read_ids:
        value -= 5.0
    if int(row["id"]) in model.saved_ids:
        value -= 1.0
    if topic in model.hidden_topics:
        value -= 100.0
    if model.hide_paywalled and row["paywalled"]:
        value -= 100.0
    return value, reasons[:3]


def diversify(rows: list, *, limit: int, per_topic: int = 5, per_source: int = 3, window: int = 24) -> list:
    """Keep the top of the feed varied: no single outlet or topic monopolises."""
    chosen = []
    deferred = []
    topic_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    story_seen: set[int] = set()
    for row in rows:
        if len(chosen) >= limit and not deferred:
            break
        story_id = row["story_id"]
        if story_id and story_id in story_seen:
            deferred.append(row)
            continue
        if len(chosen) < window:
            if topic_counts.get(row["primary_topic"], 0) >= per_topic:
                deferred.append(row)
                continue
            if source_counts.get(row["source_id"], 0) >= per_source:
                deferred.append(row)
                continue
        chosen.append(row)
        topic_counts[row["primary_topic"]] = topic_counts.get(row["primary_topic"], 0) + 1
        source_counts[row["source_id"]] = source_counts.get(row["source_id"], 0) + 1
        if story_id:
            story_seen.add(story_id)
        if len(chosen) >= limit:
            break
    if len(chosen) < limit:
        for row in deferred:
            if len(chosen) >= limit:
                break
            chosen.append(row)
    return chosen


def rank(rows: list, model: ProfileModel, *, limit: int = 40, diversity: bool = True) -> list[tuple[object, float, list[str]]]:
    scored = []
    for row in rows:
        value, reasons = score(row, model)
        scored.append((row, value, reasons))
    scored.sort(key=lambda item: item[1], reverse=True)
    if not diversity:
        return scored[:limit]
    selected_rows = diversify([item[0] for item in scored], limit=limit)
    by_id = {item[0]["id"]: item for item in scored}
    return [by_id[row["id"]] for row in selected_rows if row["id"] in by_id]


def trending(rows: list, *, limit: int = 12) -> list:
    """Story heat first, then evidence from multiple outlets."""
    def key(row):
        heat = (row["story_heat"] or 0) + (row["story_source_count"] or 1) * 1.3
        freshness = math.exp(-max(minutes_since(row["published_at"] or row["first_seen_at"]), 0) / (60 * 12))
        return heat + freshness * 5

    ranked = sorted(rows, key=key, reverse=True)
    seen_stories: set[int] = set()
    output = []
    for row in ranked:
        story_id = row["story_id"]
        if story_id and story_id in seen_stories:
            continue
        if story_id:
            seen_stories.add(story_id)
        output.append(row)
        if len(output) >= limit:
            break
    return output


def level_for_xp(xp: int) -> tuple[int, int, int, str]:
    """Return (level, xp_into_level, xp_for_next, title)."""
    titles = [
        "Rookie", "Curious", "Informed", "Analyst", "Reporter", "Editor",
        "Anchor", "Correspondent", "Bureau Chief", "Editor-in-Chief",
    ]
    level = 1
    remaining = max(0, xp)
    step = 60
    while remaining >= step and level < 99:
        remaining -= step
        level += 1
        step = int(step * 1.18)
    title = titles[min(len(titles) - 1, (level - 1) // 2)]
    return level, remaining, step, title


def why_this(row, model: ProfileModel) -> list[str]:
    _, reasons = score(row, model)
    if not reasons:
        reasons = ["Trending now"]
    return reasons
