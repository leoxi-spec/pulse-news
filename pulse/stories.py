"""Story clustering.

Ten outlets covering the same event should produce *one* card in the feed, not
ten.  Headlines from different newsrooms are similar enough for token-set
similarity to work well, and keeping the cluster key in SQLite means clustering
survives restarts and keeps improving as the archive grows.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .timeutil import minutes_since, parse_iso

_STOP = set(
    """a an the and or but if of to in on at by for with from as is are was were be been being
    this that these those it its their there here than then so such not no nor do does did
    have has had will would can could should may might must about into over under after before
    more most other some any all both each few many much own same very just also only even still
    says say said new update updates live breaking latest watch video photos report reports
    exclusive analysis opinion editorial column first second third amid ahead back away
    """.split()
)

_PUNCT = re.compile(r"[^\w\s]")
_NUMBERS = re.compile(r"\b\d[\d,.]*\b")


def _singular(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def tokens_for(title: str) -> set[str]:
    lowered = _PUNCT.sub(" ", (title or "").lower())
    lowered = _NUMBERS.sub(" ", lowered)
    out: set[str] = set()
    for token in lowered.split():
        token = _singular(token)
        if len(token) < 3 or token in _STOP:
            continue
        out.add(token)
    return out


def _significant(tokens: set[str]) -> set[str]:
    return {t for t in tokens if len(t) >= 5}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def containment(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def similarity(a: set[str], b: set[str]) -> float:
    shared = a & b
    if len(shared) < 2 or len(_significant(shared)) < 2:
        return 0.0
    return max(jaccard(a, b), containment(a, b) * 0.86)


def is_same_story(title_a: str, title_b: str, *, threshold: float = 0.52) -> bool:
    a, b = tokens_for(title_a), tokens_for(title_b)
    if not a or not b:
        return False
    shared = a & b
    if len(shared) < 2:
        return False
    sim = similarity(a, b)
    if sim >= threshold:
        return True
    # Short headlines ("Trump wins Iowa") need a stricter overlap rule.
    if containment(a, b) >= 0.8 and len(_significant(shared)) >= 2 and min(len(a), len(b)) >= 2:
        return True
    return False


def story_key(title: str) -> str:
    tokens = sorted(tokens_for(title))[:8]
    digest = hashlib.sha1(" ".join(tokens).encode()).hexdigest()[:16]
    return digest or hashlib.sha1(title.encode()).hexdigest()[:16]


def heat_score(source_count: int, article_count: int, last_seen_at: str | None) -> float:
    age_hours = max(0.0, minutes_since(last_seen_at) / 60.0)
    recency = max(0.0, 18.0 - age_hours) / 18.0
    return round(source_count * 2.4 + min(article_count, 10) * 0.7 + recency * 6.0, 2)


def is_breaking(source_count: int, first_seen_at: str | None) -> bool:
    age = minutes_since(first_seen_at)
    if source_count >= 4 and age <= 180:
        return True
    if source_count >= 2 and age <= 30:
        return True
    return False


_ENTITY = re.compile(r"\b([A-Z][A-Za-z'’.-]{2,}(?:\s+(?:of|the|and|de|van|von)?\s*[A-Z][A-Za-z'’.-]{2,}){0,2})\b")


def entities_for(title: str) -> set[str]:
    """Proper-noun-ish keys used as an extra clustering signal."""
    out: set[str] = set()
    for match in _ENTITY.finditer(title or ""):
        parts = [p for p in match.group(1).split() if p.lower() not in _STOP and len(p) > 1]
        if not parts:
            continue
        name = " ".join(parts).lower()
        if len(name) < 3:
            continue
        out.add(name)
    return out


@dataclass
class StoryRef:
    id: int
    title: str
    topic: str
    signatures: list[set[str]] = field(default_factory=list)
    entities: set[str] = field(default_factory=set)
    last_seen_at: str | None = None

    @property
    def tokens(self) -> set[str]:
        return self.signatures[0] if self.signatures else set()


class Clusterer:
    """In-memory inverted index over recent stories.

    A story keeps a small set of headline signatures (one per article that was
    merged into it). That catches the common case where the first headline
    ("US and Russia begin talks") is worded quite differently from a later one
    ("Ukraine hails 'constructive' first day of peace talks").
    """

    def __init__(self, stories: list[StoryRef], *, threshold: float = 0.48):
        self.threshold = threshold
        self.stories: dict[int, StoryRef] = {}
        self.index: dict[str, set[int]] = {}
        for story in stories:
            self.add(story)

    def add(self, story: StoryRef) -> None:
        if not story.signatures:
            story.signatures = [tokens_for(story.title)]
        if not story.entities:
            story.entities = entities_for(story.title)
        self.stories[story.id] = story
        for signature in story.signatures:
            for token in signature:
                self.index.setdefault(token, set()).add(story.id)

    def extend(self, story: StoryRef, title: str) -> None:
        """Remember another wording of the same story."""
        tokens = tokens_for(title)
        if tokens and len(story.signatures) < 8:
            story.signatures.append(tokens)
            for token in tokens:
                self.index.setdefault(token, set()).add(story.id)
        story.entities |= entities_for(title)

    def candidates(self, title: str) -> set[int]:
        tokens = tokens_for(title)
        counts: dict[int, int] = {}
        for token in tokens:
            for story_id in self.index.get(token, ()):
                counts[story_id] = counts.get(story_id, 0) + 1
        return {story_id for story_id, count in counts.items() if count >= 2}

    def match(self, title: str, topic: str) -> StoryRef | None:
        tokens = tokens_for(title)
        if not tokens:
            return None
        entities = entities_for(title)
        best: tuple[float, StoryRef] | None = None
        for story_id in self.candidates(title):
            story = self.stories.get(story_id)
            if story is None:
                continue
            sim = max((similarity(tokens, signature) for signature in story.signatures), default=0.0)
            entity_hit = entities & story.entities
            entity_match = bool(entity_hit) and (
                len(entity_hit) >= 2 or any(" " in e for e in entity_hit)
            )
            if sim < self.threshold:
                if not (entity_match and sim >= 0.24):
                    continue
            if story.topic != topic:
                # Topic classifiers disagree at the edges (politics vs world vs
                # us), so a cross-topic merge needs either matching entities or
                # a very close headline match.
                if not ((entity_match and sim >= 0.5) or sim >= 0.72):
                    continue
            score = sim + (0.08 if entity_match else 0)
            if best is None or score > best[0]:
                best = (score, story)
        return best[1] if best else None

    def remove(self, story_id: int) -> None:
        story = self.stories.pop(story_id, None)
        if not story:
            return
        for signature in story.signatures:
            for token in signature:
                ids = self.index.get(token)
                if ids:
                    ids.discard(story_id)
                    if not ids:
                        self.index.pop(token, None)

    def __len__(self) -> int:
        return len(self.stories)


def load_recent(days: int = 5) -> list[StoryRef]:
    from .db import db
    from .timeutil import iso, now
    from datetime import timedelta

    since = iso(now() - timedelta(days=days))
    rows = db.query(
        """
        SELECT s.id, s.title, s.primary_topic, s.last_seen_at
        FROM stories s WHERE s.last_seen_at >= ?
        ORDER BY s.last_seen_at DESC LIMIT 4000
        """,
        (since,),
    )
    return [
        StoryRef(id=row["id"], title=row["title"], topic=row["primary_topic"], last_seen_at=row["last_seen_at"])
        for row in rows
    ]


def best_title(titles: list[str]) -> str:
    """Prefer a headline that is specific but not clickbait-long."""
    def score(title: str) -> float:
        words = len(title.split())
        score = 0.0
        if 6 <= words <= 16:
            score += 3
        if any(mark in title for mark in ("?", "!", "Watch:", "Live:")):
            score -= 1.5
        if title.isupper():
            score -= 2
        score += min(len(title), 90) / 90
        return score

    return max(titles, key=score) if titles else ""


def freshness_note(first_seen_at: str | None, source_count: int) -> str:
    age = minutes_since(first_seen_at)
    if age < 60 and source_count >= 3:
        return "Breaking"
    if age < 180:
        return "Developing"
    if age < 1440:
        return "Today"
    return ""


def story_age_ok(last_seen_at: str | None, hours: int = 96) -> bool:
    dt = parse_iso(last_seen_at)
    if dt is None:
        return False
    return minutes_since(last_seen_at) <= hours * 60
