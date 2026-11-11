"""Daily engagement: the small, fun things that make the app worth opening.

Everything here rotates by date so the front page has something new each day:
a word, a quote, a poll, a debate, a would-you-rather, an archive "on this
day", a news-literacy quiz and a four-part daily challenge.  All of it is
honest: the quiz is built from real archived headlines, the history card comes
from the real archive, and the challenge is measured from the profile's own
events rather than invented.
"""
from __future__ import annotations

import json
import random
import re
import time
from collections import Counter
from datetime import date
from urllib.parse import quote

from .db import db
from .timeutil import day_key, now, relative, start_of_day

# ------------------------------------------------------------------ content
# Kept short and readable on a phone.  Rotated by ordinal day so every day of
# the year gets a different combination without any scheduled job.
WORDS = (
    {"word": "serendipity", "say": "ser-ən-DIP-ə-tee", "pos": "noun",
     "meaning": "Finding something good without looking for it.",
     "example": "A wrong turn led to a serendipity: the best bookshop in the city."},
    {"word": "corroborate", "say": "kə-ROB-ə-rayt", "pos": "verb",
     "meaning": "To support a claim with more evidence.",
     "example": "Two independent outlets corroborated the leaked document."},
    {"word": "nuance", "say": "NYOO-ahns", "pos": "noun",
     "meaning": "A small but important difference in meaning or tone.",
     "example": "The headline flattened all the nuance out of the report."},
    {"word": "volatile", "say": "VOL-ə-tyle", "pos": "adjective",
     "meaning": "Likely to change quickly and unpredictably.",
     "example": "Crypto prices stayed volatile all week."},
    {"word": "paradigm", "say": "PAIR-ə-dyme", "pos": "noun",
     "meaning": "A typical model or pattern of thinking.",
     "example": "The discovery shifted the paradigm in climate science."},
    {"word": "mitigate", "say": "MIT-ə-gayt", "pos": "verb",
     "meaning": "To make something less severe.",
     "example": "The city planted trees to mitigate the heat."},
    {"word": "ubiquitous", "say": "yoo-BIK-wə-təs", "pos": "adjective",
     "meaning": "Seeming to be everywhere at once.",
     "example": "Smartphones are ubiquitous in classrooms now."},
    {"word": "empirical", "say": "em-PEER-ə-kəl", "pos": "adjective",
     "meaning": "Based on observation or experiment, not just theory.",
     "example": "The claim needs empirical evidence, not another opinion."},
    {"word": "rhetoric", "say": "RET-ər-ik", "pos": "noun",
     "meaning": "Language designed to persuade, sometimes without substance.",
     "example": "The speech was heavy on rhetoric and light on policy."},
    {"word": "consensus", "say": "kən-SEN-səs", "pos": "noun",
     "meaning": "General agreement among a group.",
     "example": "There is a scientific consensus that the planet is warming."},
    {"word": "catalyst", "say": "KAT-ə-list", "pos": "noun",
     "meaning": "Something that speeds up a change or reaction.",
     "example": "The protest became a catalyst for new laws."},
    {"word": "skeptic", "say": "SKEP-tik", "pos": "noun",
     "meaning": "Someone who questions whether a claim is true.",
     "example": "Be a skeptic: check the numbers before sharing."},
    {"word": "impartial", "say": "im-PAR-shəl", "pos": "adjective",
     "meaning": "Fair and not favouring one side.",
     "example": "A good referee stays impartial."},
    {"word": "verify", "say": "VAIR-ə-fye", "pos": "verb",
     "meaning": "To check that something is true.",
     "example": "Reverse-image search is a quick way to verify a photo."},
    {"word": "algorithm", "say": "AL-gə-rith-əm", "pos": "noun",
     "meaning": "A set of rules a computer follows to make a decision.",
     "example": "The feed's algorithm decides which stories you see first."},
    {"word": "misinformation", "say": "mis-in-fər-MAY-shən", "pos": "noun",
     "meaning": "False information spread without necessarily meaning harm.",
     "example": "Misinformation can travel faster than corrections."},
    {"word": "transparency", "say": "trans-PAIR-ən-see", "pos": "noun",
     "meaning": "Being open about how decisions are made.",
     "example": "Voters asked for more transparency about the budget."},
    {"word": "accountability", "say": "ə-kown-tə-BIL-ə-tee", "pos": "noun",
     "meaning": "Being responsible for your actions and answering for them.",
     "example": "The report called for accountability at the agency."},
    {"word": "diplomacy", "say": "də-PLOH-mə-see", "pos": "noun",
     "meaning": "Managing relationships between countries through talk.",
     "example": "Quiet diplomacy secured the ceasefire."},
    {"word": "inflation", "say": "in-FLAY-shən", "pos": "noun",
     "meaning": "A general rise in prices over time.",
     "example": "Inflation made school supplies more expensive."},
    {"word": "coalition", "say": "koh-ə-LISH-ən", "pos": "noun",
     "meaning": "A group of parties or people working together temporarily.",
     "example": "The coalition needed three parties to govern."},
    {"word": "sovereignty", "say": "SOV-rən-tee", "pos": "noun",
     "meaning": "A country's right to govern itself.",
     "example": "The treaty was framed as a defence of sovereignty."},
    {"word": "infrastructure", "say": "IN-frə-struk-chər", "pos": "noun",
     "meaning": "The basic systems a place needs to function.",
     "example": "The flood exposed weaknesses in the infrastructure."},
    {"word": "biodiversity", "say": "bye-oh-dye-VER-sə-tee", "pos": "noun",
     "meaning": "The variety of living things in a place.",
     "example": "The reef is a hotspot for biodiversity."},
    {"word": "entrepreneur", "say": "ahn-trə-prə-NUR", "pos": "noun",
     "meaning": "Someone who starts a business and takes a risk.",
     "example": "The teen entrepreneur turned a school project into a company."},
    {"word": "empathy", "say": "EM-pə-thee", "pos": "noun",
     "meaning": "Understanding how someone else feels.",
     "example": "The story was reported with empathy, not pity."},
    {"word": "stigma", "say": "STIG-mə", "pos": "noun",
     "meaning": "A mark of shame or disapproval attached to something.",
     "example": "Athletes are working to remove the stigma around mental health."},
    {"word": "advocate", "say": "AD-və-kayt", "pos": "verb",
     "meaning": "To publicly support a cause or idea.",
     "example": "She advocates for free public transport for students."},
    {"word": "tangible", "say": "TAN-jə-bəl", "pos": "adjective",
     "meaning": "Real enough to be touched or clearly measured.",
     "example": "The talks produced no tangible agreement."},
    {"word": "ambiguous", "say": "am-BIG-yoo-əs", "pos": "adjective",
     "meaning": "Open to more than one interpretation.",
     "example": "The rule was ambiguous, so everyone interpreted it differently."},
    {"word": "precedent", "say": "PRES-ə-dənt", "pos": "noun",
     "meaning": "An earlier case used as an example for later ones.",
     "example": "The ruling set a precedent for future cases."},
    {"word": "scrutiny", "say": "SKROO-tə-nee", "pos": "noun",
     "meaning": "Close and critical examination.",
     "example": "The plan came under intense public scrutiny."},
    {"word": "resilience", "say": "rə-ZIL-yəns", "pos": "noun",
     "meaning": "The ability to recover after a setback.",
     "example": "The team's resilience showed in the second half."},
    {"word": "anecdote", "say": "AN-ik-doht", "pos": "noun",
     "meaning": "A short personal story, not proof of a trend.",
     "example": "One anecdote is not data, even if it is a great story."},
    {"word": "credible", "say": "KRED-ə-bəl", "pos": "adjective",
     "meaning": "Believable and trustworthy.",
     "example": "A credible source names its evidence."},
    {"word": "consolidate", "say": "kən-SOL-ə-dayt", "pos": "verb",
     "meaning": "To combine things into one stronger whole.",
     "example": "The two smaller parties consolidated before the election."},
)

