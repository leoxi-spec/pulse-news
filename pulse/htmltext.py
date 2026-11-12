"""HTML -> clean text and extractive summaries.

Two rules drive this module:

1. **Never trust third-party HTML.** Feed and page HTML is converted to plain
   text blocks and rendered as escaped text on the client. That removes the
   entire class of XSS bugs that plague feed readers.
2. **Never invent facts.** Summaries are extractive: they are sentences that
   already exist in the article, chosen by centrality. Nothing is generated
   unless the user has explicitly enabled an AI provider (see `ai.py`).
"""
from __future__ import annotations

import html as html_lib
import math
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

_BLOCK_TAGS = {
    "p", "div", "section", "article", "main", "br", "li", "ul", "ol",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "td", "th",
    "tr", "figure", "figcaption", "dd", "dt", "header", "footer", "aside",
}
_SKIP_TAGS = {"script", "style", "noscript", "svg", "math", "form", "iframe", "template", "button", "select"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "source", "area", "base", "col", "embed", "param", "track", "wbr"}

_WS = re.compile(r"[\t\r\f\v ]+")
_NEWLINES = re.compile(r"\n{3,}")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[\"'“‘(\[]?[A-Z0-9])")
_ABBREVIATIONS = ("Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.", "St.", "vs.", "etc.", "e.g.", "i.e.", "U.S.", "U.K.", "a.m.", "p.m.", "No.", "Gen.", "Sen.", "Rep.", "Gov.")


@dataclass
class Block:
    type: str
    text: str
    level: int = 0

    def to_dict(self) -> dict:
        return {"type": self.type, "text": self.text, **({"level": self.level} if self.level else {})}


@dataclass
class ExtractedArticle:
    title: str = ""
    blocks: list[Block] = field(default_factory=list)
    image: str | None = None
    images: list[str] = field(default_factory=list)
    author: str | None = None
    site_name: str | None = None
    published_hint: str | None = None
    paywall: bool = False
    word_count: int = 0

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks if b.type in ("p", "h2", "h3", "blockquote", "li"))

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "blocks": [b.to_dict() for b in self.blocks],
            "image": self.image,
            "images": self.images,
            "author": self.author,
            "site_name": self.site_name,
            "paywall": self.paywall,
            "word_count": self.word_count,
        }


class _BlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.images: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._current: list[str] = []
        self._href: str | None = None
        self._link_text: list[str] = []
        self._list_depth = 0

    # -- helpers ---------------------------------------------------------
    def _flush(self, force_type: str | None = None) -> None:
        text = _WS.sub(" ", "".join(self._current)).strip()
        self._current = []
        if len(text) < 2:
            return
        kind = force_type or ("li" if self._list_depth else "p")
        self.blocks.append(Block(kind, text))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        attributes = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
            return
        if tag == "img":
            src = attributes.get("src") or attributes.get("data-src") or ""
            if src.startswith("http"):
                self.images.append(src)
            return
        if tag == "a":
            href = attributes.get("href", "")
            if href.startswith("http"):
                self._href = href
                self._link_text = []
            return
        if tag in ("ul", "ol"):
            self._list_depth += 1
            return
        if tag in _BLOCK_TAGS:
            if self._current:
                self._flush()
            if tag in _HEADING_TAGS:
                self._pending_heading = tag
            elif tag == "blockquote":
                self._pending_heading = "blockquote"
            elif tag == "li" and self._list_depth == 0:
                self._list_depth = 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
            return
        if tag == "a" and self._href:
            label = _WS.sub(" ", "".join(self._link_text)).strip()
            if label:
                self.links.append((self._href, label))
            self._href = None
            return
        if tag in ("ul", "ol"):
            if self._current:
                self._flush("li")
            self._list_depth = max(0, self._list_depth - 1)
            return
        if tag == "li":
            if self._current:
                self._flush("li")
            return
        if tag in _BLOCK_TAGS:
            pending = getattr(self, "_pending_heading", None)
            if self._current:
                if pending in _HEADING_TAGS:
                    self._flush(pending)
                elif pending == "blockquote":
                    self._flush("blockquote")
                else:
                    self._flush()
            self._pending_heading = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
            return
        if self._href is not None:
            self._link_text.append(data)
        self._current.append(data)

    def close(self) -> None:
        super().close()
        if self._current:
            self._flush()


