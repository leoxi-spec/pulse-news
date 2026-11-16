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
        # series and event names are unambiguous
        "formula 1", "formula one", "f1", "grand prix", "motogp", "indycar", "nascar",
        "rally", "rallying", "wrc", "le mans", "wec", "formula e", "supercars",
        "pole position", "sprint race", "pit lane", "race weekend", "chequered flag",
        "constructors", "drivers championship", "world endurance",
        # named drivers avoid the "Russell Brand" / "qualifying offer" false positives
        "max verstappen", "lewis hamilton", "charles leclerc", "lando norris",
        "oscar piastri", "george russell", "carlos sainz", "fernando alonso",
        "sergio perez", "kimi antonelli", "daniel ricciardo", "valtteri bottas",
        # teams, with the motorsport context spelled out
        "red bull racing", "mclaren f1", "scuderia ferrari", "ferrari f1",
        "mercedes-amg", "aston martin f1", "williams racing", "alpine f1", "haas f1",
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

# Formula 1 is intentionally strict. A generic motorsport feed can carry
# MotoGP, cycling, sailing or rally copy; "F1" must only show open-wheel
# Formula 1 stories. The term list is therefore made of F1-specific markers,
# not the broad motorsport words above.
_F1_MARKERS = re.compile(
    r"(?<![\w-])(?:"
    r"formula\s*(?:1|one)|f1|fia|"
    r"max\s+verstappen|lewis\s+hamilton|charles\s+leclerc|lando\s+norris|"
    r"oscar\s+piastri|george\s+russell|carlos\s+sainz|fernando\s+alonso|"
    r"sergio\s+perez|kimi\s+antonelli|daniel\s+ricciardo|valtteri\s+bottas|"
    r"red\s+bull\s+racing|mclaren\s+f1|scuderia\s+ferrari|ferrari\s+f1|"
    r"mercedes-amg|aston\s+martin\s+f1|williams\s+racing|alpine\s+f1|haas\s+f1|"
    r"sauber|racing\s+bulls|alphatauri|cadillac\s+f1|audi\s+f1|"
    r"constructors(?:'|\s)?\s+championship|drivers(?:'|\s)?\s+championship|"
    r"pole\s+position|pit\s+lane|sprint\s+race|chequered\s+flag|"
    r"race\s+weekend|paddock|formula\s+one\s+world|f1\s+academy"
    r")(?![\w-])",
    re.I,
)
_NON_F1_MARKERS = re.compile(
    r"(?<![\w-])(?:motogp|moto2|moto3|indycar|nascar|rally|rallying|wrc|"
    r"le\s+mans|wec|formula\s+e|supercars|btcc|dtm|touring\s+cars?|"
    r"cycling|tour\s+de\s+france|giro|vuelta|sailing|america'?s\s+cup|"
    r"horse\s+racing|kentucky\s+derby|grand\s+national|"
    r"figure\s+skating|isu|skate\s+america|skate\s+canada|ice\s+dance|"
    r"gymnastics|show\s+jumping|dressage|swimming|athletics|marathon|"
    r"drag\s+racing|rallycross|speedway)(?![\w-])",
    re.I,
)


_F1_QUERY = re.compile(r"(?<![\w-])(?:f1|formula\s*(?:1|one)|grand\s*prix|formula\s*one)(?![\w-])", re.I)


def wants_f1(query: str | None) -> bool:
    """Whether a search should be constrained to the Formula 1 lane."""
    return bool(query and _F1_QUERY.search(query))


def is_f1(title: str, summary: str = "") -> bool:
    """True only for Formula 1 stories, never generic motorsport.

    The title decides the lane. A MotoGP or IndyCar headline is excluded even
    if the body happens to mention F1 for comparison; an F1 headline is kept
    even when it mentions another series.
    """
    title = title or ""
    summary = summary or ""
    if not f"{title} {summary}".strip():
        return False
    # Non-F1 series in the headline means this is not an F1 story.
    if _NON_F1_MARKERS.search(title):
        return False
    if _F1_MARKERS.search(title):
        return True
    # A non-F1 series only in the preview is still not an F1 story.
    if _NON_F1_MARKERS.search(summary):
        return False
    if _F1_MARKERS.search(summary):
        return True
    # "Las Vegas Grand Prix" without an F1 word is usually still F1, but only
    # when no other series marker is present.
    return bool(re.search(r"(?<![\w-])grand\s*prix(?![\w-])", f"{title} {summary}", re.I))


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
    f1_story = is_f1(title, summary)
    # A motorsport hint is not a licence to file MotoGP, cycling or sailing
    # under Formula 1. Those stories remain sports; F1 is a strict lane.
    effective_feed_topic = "sports" if feed_topic == "motorsport" and not f1_story else feed_topic
    scores = score_topics(title, summary, effective_feed_topic)
    for topic in source_topics:
        if topic == "motorsport" and not f1_story:
            topic = "sports"
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