QUOTES = (
    {"text": "Freedom of the press is not just important to democracy, it is democracy.", "by": "Walter Cronkite"},
    {"text": "Journalism is literature in a hurry.", "by": "Matthew Arnold"},
    {"text": "The more that you read, the more things you will know.", "by": "Dr. Seuss"},
    {"text": "Reading is to the mind what exercise is to the body.", "by": "Joseph Addison"},
    {"text": "Curiosity is the wick in the candle of learning.", "by": "William Arthur Ward"},
    {"text": "Education is the most powerful weapon which you can use to change the world.", "by": "Nelson Mandela"},
    {"text": "A people without the knowledge of their past history is like a tree without roots.", "by": "Marcus Garvey"},
    {"text": "The beautiful thing about learning is that no one can take it away from you.", "by": "B.B. King"},
    {"text": "If you are not willing to be wrong, you will never be right about anything new.", "by": "Anonymous"},
    {"text": "The first draft of history is written by reporters.", "by": "Anonymous"},
    {"text": "Question everything. Learn something. Answer nothing.", "by": "Euripides"},
    {"text": "The important thing is not to stop questioning.", "by": "Albert Einstein"},
    {"text": "An investment in knowledge pays the best interest.", "by": "Benjamin Franklin"},
    {"text": "Nothing in life is to be feared, it is only to be understood.", "by": "Marie Curie"},
    {"text": "Stay curious, stay kind, and check your sources.", "by": "Pulse"},
)