def text_of(markup: str) -> str:
    """HTML to normalised plain text (paragraph breaks preserved)."""
    if not markup:
        return ""
    if "<" not in markup:
        return _NEWLINES.sub("\n\n", _WS.sub(" ", markup).replace("\r\n", "\n")).strip()
    parser = _BlockParser()
    try:
        parser.feed(markup)
        parser.close()
    except Exception:
        return _WS.sub(" ", re.sub(r"<[^>]+>", " ", markup)).strip()
    parts: list[str] = []
    for block in parser.blocks:
        parts.append(block.text)
    return _NEWLINES.sub("\n\n", "\n\n".join(parts)).strip()


def blocks_of(markup: str) -> list[Block]:
    if not markup:
        return []
    parser = _BlockParser()
    try:
        parser.feed(markup)
        parser.close()
    except Exception:
        plain = _WS.sub(" ", re.sub(r"<[^>]+>", " ", markup)).strip()
        return [Block("p", plain)] if plain else []
    return [b for b in parser.blocks if len(b.text) >= 2]


def first_image(markup: str) -> str | None:
    if not markup:
        return None
    match = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']', markup, re.I)
    if match and match.group(1).startswith("http"):
        return match.group(1)
    return None


_IMG_SKIP = re.compile(
    r"(logo|icon|avatar|sprite|badge|pixel|track|analytics|spacer|advert|\bads?/|emoji|"
    r"favicon|placeholder|default|masthead|brand|share|social|subscribe|newsletter|"
    r"author|headshot|profile|thumbnail-default|related|recommend|promo|thumb|teaser|"
    r"widget|card|most-read|also-read|read-more|more-stories|elsewhere|outbrain|taboola|"
    r"mobileapp|sponsor|partner|banner|promo|(?:^|[-_/])ads?(?:[-_.]|$))",
    re.I,
)
_IMG_EXT = re.compile(r"\.(?:jpe?g|png|webp|avif)(?:[?#]|$)", re.I)


def image_urls(markup: str, base_url: str = "", limit: int = 24) -> list[str]:
    """Collect large, article-like images from a page, in reading order."""
    if not markup:
        return []
    found: list[str] = []

    def add(url: str | None, width: int | None = None, height: int | None = None,
            min_width: int = 220, min_height: int = 130) -> None:
        if not url:
            return
        url = html_lib.unescape(str(url)).strip().strip('"\'')
        if not url or url.startswith(("data:", "blob:", "javascript:")):
            return
        if width is not None and width < min_width:
            return
        if height is not None and height < min_height:
            return
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = urljoin(base_url, url)
        if not url.startswith("http"):
            return
        if _IMG_SKIP.search(url):
            return
        if not _IMG_EXT.search(url) and "format=" not in url and "image" not in url.lower():
            return
        if url in found:
            return
        found.append(url)

    # Lead image metadata first.
    for name in ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"):
        add(meta_content(markup, name))

    # JSON-LD image fields (string or list of strings/objects).
    for match in re.finditer(r'"image"\s*:\s*(\[[^\]]{0,4000}\]|"[^"]{4,500}")', markup, re.I | re.S):
        for url in re.findall(r'https?://[^"\s,\]]+', match.group(1)):
            add(url)

    # <img> and <source> tags, respecting obvious size hints and srcset.
    for tag in re.finditer(r"<(img|source)\b[^>]*>", markup, re.I | re.S):
        raw = tag.group(0)
        attrs = {k.lower(): v for k, v in re.findall(r'([a-zA-Z_:.-]+)\s*=\s*["\']([^"\']*)["\']', raw)}

        def dim(name: str) -> int | None:
            try:
                return int(float(attrs.get(name, "")))
            except (TypeError, ValueError):
                return None

        width = dim("width")
        height = dim("height")
        srcset = attrs.get("srcset") or attrs.get("data-srcset") or ""
        best = None
        best_width = -1
        for entry in srcset.split(","):
            parts = entry.strip().split()
            if not parts:
                continue
            candidate = parts[0]
            size = 0
            if len(parts) > 1 and parts[1].endswith("w"):
                try:
                    size = int(parts[1][:-1])
                except ValueError:
                    size = 0
            if size > best_width:
                best, best_width = candidate, size
        # Article figures are trustworthy; loose <img> tags need to be large
        # enough to be real photography rather than an ad or a related thumb.
        inside_figure = markup.rfind("<figure", 0, tag.start()) > markup.rfind("</figure>", 0, tag.start())
        if inside_figure:
            add(best or attrs.get("src") or attrs.get("data-src") or attrs.get("data-original"), width, height, 200, 120)
        elif best_width >= 480 or (width or 0) >= 480 or (height or 0) >= 270:
            add(best or attrs.get("src") or attrs.get("data-src") or attrs.get("data-original"), width, height, 480, 270)
        if len(found) >= limit:
            break

    return found[:limit]


