"""Topic classification and light entity extraction.

Deliberately lexicon-based: it is deterministic, private (no network calls),
fast enough to run on every ingested item, and easy to audit.  A feed's topic
hint acts as a prior, never as an override, so a stray tech story on a sports
feed still lands in Tech.
"""
from __future__ import annotations

import re
from collections import Counter

from .sources import TOPIC_SLUGS

LEXICON: dict[str, tuple[str, ...]] = {
    "world": (
        "war", "conflict", "ceasefire", "refugee", "refugees", "sanctions", "troops", "invasion",
        "diplomatic", "diplomat", "border", "humanitarian", "united nations", "nato", "treaty",
        "foreign minister", "embassy", "military", "missile", "drone strike", "peace talks",
        "summit", "coup", "insurgent", "militant", "aid convoy", "famine",
    ),
    "us": (
        "white house", "congress", "senate", "supreme court", "federal", "governor", "california",
        "texas", "florida", "new york", "chicago", "los angeles", "immigration", "border patrol",
        "gun control", "police", "sheriff", "school board", "medicaid", "medicare", "social security",
        "fbi", "doj", "pentagon", "capitol hill", "american", "americans", "u.s.",
    ),
    "politics": (
        "election", "elections", "president", "presidential", "parliament", "prime minister",
        "vote", "voters", "ballot", "bill", "legislation", "lawmakers", "court ruling", "campaign",
        "policy", "democrat", "democrats", "republican", "republicans", "trump", "biden", "harris",
        "minister", "coalition", "opposition", "impeachment", "cabinet", "referendum", "lobbying",
        "gerrymandering", "electoral",
    ),
    "business": (
        "company", "companies", "market", "markets", "stocks", "shares", "earnings", "revenue",
        "profit", "ceo", "investors", "economy", "economic", "inflation", "gdp", "trade", "merger",
        "acquisition", "ipo", "layoffs", "tariff", "tariffs", "bank", "banks", "central bank",
        "interest rates", "wall street", "supply chain", "manufacturing", "retail sales",
        "unemployment", "recession", "startup funding", "valuation", "quarterly results",
    ),
    "money": (
        "personal finance", "savings", "credit score", "debt", "student loans", "rent", "salary",
        "budgeting", "budget", "investing", "retirement", "taxes", "mortgage", "prices",
        "cost of living", "paycheck", "side hustle", "crypto", "bitcoin", "pension", "insurance",
        "frugal", "money",
    ),
    "tech": (
        "artificial intelligence", " ai ", "chatgpt", "openai", "algorithm", "app", "apps", "software",
        "hardware", "chip", "chips", "semiconductor", "iphone", "android", "google", "apple",
        "microsoft", "meta", "amazon", "tiktok", "cybersecurity", "hack", "hacked", "data breach",
        "privacy", "robot", "robotics", "social media", "platform", "cloud", "data center", "gadget",
        "electric vehicle", "self-driving", "quantum computing", "silicon valley", "developer",
    ),
    "science": (
        "study", "studies", "researchers", "scientists", "research", "journal", "peer-reviewed",
        "experiment", "physics", "biology", "chemistry", "discovery", "dna", "gene", "genome",
        "fossil", "species", "evolution", "neuroscience", "particle", "molecule", "vaccine trial",
        "archeology", "archaeology", "anthropology", "breakthrough",
    ),
    "space": (
        "nasa", "spacex", "rocket", "orbit", "orbital", "mars", "moon", "lunar", "telescope",
        "satellite", "asteroid", "astronaut", "galaxy", "galaxies", "black hole", "exoplanet",
        "space station", "launch pad", "starship", "jwst", "james webb", "comet", "solar system",
        "spaceflight", "space",
    ),
    "health": (
        "health", "disease", "virus", "vaccine", "patients", "hospital", "hospitals", "doctors",
        "cdc", "mental health", "cancer", "diabetes", "obesity", "outbreak", "symptoms", "medicine",
        "drug", "fda", "clinical trial", "therapy", "depression", "anxiety", "sleep", "nutrition",
        "public health", "healthcare", "medicaid", "who", "epidemic", "pandemic", "measles",
    ),
    "climate": (
        "climate", "emissions", "carbon", "global warming", "wildfire", "wildfires", "drought",
        "flood", "floods", "hurricane", "typhoon", "renewable", "solar power", "wind farm",
        "fossil fuel", "fossil fuels", "cop28", "cop29", "cop30", "ipcc", "heatwave", "heat wave",
        "sea level", "biodiversity", "deforestation", "methane", "net zero", "green energy",
        "extreme weather", "glacier",
    ),
    "motorsport": (
        "f1", "formula 1", "formula one", "grand prix", "verstappen", "hamilton", "norris",
        "leclerc", "russell", "piastri", "ferrari", "mercedes", "red bull racing", "mclaren",
        "aston martin", "alpine", "williams", "haas", "sauber", "motogp", "indycar", "nascar",
        "rally", "rallying", "le mans", "wec", "formula e", "pole position", "podium",
        "constructors", "drs", "sprint race", "qualifying", "race weekend", "paddock",
    ),
    "sports": (
        "game", "games", "match", "matches", "team", "teams", "coach", "league", "season",
        "playoffs", "playoff", "touchdown", "goal", "goals", "inning", "tournament", "championship",
        "olympics", "olympic", "transfer", "striker", "quarterback", "nba", "nfl", "mlb", "nhl",
        "wnba", "mls", "cricket", "football", "soccer", "tennis", "medal",
        "world cup", "super bowl", "stanley cup", "fixture", "squad", "halftime", "final score",
        "hat-trick", "wicket", "slam dunk", "esports",
    ),
    "culture": (
        "art", "arts", "museum", "museums", "book", "books", "author", "novel", "poetry", "poet",
        "exhibition", "fashion", "design", "architecture", "theatre", "theater", "broadway",
        "sculpture", "gallery", "literary", "publishing", "cultural", "heritage", "photography",
    ),
    "entertainment": (
        "film", "films", "movie", "movies", "actor", "actress", "box office", "netflix", "hulu",
        "series", "sitcom", "tv show", "television", "oscars", "academy awards", "emmy", "grammy",
        "celebrity", "trailer", "disney", "marvel", "streaming", "hollywood", "documentary",
        "cast", "season finale", "reality show",
    ),
    "music": (
        "album", "albums", "song", "songs", "musician", "singer", "band", "tour", "concert",
        "spotify", "rapper", "hip-hop", "hip hop", "pop star", "single release", "playlist",
        "record label", "festival lineup", "billboard", "vinyl", "orchestra", "dj",
    ),
    "gaming": (
        "video game", "video games", "playstation", "xbox", "nintendo", "steam", "esports",
        "rpg", "dlc", "console", "fortnite", "minecraft", "roblox", "game pass", "title update",
        "speedrun", "gameplay", "fps", "indie game", "game studio", "publisher", "game awards",
    ),
    "education": (
        "school", "schools", "students", "student", "teachers", "teacher", "university",
        "universities", "college", "exam", "exams", "curriculum", "admissions", "tuition",
        "campus", "fafsa", "scholarship", "scholarships", "classroom", "homework", "graduation",
        "k-12", "higher education", "academic", "semester", "principal", "district",
    ),
    "food": (
        "recipe", "recipes", "restaurant", "restaurants", "chef", "chefs", "dish", "cuisine",
        "ingredients", "baking", "menu", "food", "cooking", "flavor", "michelin", "grocery",
        "supermarket", "coffee shop", "vegan", "barbecue", "dessert",
    ),
    "travel": (
        "travel", "travellers", "travelers", "destination", "airline", "airlines", "hotel",
        "hotels", "tourism", "flight", "flights", "visa", "airport", "trip", "itinerary",
        "backpacking", "resort", "cruise", "passport", "layover",
    ),
    "opinion": (
        "opinion", "editorial", "column", "commentary", "analysis:", "we should", "i think",
        "the case for", "the case against", "letter to the editor", "perspective",
    ),
}