POLLS = (
    {"question": "Where do you usually get your news?", "options": ["Social feeds", "YouTube", "News apps", "Friends + family"]},
    {"question": "How long is your ideal news read?", "options": ["1 minute", "3 minutes", "5 minutes", "10+ minutes"]},
    {"question": "Do you fact-check a headline before sharing it?", "options": ["Always", "Sometimes", "Rarely", "Never"]},
    {"question": "What makes a story worth your time?", "options": ["It affects me", "It's surprising", "It's funny", "It explains why"]},
    {"question": "Should phones be banned during class?", "options": ["Yes, fully", "Only during lessons", "Only during tests", "No"]},
    {"question": "Is using AI for homework cheating?", "options": ["Always", "Usually", "Depends how", "Never"]},
    {"question": "What's your go-to study method?", "options": ["Flashcards", "Rewriting notes", "Practice questions", "Explaining it out loud"]},
    {"question": "Which would you rather have at school?", "options": ["Free period", "Free lunch", "Later start", "Shorter week"]},
    {"question": "Early bird or night owl?", "options": ["Early bird", "Night owl", "Neither", "Both, somehow"]},
    {"question": "Would you take a gap year?", "options": ["Definitely", "Maybe", "Probably not", "No"]},
    {"question": "Which school skill matters most in 2030?", "options": ["Coding", "Writing", "Critical thinking", "Working with people"]},
    {"question": "Do you read the comments?", "options": ["Always", "Sometimes", "Only the top ones", "Never"]},
    {"question": "What's the biggest issue for your generation?", "options": ["Climate", "Cost of living", "AI + jobs", "Mental health"]},
    {"question": "How do you feel about school uniforms?", "options": ["Keep them", "Loosen them", "Drop them", "No opinion"]},
    {"question": "Which topic should Pulse cover more?", "options": ["Science", "Sport", "Culture", "Money + life"]},
    {"question": "What's your ideal weekend?", "options": ["Out with friends", "Gaming", "Sport", "Nothing planned"]},
)