def meta_content(markup: str, *names: str) -> str | None:
    for name in names:
        pattern = (
            r'<meta[^>]+(?:property|name)=["\']' + re.escape(name) + r'["\'][^>]*content=["\']([^"\']*)["\']'
        )
        match = re.search(pattern, markup, re.I)
        if match:
            return html_lib.unescape(match.group(1)).strip()
        pattern = (
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']' + re.escape(name) + r'["\']'
        )
        match = re.search(pattern, markup, re.I)
        if match:
            return html_lib.unescape(match.group(1)).strip()
    return None


_PAYWALL_PHRASES = (
    "subscribe to continue reading",
    "subscribe to read",
    "to continue reading, subscribe",
    "this article is for subscribers",
    "already a subscriber",
    "sign in to read the full",
    "create a free account to continue",
    "you have reached your article limit",
    "available to subscribers only",
    "become a member to read",
    "register to continue reading",
)


def extract_article(markup: str, url: str = "", *, min_words: int = 60) -> ExtractedArticle:
    """Pull the readable body out of a news page.

    Uses the standard article containers first (JSON-LD articleBody, then
    ``<article>``/``articleBody``), falling back to a paragraph-density
    heuristic.  Returns an empty block list when the page is mostly navigation
    or a paywall, so callers can fall back to the feed summary.
    """
    result = ExtractedArticle()
    if not markup:
        return result
    lowered = markup.lower()

    result.title = (
        meta_content(markup, "og:title", "twitter:title")
        or _first_tag_text(markup, "h1")
        or _first_tag_text(markup, "title")
        or ""
    ).strip()
    result.image = meta_content(markup, "og:image", "twitter:image")
    result.site_name = meta_content(markup, "og:site_name")
    result.author = meta_content(markup, "author", "article:author", "parsely-author")
    result.published_hint = meta_content(
        markup, "article:published_time", "datePublished", "parsely-pub-date", "pubdate"
    )

    candidates: list[str] = []
    json_body = _json_ld_body(markup)
    if json_body:
        candidates.append(json_body)
    for pattern in (
        r'<article[^>]*>(.*?)</article>',
        r'<div[^>]+(?:id|class)=["\'][^"\']*article-?body[^"\']*["\'][^>]*>(.*?)</div>',
        r'<div[^>]+itemprop=["\']articleBody["\'][^>]*>(.*?)</div>',
        r'<main[^>]*>(.*?)</main>',
    ):
        for match in re.finditer(pattern, markup, re.I | re.S):
            candidates.append(match.group(1))

    best = ExtractedArticle()
    best_markup = ""
    best_score = 0.0
    for chunk in candidates:
        blocks = _clean_blocks(blocks_of(chunk))
        text = "\n\n".join(b.text for b in blocks)
        words = len(text.split())
        if words < min_words:
            continue
        score = words * (1.0 - _link_density(chunk))
        if score > best_score:
            best_score = score
            best.blocks = blocks
            best.word_count = words
            best_markup = chunk

    if not best.blocks:
        blocks = _clean_blocks(blocks_of(_strip_chrome(markup)))
        best.blocks = blocks
        best.word_count = len(" ".join(b.text for b in blocks).split())

    result.blocks = _strip_boilerplate(best.blocks, result.title or htmltext_safe_title(markup))
    result.word_count = len(" ".join(b.text for b in result.blocks).split())

    # Prefer images inside the winning article container so related-story
    # thumbnails, logos and promo cards do not end up in the gallery.
    result.images = image_urls(best_markup or markup, url)
    if not result.images:
        result.images = image_urls(markup, url)
    if result.image:
        if result.image.startswith("//"):
            result.image = "https:" + result.image
        elif result.image.startswith("/"):
            result.image = urljoin(url, result.image)
        if result.image not in result.images:
            result.images.insert(0, result.image)
    if not result.image and result.images:
        result.image = result.images[0]

    if not result.image:
        for block_source in candidates[:1] or [markup]:
            result.image = first_image(block_source)
            if result.image:
                break

    haystack = (result.text or "").lower()
    result.paywall = (
        result.word_count < 220 and any(p in lowered or p in haystack for p in _PAYWALL_PHRASES)
    ) or result.word_count == 0 and any(p in lowered for p in _PAYWALL_PHRASES)
    return result