_COMPILED: dict[str, list[re.Pattern[str]]] = {
    topic: [re.compile(r"(?<![\w-])" + re.escape(term.strip()) + r"(?![\w-])", re.I) for term in terms]
    for topic, terms in LEXICON.items()
}

_OPINION_HINTS = re.compile(r"^(opinion|editorial|column|commentary|analysis|perspective|essay)\b", re.I)

_GRAPHIC = re.compile(
    r"\b(killed|dead|death toll|corpse|massacre|beheaded|shooting|stabbed|assault|rape|murder|suicide|abuse)\b",
    re.I,
)


def score_topics(title: str, summary: str = "", feed_topic: str | None = None) -> dict[str, float]:
    text = f"{title} {summary}"
    scores: dict[str, float] = {slug: 0.0 for slug in TOPIC_SLUGS}
    for topic, patterns in _COMPILED.items():
        score = 0.0
        for pattern in patterns:
            title_hits = len(pattern.findall(title))
            if title_hits:
                score += title_hits * 3.0
            body_hits = len(pattern.findall(summary))
            if body_hits:
                score += min(body_hits, 6) * 1.0
        scores[topic] = score
    if feed_topic in scores:
        scores[feed_topic] += 2.2
    # Opinion is only a topic when the headline says so.
    if _OPINION_HINTS.match(title.strip()):
        scores["opinion"] += 5.0
    else:
        scores["opinion"] *= 0.25
    return scores


def classify(title: str, summary: str = "", feed_topic: str | None = None, source_topics: tuple[str, ...] = ()) -> tuple[str, list[str]]:
    scores = score_topics(title, summary, feed_topic)
    for topic in source_topics:
        if topic in scores:
            scores[topic] += 0.5
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    primary = ranked[0][0] if ranked and ranked[0][1] > 0 else (feed_topic or "world")
    if primary not in TOPIC_SLUGS:
        primary = "world"
    topics = [primary]
    for topic, score in ranked[1:]:
        if score >= max(6.0, scores[primary] * 0.45) and len(topics) < 4:
            topics.append(topic)
    return primary, topics


def is_graphic(text: str) -> bool:
    return bool(_GRAPHIC.search(text or ""))


_ENTITY_STOP = {
    "The", "This", "That", "These", "Those", "It", "He", "She", "They", "We", "You", "I",
    "But", "And", "For", "With", "From", "After", "Before", "When", "While", "How", "Why",
    "What", "Who", "New", "One", "Two", "Three", "First", "Last", "Next", "More", "Most",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December", "US", "UK", "EU", "UN", "AI", "CEO", "The", "In",
    "On", "At", "As", "By", "Of", "To", "A", "An", "Its", "His", "Her", "Their", "Our",
}


def entities(text: str, limit: int = 12) -> list[str]:
    """Cheap proper-noun extraction for "follow this" suggestions."""
    if not text:
        return []
    counts: Counter[str] = Counter()
    for match in re.finditer(r"\b([A-Z][a-z’'\-]{2,}(?:\s+(?:of|the|and|de|van|von)?\s*[A-Z][a-z’'\-]{2,}){0,2})", text):
        name = match.group(1).strip()
        first = name.split()[0]
        if first in _ENTITY_STOP or name in _ENTITY_STOP:
            continue
        if len(name) < 3:
            continue
        counts[name] += 1
    return [name for name, count in counts.most_common(limit) if count >= 1]


def has_deep_coverage(text: str) -> bool:
    return len((text or "").split()) > 350