DEBATES = (
    {"motion": "AI should be allowed to grade homework.",
     "for": "It gives instant feedback and frees teachers for deeper work.",
     "against": "It can be biased, wrong, and it hides how the grade was decided."},
    {"motion": "Schools should start later than 8:30.",
     "for": "Teen sleep cycles shift late; later starts improve attendance and grades.",
     "against": "Families and buses are built around early starts, and sport runs after school."},
    {"motion": "Social media companies should be regulated like tobacco companies.",
     "for": "Both sell addictive products with harms that are hard to see individually.",
     "against": "Social media is also speech and community; tobacco has no upside."},
    {"motion": "16-year-olds should be able to vote.",
     "for": "They pay taxes, work, and inherit the long-term consequences.",
     "against": "Most civic and legal responsibilities still start at 18."},
    {"motion": "Homework should be optional if you pass the test.",
     "for": "Tests measure the outcome; busywork shouldn't be punishment.",
     "against": "Practice builds the habit and the depth a single test can't capture."},
    {"motion": "Schools should teach personal finance before calculus.",
     "for": "Every student will meet rent, tax and interest; not every student needs calculus.",
     "against": "Calculus trains abstract reasoning that finance alone doesn't."},
    {"motion": "Anonymous accounts should be banned online.",
     "for": "Anonymity shelters harassment and disinformation.",
     "against": "It also protects whistleblowers, victims and political speech."},
    {"motion": "Space exploration is worth the cost.",
     "for": "It produces science, technology and a long-term future off one planet.",
     "against": "The same money could fix problems on this one right now."},
    {"motion": "Public transport should be free for students.",
     "for": "It removes a real barrier to school and work.",
     "against": "Someone still pays; free for all can mean worse service for all."},
    {"motion": "News outlets should show graphic images.",
     "for": "Images can convey the truth that words sanitise.",
     "against": "Shock isn't understanding, and it can harm viewers."},
    {"motion": "Athletes should be paid like entertainers.",
     "for": "They generate the same global audiences and revenue.",
     "against": "Public money and amateur pathways are a different kind of job."},
    {"motion": "Everyone should learn to code.",
     "for": "Software shapes everyday life; reading it is a basic literacy.",
     "against": "Not everyone needs to build software; many need other skills more."},
)

WYR = (
    ("Only ever read headlines", "Only ever read long reads"),
    ("Know the news a day early", "Never be wrong about a fact"),
    ("Interview your hero", "Have your hero read your essay"),
    ("A perfect memory", "Perfect note-taking"),
    ("No ads ever", "No paywalls ever"),
    ("Visit the past", "Visit the future"),
    ("Learn every language", "Play every instrument"),
    ("A robot does your homework", "A robot does your chores"),
    ("Infinite scroll", "Infinite attention span"),
    ("Front row at the World Cup", "Backstage at the Grammys"),
    ("Only good news", "Only breaking news"),
    ("A week offline", "A week without music"),
)

_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "will", "have", "has", "are", "was",
    "were", "but", "not", "you", "your", "its", "his", "her", "their", "they", "them", "who",
    "what", "when", "where", "why", "how", "after", "before", "over", "under", "into", "than",
    "then", "more", "most", "can", "could", "would", "should", "may", "might", "says", "said",
    "new", "now", "one", "two", "three", "first", "last", "next", "about", "amid", "as", "at",
    "by", "in", "of", "on", "to", "up", "out", "off", "is", "it", "be", "or", "an", "a",
}


def _pick(seq: tuple, offset: int = 0):
    return seq[(date.today().toordinal() + offset) % len(seq)]


def word_of_day() -> dict:
    word = dict(_pick(WORDS))
    word["date"] = day_key()
    return word


def quote_of_day() -> dict:
    return dict(_pick(QUOTES))


def poll_of_day() -> dict:
    poll = dict(_pick(POLLS))
    poll["id"] = f"poll-{date.today().toordinal() % len(POLLS)}"
    return poll


def debate_of_day() -> dict:
    debate = dict(_pick(DEBATES))
    debate["id"] = f"debate-{date.today().toordinal() % len(DEBATES)}"
    return debate


def wyr_of_day() -> dict:
    a, b = _pick(WYR)
    return {"id": f"wyr-{date.today().toordinal() % len(WYR)}", "a": a, "b": b}


def _article_brief(row) -> dict:
    published = row["published_at"] or row["first_seen_at"]
    summary = re.sub(r"<[^>]+>", " ", row["summary"] or "")
    summary = re.sub(r"\s+", " ", summary).strip()
    return {
        "id": row["id"],
        "title": row["title"],
        "preview": summary[:240],
        "image": "/api/img?u=" + quote(row["image_url"], safe="") if row["image_url"] else None,
        "topic": row["primary_topic"],
        "topic_label": (row["primary_topic"] or "world").replace("-", " ").title(),
        "source": {"name": row["source_name"]},
        "story": {"source_count": int(row["source_count"] or 1)} if "source_count" in row.keys() else {"source_count": 1},
        "published_relative": relative(published),
        "published_at": published,
        "reading_minutes": row["reading_minutes"] or 1,
    }