_BYLINE_CREDIT = re.compile(r"^(by|words by|written by|photographs? by|illustration by|reporting by)\b", re.I)
_BOILERPLATE_START = re.compile(
    r"^(published|updated|last updated|image source|image caption|getty images|photograph:|photo:|file photo|"
    r"read more|related:|advertisement|share this|follow us|subscribe|sign up|download the app|"
    r"support our journalism|this article was originally published)\b",
    re.I,
)
_AUTHOR_BIO = re.compile(
    r"\b(is|was|has been)\b[^.]{0,90}\b(reporter|editor|correspondent|writer|producer|anchor|columnist|contributor|journalist)\b",
    re.I,
)
_COPYRIGHT = re.compile(r"(all rights reserved|copyright ©|© \d{4}|terms of service|privacy policy|cookie policy)", re.I)


def htmltext_safe_title(markup: str) -> str:
    return (_first_tag_text(markup, "h1") or meta_content(markup, "og:title") or "").strip()


def _strip_boilerplate(blocks: list[Block], title: str) -> list[Block]:
    """Drop bylines, author bios, photo credits and date stamps from the body."""
    cleaned: list[Block] = []
    normalised_title = re.sub(r"\W+", " ", (title or "").lower()).strip()
    for index, block in enumerate(blocks):
        text = block.text.strip()
        low = text.lower()
        if not text:
            continue
        candidate = re.sub(r"\W+", " ", low).strip()
        if normalised_title and candidate and (candidate in normalised_title or normalised_title in candidate) and len(candidate) > 18:
            continue
        if len(text) < 260 and _BOILERPLATE_START.match(text):
            continue
        if len(text) < 260 and _BYLINE_CREDIT.match(text):
            continue
        if index < 4 and len(text) < 320 and _AUTHOR_BIO.search(text) and text.count(".") <= 2:
            continue
        if len(text) < 200 and _COPYRIGHT.search(text):
            continue
        if len(text) < 160 and re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", text):
            continue
        if len(text) < 160 and re.search(r"preferred source|\badd\s+\w+\s+as\s+a?\s*source\b", low):
            continue
        if len(text) < 160 and re.match(r"^(share|tweet|email|print|comments?|advertisement)\b", low):
            continue
        if len(text) < 120 and text.endswith(("|", "•")) and text.count(" ") < 8:
            continue
        cleaned.append(block)
    return cleaned or blocks


def _clean_blocks(blocks: list[Block]) -> list[Block]:
    cleaned: list[Block] = []
    seen: set[str] = set()
    for block in blocks:
        text = block.text.strip()
        if len(text) < 25 and block.type not in ("h2", "h3"):
            continue
        key = text.lower()[:100]
        if key in seen:
            continue
        seen.add(key)
        low = text.lower()
        if any(
            bad in low
            for bad in (
                "cookie policy", "we use cookies", "sign up for our newsletter",
                "download our app", "all rights reserved", "follow us on",
                "share this article", "advertisement",
            )
        ) and len(text) < 200:
            continue
        if len(text.split()) < 6 and block.type == "p":
            continue
        cleaned.append(block)
    return cleaned


