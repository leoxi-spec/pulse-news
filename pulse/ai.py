"""Optional AI overviews, plus the always-available non-AI fallbacks.

Honesty rules baked into the product:

* An AI overview only exists when the user has configured a provider. The UI
  labels it "AI overview" and shows the model.
* The prompt forbids outside knowledge: the model may only restate what is in
  the supplied article text.
* If no provider is configured, the endpoint still returns an **extractive**
  overview (sentences taken from the article) and says so explicitly. Nothing
  is presented as AI when it is not.
* Quiz, jargon decoding and "explain simply" all have deterministic local
  implementations, so the student features work with zero API keys.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field

from . import htmltext
from .config import settings
from .db import db
from .httpclient import FetchError, HttpClient
from .logging_setup import get_logger
from .timeutil import iso, relative

log = get_logger("ai")

_client = HttpClient()


class AIError(Exception):
    pass


@dataclass
class RateLimiter:
    limit: int
    window: float = 3600.0
    _events: list[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            self._events = [e for e in self._events if now - e < self.window]
            if len(self._events) >= self.limit:
                return False
            self._events.append(now)
            return True


_limiter = RateLimiter(settings.ai_max_requests_per_hour)


def status() -> dict:
    return {
        "enabled": settings.ai_enabled,
        "provider": "openai-compatible" if settings.ai_enabled else None,
        "model": settings.ai_model if settings.ai_enabled else None,
        "base_url_host": _host(settings.ai_base_url) if settings.ai_base_url else None,
        "note": (
            "AI overviews use a provider you configure. Summaries are grounded in the article text only."
            if settings.ai_enabled
            else "No AI provider configured. Overviews use an on-device extractive summary and are labelled as such."
        ),
    }


def _host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        from urllib.parse import urlsplit

        return urlsplit(url).hostname
    except ValueError:
        return None


# --------------------------------------------------------------------- prompt
_SYSTEM = (
    "You are a careful news editor for high-school and university students. "
    "You write neutral, factual summaries for a curious reader who has not read the article. "
    "STRICT RULES: use ONLY information contained in the supplied article text; never add outside "
    "facts, numbers, names or speculation; do not give advice; do not take sides; if the text does "
    "not support an answer, say so plainly. Write in clear, plain English at roughly a 10th-grade "
    "reading level. Avoid hype words. Always return valid JSON and nothing else."
)

_SCHEMA_HINT = (
    "Return JSON with exactly these keys: "
    '{"summary": string (2-3 sentences, max 70 words), '
    '"key_points": array of 3 to 5 short strings (each one factual sentence fragment), '
    '"why_it_matters": string (1-2 sentences, only implications stated in the text), '
    '"terms": array of {"term": string, "definition": string} for at most 3 jargon words, '
    '"questions": array of 2 to 3 {"question": string, "answer": string} comprehension questions}'
)


def _article_context(article: dict, *, max_chars: int = 6000) -> str:
    body = article.get("content_text") or ""
    summary = article.get("summary") or ""
    text = body if len(body) > 400 else summary
    text = re.sub(r"\s+", " ", text)[:max_chars]
    published = article.get("published_at") or article.get("first_seen_at")
    return (
        f"TITLE: {article.get('title', '')}\n"
        f"OUTLET: {article.get('source_name', '')}\n"
        f"PUBLISHED: {published} ({relative(published) or 'unknown'})\n"
        f"URL: {article.get('url', '')}\n"
        f"ARTICLE TEXT:\n{text}\n"
        f"END OF ARTICLE TEXT"
    )


def _call_provider(user_prompt: str, *, max_tokens: int = 900) -> str:
    if not settings.ai_enabled:
        raise AIError("no_provider")
    if not _limiter.allow():
        raise AIError("rate_limited")
    base = settings.ai_base_url.rstrip("/")
    ollama_style = "11434" in base or base.endswith("/api") or "ollama" in base.lower()

    if ollama_style:
        url = base if base.endswith("/api/chat") else base + "/api/chat"
        payload = {
            "model": settings.ai_model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
        }
    else:
        url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        payload = {
            "model": settings.ai_model,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
        }
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_api_key}"

    body = json.dumps(payload).encode()
    import urllib.error
    import urllib.request

    from . import tls

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=settings.ai_timeout_seconds, context=tls.get_context()) as response:
            raw = response.read(400_000)
    except urllib.error.HTTPError as exc:
        detail = exc.read(400).decode("utf-8", "replace")
        raise AIError(f"provider HTTP {exc.code}: {detail[:160]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AIError(f"provider unreachable: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AIError("provider returned invalid JSON") from exc
    if ollama_style:
        return ((data.get("message") or {}).get("content") or "").strip()
    choices = data.get("choices") or []
    if not choices:
        raise AIError("provider returned no choices")
    return ((choices[0].get("message") or {}).get("content") or "").strip()


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise AIError("model did not return valid JSON")


# ------------------------------------------------------------------ extractive
def extractive_overview(article: dict) -> dict:
    text = htmltext.strip_boilerplate(article.get("content_text") or article.get("summary") or "")
    summary = htmltext.summarize(text, 3, 520) or (article.get("summary") or "")
    summary_tokens = set(htmltext._tokenise(summary))
    points = [
        point for point in htmltext.key_points(text, 8)
        if len(set(htmltext._tokenise(point)) & summary_tokens) / max(1, len(set(htmltext._tokenise(point)))) < 0.75
    ][:4]
    if not points and summary:
        points = [s for s in htmltext.sentences(summary)[:3]]
    why = _why_it_matters(article, text)
    return {
        "engine": "extractive",
        "provider": None,
        "model": None,
        "summary": summary,
        "key_points": points,
        "why_it_matters": why,
        "terms": [],
        "questions": [],
        "generated_at": iso(),
        "cached": False,
    }


def _why_it_matters(article: dict, text: str) -> str:
    candidates = []
    for sentence in htmltext.sentences(text):
        low = sentence.lower()
        if any(word in low for word in ("could", "expected", "means", "will affect", "impact", "if approved", "next step", "because")):
            candidates.append(sentence)
            if len(candidates) == 1:
                break
    if candidates:
        return candidates[0]
    outlet = article.get("source_name") or "the outlet"
    others = article.get("story_source_count") or 1
    coverage = f"{others} outlets are covering it" if others > 1 else "it is a single-outlet report so far"
    return f"Reported by {outlet}; {coverage}."


# ------------------------------------------------------------------------ main
def overview(article: dict, *, force: bool = False, kind: str = "overview") -> dict:
    """Return a grounded overview, AI when configured, extractive otherwise."""
    text = article.get("content_text") or article.get("summary") or ""
    if len(text.split()) < 25:
        base = extractive_overview(article)
        base["warning"] = "Not enough text to summarise yet — open the source to read the full piece."
        base["available"] = False
        return base

    fallback = extractive_overview(article)
    fallback["available"] = False
    if not settings.ai_enabled:
        fallback["warning"] = "AI overviews are off (no provider configured). This is an extractive summary built from the article's own sentences."
        return fallback

    key = _cache_key(article, kind)
    if not force:
        cached = _read_cache(key)
        if cached:
            cached["cached"] = True
            cached["available"] = True
            return cached

    prompt = (
        f"Summarise the article below for a student.\n\n{_article_context(article)}\n\n{_SCHEMA_HINT}"
    )
    try:
        raw = _call_provider(prompt, max_tokens=900)
        data = _parse_json(raw)
        result = {
            "engine": "ai",
            "provider": "openai-compatible",
            "model": settings.ai_model,
            "summary": str(data.get("summary") or fallback["summary"])[:800],
            "key_points": [str(p)[:300] for p in (data.get("key_points") or [])][:5] or fallback["key_points"],
            "why_it_matters": str(data.get("why_it_matters") or fallback["why_it_matters"])[:600],
            "terms": [
                {"term": str(t.get("term", ""))[:60], "definition": str(t.get("definition", ""))[:240]}
                for t in (data.get("terms") or []) if isinstance(t, dict)
            ][:3],
            "questions": [
                {"question": str(q.get("question", ""))[:240], "answer": str(q.get("answer", ""))[:400]}
                for q in (data.get("questions") or []) if isinstance(q, dict)
            ][:3],
            "generated_at": iso(),
            "cached": False,
            "available": True,
            "grounded_in": "article text" if article.get("content_text") else "feed summary",
        }
        _write_cache(key, kind, result)
        return result
    except AIError as exc:
        fallback["warning"] = (
            "The AI provider could not be reached just now, so this is the on-device extractive summary. "
            f"({exc})"
        )
        fallback["error"] = str(exc)
        return fallback


def explain(article: dict) -> dict:
    """Plain-language rewrite. AI when available, deterministic otherwise."""
    text = article.get("content_text") or article.get("summary") or ""
    fallback = {
        "engine": "extractive",
        "available": False,
        "text": htmltext.simplify(text, 6),
        "jargon": decode_jargon(text),
        "warning": "Simplified by shortening and re-ordering the article's own sentences.",
    }
    if not settings.ai_enabled or len(text.split()) < 40:
        return fallback
    key = _cache_key(article, "explain")
    cached = _read_cache(key)
    if cached:
        return cached
    prompt = (
        "Rewrite the article below for a 14-year-old who is smart but new to this topic. "
        "Keep every fact, name and number; do not add anything. 5 short sentences maximum. "
        'Return JSON: {"text": string, "jargon": [{"term": string, "definition": string}]}.\n\n'
        + _article_context(article, max_chars=5000)
    )
    try:
        data = _parse_json(_call_provider(prompt, max_tokens=600))
        result = {
            "engine": "ai",
            "available": True,
            "provider": "openai-compatible",
            "model": settings.ai_model,
            "text": str(data.get("text") or fallback["text"])[:1600],
            "jargon": [
                {"term": str(j.get("term", ""))[:60], "definition": str(j.get("definition", ""))[:240]}
                for j in (data.get("jargon") or []) if isinstance(j, dict)
            ][:6] or fallback["jargon"],
            "generated_at": iso(),
            "cached": False,
        }
        _write_cache(key, "explain", result)
        return result
    except AIError as exc:
        fallback["warning"] = f"AI unavailable ({exc}); showing a deterministic simplification instead."
        return fallback


# ----------------------------------------------------------------------- quiz
def quiz(article: dict, *, count: int = 4) -> dict:
    """Build a comprehension quiz. AI questions when available, else cloze."""
    text = htmltext.strip_boilerplate(article.get("content_text") or article.get("summary") or "")
    local = _local_quiz(article, text, count=count)
    if not settings.ai_enabled or len(text.split()) < 60:
        return local
    key = _cache_key(article, "quiz")
    cached = _read_cache(key)
    if cached:
        return cached
    prompt = (
        "Write a short comprehension quiz about the article below for a student. "
        "Every answer must be verifiable in the text. Do not ask about opinions. "
        'Return JSON: {"questions": [{"question": string, "options": [4 strings], '
        '"answer_index": 0-3, "explain": string (one sentence quoting the text)}]}\n\n'
        + _article_context(article, max_chars=5000)
    )
    try:
        data = _parse_json(_call_provider(prompt, max_tokens=900))
        questions = []
        for raw in data.get("questions") or []:
            options = [str(o)[:220] for o in (raw.get("options") or []) if str(o).strip()]
            if len(options) < 2:
                continue
            try:
                answer = int(raw.get("answer_index", 0))
            except (TypeError, ValueError):
                answer = 0
            questions.append(
                {
                    "question": str(raw.get("question", ""))[:300],
                    "options": options[:4],
                    "answer_index": max(0, min(len(options) - 1, answer)),
                    "explain": str(raw.get("explain", ""))[:400],
                }
            )
        if not questions:
            return local
        result = {
            "engine": "ai",
            "available": True,
            "provider": "openai-compatible",
            "model": settings.ai_model,
            "questions": questions[:6],
            "generated_at": iso(),
            "cached": False,
        }
        _write_cache(key, "quiz", result)
        return result
    except AIError:
        return local


_NUMBER = re.compile(
    r"\$?\d[\d,.]*\s?(?:%|percent|million|billion|trillion|thousand|people|votes|years|months|days|"
    r"miles|kilometres|kilometers|km|degrees|points|seats|jobs)?",
    re.I,
)
_YEAR = re.compile(r"^(19|20)\d{2}$")


def _local_quiz(article: dict, text: str, *, count: int = 4) -> dict:
    """Deterministic cloze quiz built only from the article's own sentences.

    Two question types, both answerable strictly from the text:
      * "which figure appears here" (numbers/percentages)
      * "which name completes this sentence" (multi-word proper nouns)
    """
    import random

    sentences = [
        s.strip() for s in htmltext.sentences(text)
        if 55 <= len(s) <= 300
        and not re.match(r"^\s*\d{1,2}[.)]\s", s.strip())
        and "preferred source" not in s.lower()
    ]
    pool = sentences or [s for s in htmltext.sentences(text) if len(s) > 30]
    rng = random.Random(hash(article.get("id")) & 0xFFFF)
    questions: list[dict] = []

    # All figures mentioned anywhere in the piece, for plausible distractors.
    all_numbers: list[str] = []
    for sentence in pool:
        for raw in _NUMBER.findall(sentence):
            value = raw.strip().rstrip(".,;:")
            if value and value not in all_numbers:
                all_numbers.append(value)

    for sentence in pool:
        if len(questions) >= count:
            break
        numbers = [n.strip().rstrip(".,;:") for n in _NUMBER.findall(sentence)]
        numbers = [n for n in numbers if n and len(n) <= 18]
        if not numbers:
            continue
        answer = numbers[0]
        if answer not in sentence or sentence.find(answer) < 12:
            continue
        # A bare year is only interesting when the sentence is about the year.
        if _YEAR.match(answer) and not re.search(r"\b(year|in|since|until|during)\b", sentence[: sentence.find(answer)], re.I):
            continue
        others = [n for n in all_numbers if n != answer and n != answer.rstrip("%")]
        # Prefer numbers of a similar shape (both percentages, both money, etc.)
        same_shape = [n for n in others if ("%" in n) == ("%" in answer) and ("$" in n) == ("$" in answer)]
        candidates = same_shape or others
        rng.shuffle(candidates)
        options = [answer]
        for candidate in candidates:
            if candidate not in options:
                options.append(candidate)
            if len(options) == 4:
                break
        if len(options) < 3:
            continue
        options = options[:4]
        rng.shuffle(options)
        questions.append(
            {
                "type": "figure",
                "question": "Which figure belongs in the blank?\n\n“" + _blank_numbers(sentence) + "”",
                "options": options,
                "answer_index": options.index(answer),
                "explain": "The article states: “" + sentence + "”",
            }
        )

    # Name questions: blank a full multi-word name so the answer is unambiguous.
    name_pool: list[str] = []
    for sentence in pool:
        for match in re.finditer(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})\b", sentence):
            name = match.group(1)
            if name not in name_pool and not re.match(r"^(The|This|That|These|Those|In|On|At|By|For|And|But)\b", name):
                name_pool.append(name)

    for sentence in pool:
        if len(questions) >= count:
            break
        matches = list(re.finditer(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})\b", sentence))
        if not matches:
            continue
        match = max(matches, key=lambda m: len(m.group(1)))
        answer = match.group(1)
        if sentence.count(answer) > 1 or len(answer.split()) < 2:
            continue
        distractors = [n for n in name_pool if n != answer and answer.split()[0] not in n and n.split()[0] not in answer]
        if len(distractors) < 2:
            continue
        rng.shuffle(distractors)
        options = [answer] + distractors[:3]
        rng.shuffle(options)
        questions.append(
            {
                "type": "name",
                "question": "Which name completes this sentence?\n\n“" + sentence.replace(answer, "______", 1) + "”",
                "options": options,
                "answer_index": options.index(answer),
                "explain": "The article says: “" + sentence + "”",
            }
        )

    return {
        "engine": "local",
        "available": True,
        "provider": None,
        "model": "rule-based cloze",
        "questions": questions[:count],
        "generated_at": iso(),
        "cached": False,
        "note": "Generated on-device from the article's own sentences, so every answer is checkable against the text.",
    }


def _blank_numbers(sentence: str) -> str:
    return _NUMBER.sub(" ______ ", sentence, count=1).replace("  ", " ")


# ---------------------------------------------------------------------- jargon
JARGON: dict[str, str] = {
    "inflation": "The rate at which prices rise. When inflation is 3%, things that cost $100 last year cost about $103 now.",
    "deflation": "Falling prices. Sounds good, but it can make people delay spending and slow the economy.",
    "gdp": "Gross domestic product: the total value of everything a country produces in a year.",
    "recession": "Two quarters (six months) in a row of shrinking economic output.",
    "tariff": "A tax a country charges on goods imported from another country.",
    "sanctions": "Penalties — often travel or money restrictions — one country imposes on another.",
    "ceasefire": "An agreement to stop fighting, usually temporary and often monitored by outsiders.",
    "coalition": "A government formed when several parties team up because no single party won enough seats.",
    "quorum": "The minimum number of members who must be present for a vote or meeting to count.",
    "filibuster": "A long speech used to delay or block a vote in a legislature.",
    "amendment": "A formal change to a law or constitution.",
    "referendum": "A direct vote by the public on a single question, rather than a vote in parliament.",
    "injunction": "A court order telling someone to do — or stop doing — something.",
    "indictment": "A formal charge saying someone is suspected of a crime and should face trial.",
    "plea deal": "An agreement where a defendant admits to a lesser charge in exchange for a lighter punishment.",
    "subpoena": "A legal order requiring someone to appear in court or hand over documents.",
    "monetary policy": "Central-bank decisions about interest rates and money supply, used to steer the economy.",
    "interest rate": "The cost of borrowing money, set by a central bank or lender, shown as a percentage.",
    "bond": "A loan to a government or company that pays interest and is paid back on a set date.",
    "yield": "The income an investment pays, usually expressed as a yearly percentage.",
    "ipo": "Initial public offering: the first time a private company sells shares to the public.",
    "valuation": "An estimate of how much a company is worth.",
    "quarterly earnings": "A company's profit report for a three-month period.",
    "supply chain": "The chain of companies and steps that turn raw materials into a product you can buy.",
    "algorithm": "A set of rules a computer follows to make a decision or recommendation.",
    "machine learning": "Software that improves at a task by finding patterns in data instead of following fixed rules.",
    "large language model": "An AI trained on huge amounts of text to predict and produce language.",
    "data centre": "A building full of servers that stores and processes data for the internet.",
    "open source": "Software whose code is public and can be reused and modified.",
    "encryption": "Scrambling data so only someone with the right key can read it.",
    "zero-day": "A software flaw attackers can exploit before the maker has a fix.",
    "malware": "Software designed to damage or break into a computer system.",
    "phishing": "Fake messages that pretend to be trustworthy to steal passwords or money.",
    "peer review": "Experts checking a study before it is published.",
    "placebo": "A treatment with no active ingredient, used to compare against a real treatment.",
    "randomised trial": "A study where participants are assigned to groups by chance, to avoid bias.",
    "preprint": "A research paper shared publicly before peer review.",
    "variant": "A version of a virus with genetic changes.",
    "efficacy": "How well something works in controlled conditions.",
    "incidence": "How many new cases of something appear in a population over a period.",
    "prevalence": "How common something is in a population at a given time.",
    "emissions": "Gases released into the air, especially those that warm the climate.",
    "net zero": "Removing as many greenhouse gases as you emit.",
    "carbon offset": "Paying for emissions reductions elsewhere to balance your own.",
    "renewable": "Energy from sources that refill naturally, like sun, wind and water.",
    "biodiversity": "The variety of living things in a place.",
    "adaptation": "Changing how we live to cope with climate impacts that are already happening.",
    "mitigation": "Actions that reduce the causes of climate change, like cutting emissions.",
    "injunction relief": "A temporary court order while a case is decided.",
    "appropriations": "The formal process a legislature uses to approve spending.",
    "continuing resolution": "A temporary spending law that keeps government funded when a budget is not passed.",
    "debt ceiling": "A legal limit on how much a government can borrow.",
    "austerity": "Government spending cuts designed to reduce deficits.",
    "subsidy": "Government money that lowers the cost of something for producers or consumers.",
    "antitrust": "Laws meant to stop companies from dominating a market unfairly.",
    "merger": "Two companies joining into one.",
    "acquisition": "One company buying another.",
    "layoffs": "Job cuts by an employer.",
    "strike": "Workers refusing to work as a form of protest, usually over pay or conditions.",
    "union": "An organisation of workers that negotiates with employers.",
    "ballot measure": "A proposal decided directly by voters.",
    "swing state": "A place where elections are close enough that either party could win.",
    "exit poll": "A survey of voters right after they vote, used to estimate results.",
    "coalition government": "A government formed by multiple parties sharing power.",
    "veto": "A president's or governor's power to reject a law.",
    "executive order": "A directive from a president or governor that does not need a new law.",
}


def decode_jargon(text: str, limit: int = 5) -> list[dict]:
    lowered = (text or "").lower()
    found = []
    for term, definition in JARGON.items():
        if term in lowered:
            found.append({"term": term, "definition": definition})
            if len(found) >= limit:
                break
    return found


# --------------------------------------------------------------------- caching
def _cache_key(article: dict, kind: str) -> str:
    basis = f"{article.get('id')}:{article.get('content_hash') or (article.get('content_text') or article.get('summary') or '')[:4000]}:{kind}:{settings.ai_model}"
    return hashlib.sha1(basis.encode()).hexdigest()


def _read_cache(key: str) -> dict | None:
    row = db.query_one("SELECT payload FROM ai_cache WHERE key=?", (key,))
    if not row:
        return None
    try:
        return json.loads(row["payload"])
    except (ValueError, TypeError):
        return None


def _write_cache(key: str, kind: str, payload: dict) -> None:
    try:
        db.execute(
            "INSERT INTO ai_cache(key, kind, model, payload, created_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, created_at=excluded.created_at",
            (key, kind, settings.ai_model, json.dumps(payload), iso()),
        )
    except Exception:
        log.debug("could not cache AI result")


def provider_test() -> dict:
    """Small call used by the settings page to verify a provider."""
    if not settings.ai_enabled:
        return {"ok": False, "error": "no_provider"}
    try:
        text = _call_provider('Return exactly this JSON: {"ok": true}', max_tokens=32)
        return {"ok": True, "raw": text[:200]}
    except AIError as exc:
        return {"ok": False, "error": str(exc)}