def history_today(limit: int = 2) -> tuple[list[dict], str]:
    """Real archive stories from this calendar day in earlier years."""
    today = date.today()
    stamp = today.strftime("%m-%d")
    rows = db.query(
        """SELECT a.id, a.title, a.summary, a.image_url, a.primary_topic, a.reading_minutes,
                  a.published_at, a.first_seen_at, s.name AS source_name
           FROM articles a JOIN sources s ON s.id = a.source_id
           WHERE strftime('%m-%d', COALESCE(a.published_at, a.first_seen_at)) = ?
             AND CAST(strftime('%Y', COALESCE(a.published_at, a.first_seen_at)) AS INTEGER) < ?
           ORDER BY a.id DESC LIMIT ?""",
        (stamp, today.year, limit),
    )
    label = "On this day"
    if not rows:
        # Fresh installs have no earlier years yet: show the oldest things in
        # the archive instead, clearly labelled by their real date.
        label = "From the archive"
        # No same-day history on a fresh install: show real stories from about
        # a year ago, preferring ones that actually have a picture, instead of
        # the oldest newsletter boilerplate in the database.
        rows = db.query(
            """SELECT a.id, a.title, a.summary, a.image_url, a.primary_topic, a.reading_minutes,
                      a.published_at, a.first_seen_at, s.name AS source_name
               FROM articles a
               JOIN sources s ON s.id = a.source_id
               JOIN stories st ON st.id = a.story_id
               WHERE a.image_url IS NOT NULL AND a.image_url <> ''
                 AND COALESCE(st.source_count, 1) >= 3
                 AND a.title NOT LIKE '%recipe%' AND a.title NOT LIKE '%horoscope%'
                 AND a.title NOT LIKE '%air fryer%' AND a.title NOT LIKE '%deal%'
                 AND COALESCE(a.published_at, a.first_seen_at)
                     BETWEEN datetime('now', '-400 days') AND datetime('now', '-200 days')
               ORDER BY COALESCE(st.source_count, 0) DESC, a.id DESC LIMIT ?""",
            (limit,),
        )
        if not rows:
            rows = db.query(
                """SELECT a.id, a.title, a.summary, a.image_url, a.primary_topic, a.reading_minutes,
                          a.published_at, a.first_seen_at, s.name AS source_name
                   FROM articles a JOIN sources s ON s.id = a.source_id
                   WHERE a.image_url IS NOT NULL AND a.image_url <> ''
                   ORDER BY a.id DESC LIMIT ?""",
                (limit,),
            )
    return [_article_brief(row) for row in rows], label


_trend_cache: tuple[float, list[dict]] = (0.0, [])