def _strip_chrome(markup: str) -> str:
    markup = re.sub(r"<(script|style|noscript|svg|nav|footer|header|aside|form)[^>]*>.*?</\1>", " ", markup, flags=re.I | re.S)
    return markup


def _link_density(markup: str) -> float:
    link_text = sum(len(m.group(1)) for m in re.finditer(r"<a[^>]*>(.*?)</a>", markup, re.I | re.S))
    total = len(re.sub(r"<[^>]+>", "", markup))
    return min(1.0, link_text / max(total, 1))


def _first_tag_text(markup: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", markup, re.I | re.S)
    return text_of(match.group(1)) if match else ""


def _json_ld_body(markup: str) -> str | None:
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', markup, re.I | re.S):
        raw = match.group(1).strip()
        try:
            import json

            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                body = node.get("articleBody")
                if isinstance(body, str) and len(body) > 200:
                    return "<p>" + body.replace("\n\n", "</p><p>") + "</p>"
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            elif isinstance(node, list):
                stack.extend(node)
    return None


# --------------------------------------------------------------------- prose
def sentences(text: str) -> list[str]:
    if not text:
        return []
    prepared = text.replace("\n", " ")
    for abbr in _ABBREVIATIONS:
        prepared = prepared.replace(abbr, abbr.replace(".", "\u2024"))
    parts = _SENTENCE_END.split(prepared)
    out: list[str] = []
    for part in parts:
        part = part.replace("\u2024", ".").strip()
        if len(part) < 30:
            if out and len(part) < 30:
                out[-1] = (out[-1] + " " + part).strip()
            continue
        out.append(part)
    return out


_STOP = set(
    """a an the and or but if while of to in on at by for with from as is are was were be been being
    this that these those it its it's their there here than then so such not no nor do does did done
    have has had having will would can could should may might must about into over under after before
    more most other some any all both each few many much own same very just also only even still yet
    said says say according new news report reports reported told tells like get got make made
    you your we our they them he she his her him i me my""".split()
)


def _tokenise(text: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z][A-Za-z'’-]{2,}", text.lower()) if w not in _STOP]


def keywords(text: str, limit: int = 8) -> list[str]:
    if not text:
        return []
    tokens = _tokenise(text)
    if not tokens:
        return []
    freq: dict[str, int] = {}
    for token in tokens:
        freq[token] = freq.get(token, 0) + 1
    # Reward capitalised multi-word entities roughly by re-checking the source.
    proper = {m.group(0).lower() for m in re.finditer(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b", text)}
    ranked = sorted(
        freq.items(),
        key=lambda kv: (kv[1] * (1.8 if kv[0] in proper else 1.0), len(kv[0])),
        reverse=True,
    )
    return [word for word, count in ranked[: limit * 2] if count > 0][:limit]


_FRAGMENT_HINT = re.compile(r"\b(receive[sd]?|acquire[sd]?|traded to|signs with)\s*:", re.I)


def is_fragment(sentence: str) -> bool:
    """True for list-item debris, live-blog stubs and stat lines."""
    text = sentence.strip()
    if len(text) < 40:
        return True
    if _FRAGMENT_HINT.search(text) or text.count(":") >= 2:
        return True
    if re.match(r"^\d{1,2}[.)]\s", text):
        return True
    digits = len(re.findall(r"\d", text))
    if digits and digits / max(len(text), 1) > 0.055:
        return True
    if re.search(r"\b(related|read more|advertisement|sign up|follow us|subscribe)\b", text, re.I) and len(text) < 180:
        return True
    if text.count('"') >= 6:
        return True
    return False


_US_DATE_STAMP = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s*\d{4}\s+at\s+\d{1,2}:\d{2}\s*(?:AM|PM)?\s*(?:UTC|GMT|ET|EST|EDT|BST)?\b",
    re.I,
)


def _strip_leading_widgets(text: str) -> str:
    """Drop a leading stack of trending links/headline teasers before a body.

    Yahoo, MSN and several local-news templates put a "more headlines" list at
    the top of the page, and the extractor keeps those short lines.  When the
    first real paragraph is far enough down, cut the teaser stack instead of
    letting it leak into the summary.
    """
    if not text:
        return ""
    text = _US_DATE_STAMP.sub(" ", text)
    parts = [part.strip() for part in re.split(r"\n+", text) if part.strip()]
    if len(parts) < 3:
        return text
    index = 0
    while index < len(parts) and index < 10:
        part = parts[index]
        if len(part) >= 100 or (len(part) >= 60 and part.endswith((".", "!", "?", "”", '"'))):
            break
        if part.endswith(":"):
            break
        index += 1
    if index >= 2 and len(parts) - index >= 2:
        return "\n\n".join(parts[index:])
    return text


def clean_blocks(blocks: list[dict]) -> list[dict]:
    """Remove leading widget links and stray timestamps from stored blocks."""
    cleaned: list[dict] = []
    for block in blocks or []:
        text = (block.get("text") or "").strip()
        if not text:
            continue
        if len(text) < 90 and (_US_DATE_STAMP.search(text) or _DATE_STAMP.search(text)):
            continue
        cleaned.append(block)
    # A run of short list items before any paragraph is a navigation/trending
    # list, not article content.
    index = 0
    while index < len(cleaned) and index < 10:
        block = cleaned[index]
        text = (block.get("text") or "").strip()
        if block.get("type") == "li" and len(text) < 100:
            index += 1
            continue
        break
    if index >= 2 and len(cleaned) - index >= 1:
        cleaned = cleaned[index:]
    # A short headline stack before the first long paragraph.
    index = 0
    while index < len(cleaned) and index < 6:
        block = cleaned[index]
        text = (block.get("text") or "").strip()
        if len(text) >= 100:
            break
        if block.get("type") in ("h2", "h3", "h4") or text.endswith(":"):
            break
        if len(text) >= 60 and text.endswith((".", "!", "?", "”", '"')):
            break
        index += 1
    if index >= 2 and len(cleaned) - index >= 2:
        cleaned = cleaned[index:]
    return cleaned


def strip_boilerplate(text: str) -> str:
    """Remove bylines, widget junk and date stamps from stored article text."""
    if not text:
        return ""
    cleaned = _strip_leading_widgets(text)
    cleaned = _PHOTO_CREDIT.sub("", cleaned.strip())
    cleaned = _WIDGET_JUNK.sub(" ", cleaned)
    cleaned = _SUBSCRIPTION_CTA.sub(" ", cleaned)
    cleaned = _DATE_STAMP.sub(" ", cleaned)
    cleaned = _strip_byline(cleaned)
    kept = []
    for sentence in sentences(cleaned):
        if len(sentence) < 320 and _AUTHOR_BIO.search(sentence) and sentence.count(".") <= 1:
            continue
        if "preferred source" in sentence.lower():
            continue
        kept.append(sentence)
    return " ".join(kept).strip()


def summarize(text: str, max_sentences: int = 3, max_chars: int = 700) -> str:
    """Extractive summary: keep the most central sentences, in order."""
    if not text:
        return ""
    candidates = [
        s for s in sentences(text)
        if 45 <= len(s) <= 420 and not is_fragment(s)
        and not _US_DATE_STAMP.search(s)
        and not re.search(r"\b(?:NFL|NBA|MLB|NHL)\b.*\b(?:grades|tracker|recap)\b", s, re.I)
    ]
    if not candidates:
        return truncate_words(text, max_chars // 6)
    tokens_per_sentence = [set(_tokenise(s)) for s in candidates]
    doc_freq: dict[str, int] = {}
    for tokens in tokens_per_sentence:
        for token in tokens:
            doc_freq[token] = doc_freq.get(token, 0) + 1
    total = len(candidates)
    scores: list[float] = []
    for index, tokens in enumerate(tokens_per_sentence):
        if not tokens:
            scores.append(0.0)
            continue
        score = sum(math.log((total + 1) / (doc_freq[t] + 0.5)) for t in tokens) / (len(tokens) ** 0.65)
        if index < 3:
            score *= 1.25
        if re.search(r"\d", candidates[index]):
            score *= 1.07
        if candidates[index].lstrip().startswith(("\"", "“")):
            score *= 0.9
        scores.append(score)
    order = sorted(range(total), key=lambda i: scores[i], reverse=True)
    chosen: list[int] = []
    for index in order:
        if len(chosen) >= max_sentences:
            break
        if any(_jaccard(tokens_per_sentence[index], tokens_per_sentence[j]) > 0.55 for j in chosen):
            continue
        chosen.append(index)
    chosen.sort()
    summary = " ".join(candidates[i] for i in chosen).strip()
    if len(summary) > max_chars:
        summary = truncate_words(summary, max_chars // 6) + "…"
    return summary


def key_points(text: str, limit: int = 4) -> list[str]:
    """Short factual bullets pulled straight from the article."""
    if not text:
        return []
    cands = [s for s in sentences(text) if 40 <= len(s) <= 260 and not is_fragment(s)]
    if not cands:
        return []
    scored = []
    for index, sentence in enumerate(cands):
        score = 0.0
        if re.search(r"\b\d", sentence):
            score += 1.4
        if re.search(r"\b(percent|million|billion|thousand|first|new|announced|approved|ruled|won|lost|launched|agreed|signed)\b", sentence, re.I):
            score += 1.0
        if index < 2:
            score += 0.8
        if "?" in sentence:
            score -= 0.6
        score += min(len(sentence), 200) / 400
        scored.append((score, index, sentence))
    scored.sort(reverse=True)
    picked = []
    for score, index, sentence in scored:
        if len(picked) >= limit:
            break
        if any(_jaccard(set(_tokenise(sentence)), set(_tokenise(p))) > 0.5 for _, p in picked):
            continue
        picked.append((index, sentence))
    picked.sort()
    return [s.rstrip(".") + "." if not s.endswith((".", "!", "?", "…")) else s for _, s in picked]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def truncate_words(text: str, words: int = 40) -> str:
    parts = (text or "").split()
    if len(parts) <= words:
        return (text or "").strip()
    return " ".join(parts[:words]).rstrip(",;:") + "…"


def reading_minutes(text: str, words_per_minute: int = 225) -> int:
    words = len((text or "").split())
    return max(1, round(words / words_per_minute)) if words else 1


def word_count(text: str) -> int:
    return len((text or "").split())


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def clean_author(value: str | None) -> str | None:
    """Feed bylines are often junk: URLs, handles, whole paragraphs."""
    text = (value or "").strip()
    if not text:
        return None
    if re.search(r"https?://|www\.|@|\b\.(com|co|org|net|uk)\b", text, re.I):
        return None
    if len(text) > 80:
        return None
    letters = sum(1 for char in text if char.isalpha())
    if letters / max(len(text), 1) < 0.6:
        return None
    text = re.sub(r"^(by|words by|written by|posted by)\s+", "", text, flags=re.I).strip()
    return text[:120] or None


def clean_title(title: str) -> str:
    title = title or ""
    if "<" in title and ">" in title:
        title = text_of(title)
    title = html_lib.unescape(title).strip()
    title = _WS.sub(" ", title)
    # Strip trailing " - Site Name" / " | Site Name" that feeds love to add.
    title = re.sub(r"\s+[|\-–—]\s+[A-Z][\w .&']{2,28}$", "", title).strip()
    return title


_BYLINE_ROLE = re.compile(
    r"\b(reporter|correspondent|editor|writer|producer|journalist|anchor|columnist)\b", re.I
)
_BYLINE_REJECT = re.compile(r"\b(said|says|told|according|argued|wrote|reported)\b", re.I)
_BYLINE_STOP = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "contrast", "comparison",
    "then", "now", "next", "far", "law", "design", "default", "definition",
    "extension", "the", "a", "an", "and", "using", "adding", "making", "doing",
    "midnight", "noon", "2024", "2025", "2026", "2027",
}


def _strip_byline(text: str) -> str:
    """Remove "By First Last, Role and Someone Else, Role" anywhere in a summary.

    Bylines are frequently glued onto the end of feed descriptions, sometimes
    without a space ("ByKali Hays"), so this scans for the shape rather than
    anchoring to the start.
    """
    for match in list(re.finditer(r"\bBy\s?[A-Z][a-z]", text))[:3]:
        start = match.start()
        window = text[start:start + 190]
        roles = list(_BYLINE_ROLE.finditer(window))
        if not roles:
            continue
        prefix = window[: roles[-1].start()]
        if "," not in prefix and " and " not in prefix:
            continue
        if _BYLINE_REJECT.search(prefix):
            continue
        first_token = re.match(r"By\s?([A-Za-z0-9'’\-]+)", window)
        if first_token and first_token.group(1).lower() in _BYLINE_STOP:
            continue
        before = text[:start].rstrip()
        after = text[start + roles[-1].end():].lstrip(" .,;:–—-")
        if before and after and before[-1] not in ".!?" and after[0].isupper():
            text = f"{before}. {after}"
        else:
            text = f"{before} {after}"
        text = re.sub(r"\s{2,}", " ", text)
    return text


_TRAILING_CTA = re.compile(
    r"\s*(continue reading|read more|read the full (story|article)|sign up for our newsletter)\s*:?\s*"
    r"(https?://\S+)?[^.]*$",
    re.I,
)
_SUBSCRIPTION_CTA = re.compile(
    r"(?:^|\s)(?:access|join|subscribe|sign up|already a subscriber|log in to continue|click here)"
    r"[^.]{0,240}(?:subscriber|subscription|newsletter|premium|\bbeat\b|features)[^.]*\.",
    re.I,
)
_WIDGET_JUNK = re.compile(
    r"(add\s+\S+\s+as\s+(a\s+)?preferred source|preferred source|advertisement|sponsored content)",
    re.I,
)
_DATE_STAMP = re.compile(
    r"\b\d{1,2}\s+[A-Z][a-z]+\s+\d{4},?\s+\d{1,2}:\d{2}\s*(GMT|UTC|BST|EST|EDT)?\b"
)


_PHOTO_CREDIT = re.compile(
    r"^(?:photo|image|picture|credit|illustration)\s*(?:by|:)?\s*[^.]{0,90}?"
    r"(?:getty images|associated press|\bap\b|reuters|afp|shutterstock|unsplash|epa)\s*[.·—–-]?\s*",
    re.I,
)


def clean_summary(text: str, limit: int = 520) -> str:
    plain = text_of(text or "")
    plain = re.sub(r"\s+", " ", plain).strip()
    plain = _PHOTO_CREDIT.sub("", plain).strip()
    for prefix in ("Read more", "Continue reading", "Watch:", "Listen:"):
        if plain.startswith(prefix):
            plain = plain[len(prefix):].lstrip(" :–-")
    plain = _WIDGET_JUNK.sub(" ", plain)
    plain = _DATE_STAMP.sub(" ", plain)
    plain = _strip_byline(plain)
    plain = _TRAILING_CTA.sub("", plain).strip()
    plain = _SUBSCRIPTION_CTA.sub(" ", plain).strip()
    plain = re.sub(r"\s{2,}", " ", plain)
    if len(plain) > limit:
        plain = truncate_words(plain, limit // 6)
    return plain


def simplify(text: str, max_sentences: int = 6) -> str:
    """A 'plain English' pass that only re-orders existing sentences.

    We pick short, low-jargon sentences and drop ones dense with clauses.  This
    is deliberately not an LLM: it cannot hallucinate, and the UI labels it as
    a readability aid rather than an AI summary.
    """
    cands = [s for s in sentences(text) if 30 <= len(s) <= 180]
    if not cands:
        return summarize(text, max_sentences)
    def complexity(sentence: str) -> float:
        words = sentence.split()
        long_words = sum(1 for w in words if len(w) > 10)
        commas = sentence.count(",")
        return long_words / max(len(words), 1) + commas * 0.04
    ranked = sorted(enumerate(cands), key=lambda pair: (complexity(pair[1]), pair[0]))
    chosen = sorted(ranked[:max_sentences])
    return " ".join(sentence for _, sentence in chosen)
