"""English localisation for headlines and previews.

Pulse keeps the publisher's full article in its original language.  This module
only localises the short surfaces a reader sees before opening the story:
headline, preview/summary and overview.  Translations are cached in SQLite and
never sent to the browser as if they were the publisher's own wording.

The app works without a key.  Google's public translation endpoint is used
first, with MyMemory as a no-key fallback.  Both receive only the headline and
preview, never the full article text.  If both are unavailable we return the
original text and the UI can still link to the source.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import unicodedata
import urllib.parse
from dataclasses import dataclass

from .config import settings
from .db import db
from .httpclient import FetchError, HttpClient
from .logging_setup import get_logger
from .timeutil import iso

log = get_logger("translate")

LANGUAGE_NAMES = {
    "ar": "Arabic", "bg": "Bulgarian", "bn": "Bengali", "ca": "Catalan",
    "cs": "Czech", "da": "Danish", "de": "German", "el": "Greek", "en": "English",
    "es": "Spanish", "fa": "Persian", "fi": "Finnish", "fr": "French", "he": "Hebrew",
    "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian", "id": "Indonesian",
    "it": "Italian", "ja": "Japanese", "ko": "Korean", "nl": "Dutch", "no": "Norwegian",
    "pl": "Polish", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian",
    "sk": "Slovak", "sr": "Serbian", "sv": "Swedish", "th": "Thai", "tr": "Turkish",
    "uk": "Ukrainian", "vi": "Vietnamese", "zh": "Chinese",
}

# Words that are common enough that several hits are strong evidence.  Short
# words such as "a", "y", "e" are deliberately excluded: names and English
# copy produce too many false positives.
_PROFILES: dict[str, tuple[str, ...]] = {
    "es": ("el", "la", "los", "las", "de", "del", "que", "en", "un", "una", "unos", "unas",
           "por", "para", "con", "sin", "como", "más", "pero", "sus", "su", "al", "se",
           "entre", "desde", "hasta", "sobre", "este", "esta", "estos", "estas", "fue",
           "son", "ser", "hay", "muy", "también", "según", "gobierno", "presidente"),
    "fr": ("le", "la", "les", "des", "du", "de", "et", "est", "une", "un", "dans", "pour",
           "qui", "que", "sur", "au", "aux", "ce", "cette", "ces", "pas", "plus", "avec",
           "sont", "être", "a", "ont", "par", "mais", "comme", "selon"),
    "pt": ("o", "a", "os", "as", "de", "do", "da", "dos", "das", "que", "em", "um", "uma",
           "para", "com", "não", "por", "mais", "como", "ao", "aos", "é", "são", "foi",
           "ser", "na", "no", "nas", "nos", "se", "sobre", "entre", "governo"),
    "it": ("il", "lo", "la", "i", "gli", "le", "di", "del", "della", "che", "un", "una",
           "per", "con", "non", "sono", "è", "era", "più", "anche", "come", "nel", "nella",
           "alla", "allo", "dai", "dalle", "questo", "questa", "governo"),
    "de": ("der", "die", "das", "den", "dem", "des", "und", "ist", "nicht", "mit", "für",
           "auf", "ein", "eine", "einer", "eines", "zu", "von", "im", "in", "als", "auch",
           "sich", "wird", "werden", "hat", "haben", "nach", "bei", "aus", "über"),
    "nl": ("de", "het", "een", "en", "van", "dat", "die", "in", "op", "voor", "met", "niet",
           "is", "zijn", "wordt", "door", "aan", "bij", "maar", "ook", "als", "om", "te"),
    "sv": ("och", "det", "att", "som", "på", "är", "av", "för", "med", "till", "den", "ett",
           "inte", "om", "var", "har", "men", "från", "vid", "ska", "kan"),
    "da": ("og", "det", "at", "som", "på", "er", "af", "for", "med", "til", "den", "en",
           "ikke", "om", "var", "har", "men", "fra", "ved", "skal", "kan"),
    "no": ("og", "det", "at", "som", "på", "er", "av", "for", "med", "til", "den", "en",
           "ikke", "om", "var", "har", "men", "fra", "ved", "skal", "kan"),
    "pl": ("i", "w", "z", "na", "do", "nie", "że", "się", "jest", "dla", "od", "po", "jak",
           "ale", "tak", "ten", "ta", "to", "są", "być", "przez", "przy", "oraz"),
    "tr": ("ve", "bir", "bu", "da", "de", "için", "ile", "olarak", "sonra", "gibi", "daha",
           "çok", "var", "yok", "olan", "olan", "tarafından", "kadar", "ama", "veya"),
    "id": ("dan", "yang", "di", "ke", "dari", "untuk", "dengan", "ini", "itu", "tidak",
           "adalah", "akan", "pada", "juga", "dalam", "sebagai", "oleh", "atau", "karena"),
    "ro": ("și", "în", "de", "la", "cu", "pe", "un", "o", "care", "este", "sunt", "pentru",
           "din", "nu", "mai", "după", "despre", "ca", "prin"),
    "ca": ("el", "la", "els", "les", "de", "del", "que", "en", "un", "una", "per", "amb",
           "no", "és", "són", "com", "més", "aquest", "aquesta", "segons"),
}

_LATIN_ACCENTS = set("áéíóúñüçàèìòùâêîôûäëïöüãõåæøœßşğıłńśźżčřěůý")
_ENGLISH = {
    "the", "and", "of", "to", "in", "is", "for", "that", "with", "on", "as", "are",
    "was", "were", "by", "from", "at", "this", "it", "be", "or", "an", "not", "have",
    "has", "had", "will", "would", "can", "could", "after", "before", "says", "said",
    "new", "over", "into", "about", "than", "its", "their", "his", "her", "they",
}

_client = HttpClient()
_cache_lock = threading.Lock()
_memory: dict[str, str] = {}
_last_network = 0.0
_NETWORK_GAP = 0.25


def language_name(code: str | None) -> str:
    if not code:
        return "another language"
    return LANGUAGE_NAMES.get(code.lower(), code.upper())


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def detect_language(text: str | None) -> str:
    """Best-effort language code for a headline + short preview.

    This is intentionally conservative: English copy with a foreign name stays
    English.  Script detection is exact for non-Latin writing systems.
    """
    value = _clean(text)
    if len(value) < 4:
        return "en"
    # Scripts with an unambiguous Unicode block.
    if re.search(r"[\u0600-\u06ff\u0750-\u077f]", value):
        return "fa" if re.search(r"[پچژگ]", value) else "ar"
    if re.search(r"[\u0590-\u05ff]", value):
        return "he"
    if re.search(r"[\u0370-\u03ff]", value):
        return "el"
    if re.search(r"[\u0400-\u04ff]", value):
        return "uk" if re.search(r"[іїєґІЇЄҐ]", value) else "ru"
    if re.search(r"[\u0900-\u097f]", value):
        return "hi"
    if re.search(r"[\u0980-\u09ff]", value):
        return "bn"
    if re.search(r"[\u0b80-\u0bff]", value):
        return "ta"
    if re.search(r"[\u0e00-\u0e7f]", value):
        return "th"
    if re.search(r"[\u3040-\u30ff]", value):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", value):
        return "ko"
    if re.search(r"[\u4e00-\u9fff]", value):
        return "zh"

    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž'’-]+", value.lower())
    if len(words) < 3:
        return "en"
    counts: dict[str, int] = {}
    for code, markers in _PROFILES.items():
        hits = sum(1 for word in words if len(word) > 1 and word not in _ENGLISH and word in markers)
        # Accented characters are useful supporting evidence, but not enough on
        # their own (English articles mention "São Paulo" and "México").
        accents = sum(1 for char in value.lower() if char in _LATIN_ACCENTS)
        counts[code] = hits * 2 + (1 if accents >= 2 else 0)
    english_hits = sum(1 for word in words if word in _ENGLISH)
    best_code, best_score = max(counts.items(), key=lambda item: item[1])
    if best_score >= 4 and best_score > english_hits * 2 + 1:
        return best_code
    if best_score >= 8 and english_hits <= 2:
        return best_code
    return "en"


def _cache_key(source_lang: str, text: str) -> str:
    return hashlib.sha256(f"{source_lang}|en|{text}".encode("utf-8")).hexdigest()


def _cache_get(source_lang: str, text: str) -> str | None:
    key = _cache_key(source_lang, text)
    with _cache_lock:
        if key in _memory:
            return _memory[key]
    row = db.query_one(
        "SELECT translated_text FROM translations WHERE cache_key=? AND target_lang='en'",
        (key,),
    )
    if row:
        with _cache_lock:
            _memory[key] = row["translated_text"]
        return row["translated_text"]
    return None


def _cache_put(source_lang: str, text: str, translated: str, provider: str) -> None:
    key = _cache_key(source_lang, text)
    with _cache_lock:
        _memory[key] = translated
    try:
        db.execute(
            """
            INSERT INTO translations(cache_key, source_lang, target_lang, source_text,
                                     translated_text, provider, created_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(cache_key) DO UPDATE SET
              translated_text=excluded.translated_text, provider=excluded.provider,
              created_at=excluded.created_at
            """,
            (key, source_lang, "en", text[:4000], translated[:8000], provider, iso()),
        )
    except Exception:
        log.debug("could not persist translation", exc_info=True)


def _google(text: str) -> tuple[str | None, str | None]:
    url = (
        "https://clients5.google.com/translate_a/t?client=dict-chrome-ex"
        "&sl=auto&tl=en&q=" + urllib.parse.quote(text[:1600], safe="")
    )
    result = _client.fetch(url, timeout=9, retries=0, allow_curl_fallback=True)
    if result.status != 200 or not result.body:
        return None, None
    try:
        data = json.loads(result.text)
    except (ValueError, TypeError):
        return None, None
    if not isinstance(data, list) or not data:
        return None, None
    first = data[0]
    if isinstance(first, list):
        translated = first[0] if first else None
    else:
        translated = first
    detected = data[1] if len(data) > 1 and isinstance(data[1], str) else None
    if not isinstance(translated, str) or not translated.strip():
        return None, detected
    return translated, detected


def _mymemory(text: str, source_lang: str) -> str | None:
    params = {"q": text[:490], "langpair": f"{source_lang}|en"}
    email = __import__("os").environ.get("PULSE_TRANSLATE_EMAIL", "").strip()
    if email:
        params["de"] = email
    url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(params)
    result = _client.fetch(url, timeout=9, retries=0, allow_curl_fallback=True)
    if result.status != 200:
        return None
    try:
        data = json.loads(result.text)
    except (ValueError, TypeError):
        return None
    translated = ((data.get("responseData") or {}).get("translatedText") or "").strip()
    if not translated or "MYMEMORY WARNING" in translated.upper():
        return None
    return html.unescape(translated)


def translate_text(text: str, source_lang: str | None = None) -> tuple[str | None, str]:
    """Translate one short string; returns (translated, provider)."""
    text = _clean(text)
    if not text:
        return None, "none"
    code = (source_lang or detect_language(text) or "").lower()
    if code == "en":
        return text, "none"
    cached = _cache_get(code, text)
    if cached:
        return cached, "cache"
    translated = None
    provider = "google"
    try:
        translated, _detected = _google(text)
    except (FetchError, OSError, ValueError) as exc:
        log.debug("google translate unavailable: %s", exc)
    if not translated:
        provider = "mymemory"
        try:
            translated = _mymemory(text, code)
        except (FetchError, OSError, ValueError) as exc:
            log.debug("mymemory translate unavailable: %s", exc)
    if not translated:
        return None, "none"
    translated = _clean(translated)
    _cache_put(code, text, translated, provider)
    return translated, provider


@dataclass
class PairTranslation:
    title: str
    summary: str
    provider: str
    source_lang: str


_SEP = "\n\n@@PULSE@@\n\n"


def translate_pair(title: str, summary: str, source_lang: str | None = None) -> PairTranslation | None:
    """Translate headline + preview in one request using a stable separator."""
    title = _clean(title)
    summary = _clean(summary)
    if not title:
        return None
    code = (source_lang or detect_language(f"{title} {summary}")).lower()
    if code == "en":
        return PairTranslation(title, summary, "none", "en")
    # Keep the request small enough for the free endpoints.  The headline is
    # always kept whole; the preview is trimmed at a word boundary.
    combined = title + _SEP + summary[:700]
    if len(combined) > 1500:
        combined = combined[:1500].rsplit(" ", 1)[0]
    cached = _cache_get(code, combined)
    provider = "cache"
    if not cached:
        provider = "google"
        translated = None
        try:
            translated, _detected = _google(combined)
        except (FetchError, OSError, ValueError):
            translated = None
        if not translated:
            provider = "mymemory"
            try:
                translated = _mymemory(combined, code)
            except (FetchError, OSError, ValueError):
                translated = None
        if not translated:
            return None
        cached = _clean(translated)
        _cache_put(code, combined, cached, provider)
    if _SEP.strip() in cached:
        parts = cached.split("@@PULSE@@", 1)
        new_title = _clean(parts[0])
        new_summary = _clean(parts[1]) if len(parts) > 1 else ""
    else:
        # Some providers collapse the separator.  Keep the translation as the
        # headline and leave the preview blank rather than risk mixing copy.
        new_title = _clean(cached)
        new_summary = ""
    if not new_title:
        return None
    return PairTranslation(new_title, new_summary, provider, code)


def _preview(text: str, limit: int = 260) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if boundary >= int(limit * 0.55):
        return cut[: boundary + 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def decorate(payload: dict) -> dict:
    """Attach language metadata and apply a cached translation, if present."""
    title = str(payload.get("title") or "")
    summary = str(payload.get("summary") or "")
    code = detect_language(f"{title} {summary}")
    payload["language"] = code
    payload["language_name"] = language_name(code)
    if code == "en":
        payload.setdefault("translated", False)
        return payload
    combined = _clean(title) + _SEP + _clean(summary)[:700]
    cached = _cache_get(code, combined)
    if cached and _SEP.strip() in cached:
        parts = cached.split("@@PULSE@@", 1)
        apply_translation(payload, code, _clean(parts[0]), _clean(parts[1]), "cache")
    return payload


def apply_translation(payload: dict, code: str, title: str, summary: str, provider: str) -> dict:
    if not title:
        return payload
    payload["title_original"] = payload.get("title") or ""
    payload["summary_original"] = payload.get("summary") or ""
    payload["preview_original"] = payload.get("preview") or ""
    payload["title"] = title
    if summary:
        payload["summary"] = summary
        payload["preview"] = _preview(summary)
        if "snippet" in payload:
            payload["snippet"] = _preview(summary, 240)
    payload["translated"] = True
    payload["translation_provider"] = provider
    payload["language"] = code
    payload["language_name"] = language_name(code)
    return payload


def localize_payload(payload: dict, *, sync: bool = False) -> dict:
    """Localise a feed card/detail payload.  Synchronous calls are bounded."""
    if payload.get("translated"):
        return payload
    code = payload.get("language") or detect_language(
        f"{payload.get('title') or ''} {payload.get('summary') or ''}"
    )
    payload["language"] = code
    payload["language_name"] = language_name(code)
    if code == "en":
        return payload
    combined = _clean(payload.get("title")) + _SEP + _clean(payload.get("summary"))[:700]
    cached = _cache_get(code, combined)
    if cached:
        if _SEP.strip() in cached:
            parts = cached.split("@@PULSE@@", 1)
            return apply_translation(payload, code, _clean(parts[0]), _clean(parts[1]), "cache")
        return payload
    if not sync:
        return payload
    result = translate_pair(payload.get("title") or "", payload.get("summary") or "", code)
    if result and result.title:
        apply_translation(payload, result.source_lang, result.title, result.summary, result.provider)
    return payload


def localize_items(items: list[dict], *, sync_limit: int = 6) -> list[dict]:
    """Decorate a page of cards, translating only a bounded number on demand."""
    remaining = max(0, sync_limit)
    for item in items:
        decorate(item)
        if item.get("language") and item["language"] != "en" and not item.get("translated"):
            if remaining > 0:
                localize_payload(item, sync=True)
                remaining -= 1
            else:
                localize_payload(item, sync=False)
    return items


def translate_overview(overview: dict, source_lang: str | None) -> dict:
    """Translate extractive overview fields; AI overviews are already English."""
    if overview.get("engine") == "ai" or not source_lang or source_lang == "en":
        return overview
    summary = _clean(overview.get("summary") or "")
    points = [str(p) for p in (overview.get("key_points") or []) if str(p).strip()]
    why = _clean(overview.get("why_it_matters") or "")
    if not summary and not points:
        return overview
    combined = summary + _SEP + _SEP.join(points[:3]) + _SEP + why
    result, provider = translate_text(combined, source_lang)
    if not result:
        overview["translation_unavailable"] = True
        return overview
    parts = result.split("@@PULSE@@")
    if len(parts) >= 2 and parts[0].strip():
        overview["summary"] = _clean(parts[0])
    if len(parts) >= 3:
        translated_points = [_clean(p) for p in parts[1:-1] if _clean(p)]
        if translated_points:
            overview["key_points"] = translated_points[:5]
    if len(parts) >= 2 and parts[-1].strip():
        overview["why_it_matters"] = _clean(parts[-1])
    overview["translation_provider"] = provider
    overview["translated"] = True
    return overview


# --------------------------------------------------------------- full article
# The short surfaces above are translated automatically.  Full article
# translation is an explicit reader action: only when someone taps "Translate
# article" do we send the publisher's paragraphs to the same service.  The
# translation is stored as a single JSON document, so revisiting the story is
# instant and does not hit the network again.

_MAX_BLOCK_CHARS = 1400


def _full_cache_key(article_id: int, code: str) -> str:
    return hashlib.sha256(f"article-full|{article_id}|{code}|en".encode("utf-8")).hexdigest()


def _full_cache_get(key: str) -> dict | None:
    row = db.query_one(
        "SELECT translated_text, provider FROM translations WHERE cache_key=? AND target_lang='en'",
        (key,),
    )
    if not row:
        return None
    try:
        data = json.loads(row["translated_text"])
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    data["provider"] = row["provider"] or data.get("provider") or "cache"
    data["cached"] = True
    return data


def _full_cache_put(key: str, payload: dict, code: str, provider: str) -> None:
    try:
        db.execute(
            """
            INSERT INTO translations(cache_key, source_lang, target_lang, source_text,
                                     translated_text, provider, created_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(cache_key) DO UPDATE SET
              translated_text=excluded.translated_text, provider=excluded.provider,
              created_at=excluded.created_at
            """,
            (key, code, "en", f"article-full:{code}", json.dumps(payload, ensure_ascii=False), provider, iso()),
        )
    except Exception:
        log.debug("could not persist full article translation", exc_info=True)


def _split_text(text: str, limit: int = _MAX_BLOCK_CHARS) -> list[str]:
    """Split a long paragraph on word boundaries without dropping content."""
    text = _clean(text)
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining[:limit]
        boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind("; "))
        if boundary < int(limit * 0.55):
            boundary = cut.rfind(" ")
        if boundary < int(limit * 0.4):
            boundary = limit
        part = remaining[:boundary].strip()
        if part:
            parts.append(part)
        remaining = remaining[boundary:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def _translate_chunk(text: str, code: str) -> tuple[str | None, str]:
    """Translate one <=1400 character chunk, using the short-text cache."""
    cached = _cache_get(code, text)
    if cached:
        return cached, "cache"
    translated = None
    try:
        translated, _detected = _google(text)
    except (FetchError, OSError, ValueError) as exc:
        log.debug("google article translate unavailable: %s", exc)
    provider = "google"
    if not translated and len(text) <= 490:
        provider = "mymemory"
        try:
            translated = _mymemory(text, code)
        except (FetchError, OSError, ValueError) as exc:
            log.debug("mymemory article translate unavailable: %s", exc)
    if not translated:
        return None, "none"
    translated = _clean(translated)
    _cache_put(code, text, translated, provider)
    return translated, provider


def _translate_block_batch(texts: list[str], code: str) -> tuple[list[str | None], str]:
    """Translate several paragraphs in as few requests as possible."""
    results: list[str | None] = [None] * len(texts)
    providers: set[str] = set()
    groups: list[list[int]] = []
    current: list[int] = []
    size = 0
    for index, text in enumerate(texts):
        if len(text) > _MAX_BLOCK_CHARS:
            if current:
                groups.append(current)
                current, size = [], 0
            parts = _split_text(text)
            translated_parts = []
            for part in parts:
                translated, provider_one = _translate_chunk(part, code)
                if translated:
                    translated_parts.append(translated)
                    providers.add(provider_one)
            if translated_parts and len(translated_parts) == len(parts):
                results[index] = " ".join(translated_parts)
            continue
        extra = len(text) + (len(_SEP) if current else 0)
        if current and size + extra > _MAX_BLOCK_CHARS:
            groups.append(current)
            current, size = [], 0
        current.append(index)
        size += extra
    if current:
        groups.append(current)

    for group in groups:
        combined = _SEP.join(texts[index] for index in group)
        cached = _cache_get(code, combined)
        translated = cached
        provider = "cache" if cached else "google"
        if not translated:
            try:
                translated, _detected = _google(combined)
            except (FetchError, OSError, ValueError) as exc:
                log.debug("google article batch unavailable: %s", exc)
            if translated:
                translated = _clean(translated)
                _cache_put(code, combined, translated, provider)
        if translated:
            parts = [_clean(part) for part in re.split(r"\s*@@PULSE@@\s*", translated)]
            if len(parts) == len(group) and all(parts):
                for index, part in zip(group, parts):
                    results[index] = part
                providers.add(provider)
                continue
        # A provider can collapse or duplicate the separator.  Fall back to
        # individual paragraphs rather than risk putting the wrong text under a
        # heading.
        for index in group:
            translated_one, provider_one = _translate_chunk(texts[index], code)
            if translated_one:
                results[index] = translated_one
                providers.add(provider_one)
    if not providers:
        return results, "none"
    if providers == {"cache"}:
        return results, "cache"
    if "google" in providers:
        return results, "google"
    if "mymemory" in providers:
        return results, "mymemory"
    return results, "none"


def full_article_translation(article: dict, source_lang: str | None = None) -> dict:
    """Translate every readable paragraph of an article payload.

    ``article`` is the serialised article detail payload (it contains
    ``blocks``).  Returns a payload ready for the JSON API.  The original
    publisher text is never replaced on disk; only the returned copy changes.
    """
    blocks = article.get("blocks") or []
    if not isinstance(blocks, list) or not blocks:
        return {
            "translated": False,
            "language": source_lang or "en",
            "language_name": language_name(source_lang),
            "error": "This story has no full text to translate.",
            "blocks": [],
        }
    code = (source_lang or article.get("language") or detect_language(
        f"{article.get('title') or ''} {article.get('summary') or ''}"
    )).lower()
    if code == "en":
        return {
            "translated": False,
            "language": "en",
            "language_name": "English",
            "error": "This story is already in English.",
            "blocks": blocks,
        }
    article_id = int(article.get("id") or 0)
    key = _full_cache_key(article_id, code)
    cached = _full_cache_get(key)
    if cached and isinstance(cached.get("blocks"), list):
        return cached

    translatable: list[int] = []
    texts: list[str] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type") or "p")
        if kind not in {"p", "h2", "h3", "h4", "li", "blockquote"}:
            continue
        text = _clean(str(block.get("text") or ""))
        if len(text) < 2:
            continue
        translatable.append(index)
        texts.append(text)

    translated_texts, provider = _translate_block_batch(texts, code)
    out_blocks = [dict(block) if isinstance(block, dict) else block for block in blocks]
    translated_count = 0
    for index, text in zip(translatable, translated_texts):
        if text:
            out_blocks[index]["text"] = text
            translated_count += 1
    if translated_count == 0:
        return {
            "translated": False,
            "language": code,
            "language_name": language_name(code),
            "error": "The translation service is busy. Try again in a moment.",
            "blocks": blocks,
        }

    payload = {
        "translated": True,
        "partial": translated_count < len(translatable),
        "language": code,
        "language_name": language_name(code),
        "provider": provider,
        "translated_paragraphs": translated_count,
        "paragraphs": len(translatable),
        "blocks": out_blocks,
        "cached": False,
    }
    # Only cache a complete translation. A partial result is still shown, but
    # a later attempt should be able to fill the paragraphs the service missed.
    if not payload["partial"]:
        _full_cache_put(key, payload, code, provider)
    return payload