def trending(limit: int = 8) -> list[dict]:
    global _trend_cache
    if time.time() - _trend_cache[0] < 900:
        return _trend_cache[1]
    rows = db.query(
        """SELECT title FROM articles
           WHERE COALESCE(published_at, first_seen_at) >= datetime('now', '-1 day')
             AND lang = 'en'
           ORDER BY id DESC LIMIT 1400"""
    )
    # Proper nouns make a far better ticker than single words: "Taylor Swift"
    # instead of fragments like "para" or "visita".
    counter: Counter[str] = Counter()
    for row in rows:
        title = row["title"] or ""
        for match in re.findall(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b", title):
            phrase = match.strip()
            low = phrase.lower()
            if low in _STOP:
                continue
            words = phrase.split()
            if len(words) == 1 and len(phrase) < 5:
                continue
            counter[phrase] += 1
    data = [{"term": term, "count": count} for term, count in counter.most_common(limit * 3)
            if count >= 3][:limit]
    _trend_cache = (time.time(), data)
    return data


def quiz(limit: int = 3) -> dict:
    """News-literacy quiz: match a real archived headline to its outlet."""
    today_seed = date.today().toordinal()
    rng = random.Random(today_seed)
    # Prefer established English-language outlets, grouped by country so the
    # distractors feel plausible rather than random.
    source_rows = db.query(
        """SELECT s.name, s.country, COUNT(a.id) AS n
           FROM sources s JOIN articles a ON a.source_id = s.id
           GROUP BY s.id HAVING n >= 10 ORDER BY n DESC LIMIT 120"""
    )
    by_country: dict[str, list[str]] = {}
    for row in source_rows:
        by_country.setdefault(row["country"] or "", []).append(row["name"])
    names = [row["name"] for row in source_rows]
    rows = db.query(
        """SELECT a.id, a.title, s.name AS source_name, s.country AS source_country
           FROM articles a JOIN sources s ON s.id = a.source_id
           WHERE COALESCE(a.published_at, a.first_seen_at) >= datetime('now', '-3 days')
             AND a.lang = 'en'
             AND length(a.title) BETWEEN 28 AND 130
           ORDER BY a.id DESC LIMIT 400"""
    )
    # The archive is multilingual; keep the quiz in English so headlines are
    # readable and the outlet choices are comparable.
    def english(title: str) -> bool:
        if re.search(r"[^\x00-\x7F]", title or ""):
            return False
        return not re.search(r"\b(el|la|los|las|de|del|y|en|con|para|por|una|un|le|les|des|du)\b",
                             (title or "").lower())

    rows = [row for row in rows if english(row["title"])]
    if len(names) < 5 or len(rows) < limit:
        return {"questions": []}
    picked = rng.sample(list(rows), min(limit, len(rows)))
    questions = []
    for row in picked:
        correct = row["source_name"]
        if correct not in names:
            names.append(correct)
        pool = by_country.get(row["source_country"] or "") or names
        pool = [n for n in pool if n != correct]
        if len(pool) < 3:
            pool = [n for n in names if n != correct]
        distractors = rng.sample(pool, min(3, len(pool)))
        options = distractors + [correct]
        rng.shuffle(options)
        questions.append({
            "article_id": row["id"],
            "headline": row["title"],
            "options": options,
            "answer": options.index(correct),
            "source": correct,
        })
    return {"questions": questions}


def challenge(profile_id: str | None) -> dict:
    profile_id = profile_id or ""
    reads = db.query_one(
        "SELECT read_count FROM daily_stats WHERE profile_id=? AND day=?",
        (profile_id, day_key(now())),
    )
    read_now = int(reads["read_count"]) if reads else 0
    since = start_of_day()

    def count(sql: str) -> int:
        row = db.query_one(sql, (profile_id, since))
        return int(row["n"]) if row else 0

    quizzes = count("SELECT COUNT(DISTINCT article_id) n FROM events WHERE profile_id=? AND kind='quiz_attempt' AND created_at>=?")
    saves = count("SELECT COUNT(*) n FROM events WHERE profile_id=? AND kind='save' AND created_at>=?")
    topics = count("SELECT COUNT(DISTINCT topic) n FROM events WHERE profile_id=? AND kind IN ('read','open') AND topic IS NOT NULL AND created_at>=?")
    target = 2
    try:
        row = db.query_one("SELECT survey FROM profiles WHERE id=?", (profile_id,))
        age = int(json.loads(row["survey"] or "{}").get("age", 13)) if row else 13
        target = 2 if age <= 10 else 3 if age <= 14 else 4
    except (ValueError, TypeError, AttributeError):
        target = 2
    tasks = [
        {"id": "read", "icon": "📖", "label": f"Read {target} stories", "target": target, "now": min(target, read_now)},
        {"id": "quiz", "icon": "🧠", "label": "Try one quiz", "target": 1, "now": min(1, quizzes)},
        {"id": "save", "icon": "🔖", "label": "Save one for later", "target": 1, "now": min(1, saves)},
        {"id": "topics", "icon": "🧭", "label": "Read 2 different topics", "target": 2, "now": min(2, topics)},
    ]
    for task in tasks:
        task["done"] = task["now"] >= task["target"]
    done = sum(1 for task in tasks if task["done"])
    return {"tasks": tasks, "done": done, "total": len(tasks), "percent": round(done / len(tasks) * 100)}


_WIDGET_CACHE: tuple[float, dict] = (0.0, {})
_WIDGET_SELECT = """
    SELECT a.id, a.title, a.summary, a.image_url, a.primary_topic, a.reading_minutes,
           a.published_at, a.first_seen_at, s.name AS source_name,
           COALESCE(st.source_count, 1) AS source_count
    FROM articles a
    JOIN sources s ON s.id = a.source_id
    LEFT JOIN stories st ON st.id = a.story_id
"""


def _widget_rows(where: str, params: tuple = (), limit: int = 3, order: str = "COALESCE(a.published_at, a.first_seen_at) DESC"):
    rows = db.query(f"{_WIDGET_SELECT} WHERE {where} ORDER BY {order} LIMIT ?", (*params, limit))
    return [_article_brief(row) for row in rows]


def widget_stories() -> dict:
    """Small ready-made story sets for the customisable Today board."""
    global _WIDGET_CACHE
    if time.time() - _WIDGET_CACHE[0] < 300:
        return _WIDGET_CACHE[1]
    topics = [row["primary_topic"] for row in db.query(
        "SELECT primary_topic FROM articles GROUP BY primary_topic ORDER BY COUNT(*) DESC LIMIT 12"
    )]
    day = date.today().toordinal()
    spotlight_topic = topics[day % len(topics)] if topics else "world"
    source_row = db.query_one(
        "SELECT source_id FROM articles WHERE primary_topic = ? AND image_url IS NOT NULL "
        "ORDER BY COALESCE(published_at, first_seen_at) DESC LIMIT 1",
        (spotlight_topic,),
    )
    data = {
        "top": _widget_rows("a.content_state = 'extracted'", order="COALESCE(st.heat, 0) DESC, COALESCE(a.published_at, a.first_seen_at) DESC"),
        "quick": _widget_rows("a.reading_minutes <= 2 AND a.content_state = 'extracted'"),
        "long": _widget_rows("a.reading_minutes >= 6 AND a.content_state = 'extracted'", limit=2),
        "good": _widget_rows("a.primary_topic IN ('science','health','culture') AND a.is_breaking = 0"),
        "photo": _widget_rows("a.image_url IS NOT NULL AND a.image_url <> ''"),
        "sports": _widget_rows("a.primary_topic = 'sports'"),
        "motorsport": _widget_rows("a.primary_topic = 'motorsport'"),
        "science": _widget_rows("a.primary_topic = 'science'", limit=2),
        "culture": _widget_rows("a.primary_topic = 'culture'", limit=2),
        "most": _widget_rows("a.content_state = 'extracted'", order="COALESCE(st.source_count, 0) DESC, COALESCE(a.published_at, a.first_seen_at) DESC", limit=2),
        "next": _widget_rows("a.content_state = 'extracted'", order="RANDOM()", limit=2),
        "topic": {
            "topic": spotlight_topic,
            "topic_label": spotlight_topic.replace("-", " ").title(),
            "items": _widget_rows("a.primary_topic = ?", (spotlight_topic,), limit=2),
        },
        "source": {
            "name": (source_row["source_id"] if source_row else ""),
            "items": _widget_rows("a.source_id = ? AND a.image_url IS NOT NULL", (source_row["source_id"],), limit=2) if source_row else [],
        },
    }
    # A number worth pausing on, pulled from a real headline or summary.
    number = None
    for item in data["top"] + data["most"]:
        match = re.search(r"\b\d[\d,.]*\s?(?:%|percent|million|billion|trillion|bn|km|kg|years?|people|students?|seats?|votes?|goals?|points?)\b", f"{item['title']} {item['preview']}", re.I)
        if match:
            number = {"value": match.group(0), "context": item["title"], "item": item}
            break
    data["number"] = number
    _WIDGET_CACHE = (time.time(), data)
    return data


def payload(profile_id: str | None = None) -> dict:
    history, history_label = history_today()
    return {
        "date": day_key(),
        "word": word_of_day(),
        "quote": quote_of_day(),
        "poll": poll_of_day(),
        "debate": debate_of_day(),
        "wyr": wyr_of_day(),
        "trending": trending(),
        "history": history,
        "history_label": history_label,
        "quiz": quiz(),
        "challenge": challenge(profile_id),
        "widgets": widget_stories(),
    }
