"""Feed parsing for RSS 2.0, RSS 1.0 (RDF), Atom and JSON Feed.

Real feeds are messy: undeclared HTML entities, CDATA, namespaces invented by
the CMS, missing GUIDs, timestamps in six formats.  The parser is therefore
defensive: strict XML first, a regex fallback second, and it always reports
*why* a feed failed so the health dashboard can be specific.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from . import htmltext
from .logging_setup import get_logger

log = get_logger("feeds")

_ENTITY_RE = re.compile(r"&([a-zA-Z][a-zA-Z0-9]{1,30});")
_XML_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
_ITEM_RE = re.compile(r"<item[\s>].*?</item>", re.I | re.S)
_ENTRY_RE = re.compile(r"<entry[\s>].*?</entry>", re.I | re.S)
_TAG_RE = re.compile(r"<([\w:.-]+)([^>]*)>(.*?)</\1>", re.I | re.S)


class FeedError(Exception):
    def __init__(self, message: str, *, blocked: bool = False, status: int | None = None):
        super().__init__(message)
        self.blocked = blocked
        self.status = status


@dataclass
class FeedItem:
    guid: str
    title: str
    link: str
    summary_html: str = ""
    content_html: str = ""
    author: str | None = None
    published_raw: str | None = None
    updated_raw: str | None = None
    image: str | None = None
    categories: list[str] = field(default_factory=list)
    is_paywalled: bool = False

    @property
    def best_html(self) -> str:
        return self.content_html if len(self.content_html) > len(self.summary_html) else self.summary_html


@dataclass
class ParsedFeed:
    title: str
    items: list[FeedItem]
    kind: str = "rss"


def parse_feed(text: str, url: str = "") -> ParsedFeed:
    if not text or not text.strip():
        raise FeedError("Empty response body")
    stripped = text.lstrip("\ufeff \t\r\n")
    lowered = stripped[:4000].lower()

    if stripped.startswith("{") or stripped.startswith("["):
        return _parse_json_feed(stripped, url)

    if "html" in lowered[:200] and "<rss" not in lowered and "<feed" not in lowered and "<rdf" not in lowered:
        raise FeedError(_describe_html_block(reason=lowered), blocked=_looks_blocked(lowered))

    cleaned = _sanitize_entities(stripped)
    try:
        root = ET.fromstring(cleaned)
        return _parse_xml(root, url)
    except ET.ParseError as exc:
        # Truncated or malformed XML: try to salvage items with regex.
        items = _regex_items(stripped)
        if items:
            log.debug("recovered %d items from malformed feed %s (%s)", len(items), url, exc)
            return ParsedFeed(title="", items=items, kind="rss")
        if "<rss" in lowered or "<feed" in lowered or "<rdf" in lowered:
            raise FeedError(f"Malformed XML: {exc}") from exc
        raise FeedError("Response is not a recognised feed") from exc


def _describe_html_block(reason: str) -> str:
    if _looks_blocked(reason):
        return "Blocked by a network filter (HTML block page returned instead of a feed)"
    if "captcha" in reason or "cloudflare" in reason:
        return "Feed is behind a bot-protection challenge"
    if "404" in reason or "not found" in reason:
        return "Feed URL returned a 404 page"
    return "Server returned HTML instead of a feed"


def _looks_blocked(text: str) -> bool:
    needles = (
        "for your safety this page has been restricted",
        "access denied",
        "blocked by",
        "web filter",
        "pornography",
        "qustodio",
    )
    return any(n in text for n in needles)


def _sanitize_entities(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in _XML_ENTITIES:
            return match.group(0)
        import html

        unescaped = html.unescape(match.group(0))
        if unescaped == match.group(0):
            return f"&amp;{name};"
        return unescaped

    return _ENTITY_RE.sub(repl, text)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower() if "}" in tag else tag.lower()


def _namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def _text(element: ET.Element) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _children(element: ET.Element, *names: str) -> list[ET.Element]:
    wanted = {n.lower() for n in names}
    return [child for child in element if _local(child.tag) in wanted]


def _first(element: ET.Element, *names: str) -> ET.Element | None:
    for child in element:
        if _local(child.tag) in {n.lower() for n in names}:
            return child
    return None


def _parse_xml(root: ET.Element, url: str) -> ParsedFeed:
    root_name = _local(root.tag)
    title_el = _first(root, "title")
    feed_title = _text(title_el) if root_name in ("rss", "feed", "rdf") else ""

    entries: list[ET.Element] = []
    kind = "rss"
    if root_name == "feed":
        kind = "atom"
        entries = [child for child in root if _local(child.tag) == "entry"]
    else:
        channel = _first(root, "channel")
        container = channel if channel is not None else root
        entries = [child for child in container if _local(child.tag) == "item"]
        if not entries:
            entries = [el for el in root.iter() if _local(el.tag) == "item"]
        if not title_el and channel is not None:
            feed_title = _text(_first(channel, "title"))
        if kind != "atom" and _namespace(root.tag).endswith("rdf-syntax-ns#"):
            kind = "rdf"
    items: list[FeedItem] = []
    for entry in entries:
        item = _parse_item(entry, url, kind)
        if item is not None:
            items.append(item)

    # Feeds sometimes nest items in a namespace we did not guess.
    if not items:
        for entry in root.iter():
            if _local(entry.tag) in ("item", "entry") and entry is not root:
                item = _parse_item(entry, url, kind)
                if item is not None:
                    items.append(item)

    if not items:
        raise FeedError("Feed contains no items")
    return ParsedFeed(title=htmltext.clean_title(feed_title) if feed_title else "", items=items, kind=kind)


def _parse_item(entry: ET.Element, feed_url: str, kind: str) -> FeedItem | None:
    title = htmltext.clean_title(_text(_first(entry, "title")))
    link = ""
    for child in entry:
        local = _local(child.tag)
        if local == "link":
            href = child.get("href") or ""
            rel = (child.get("rel") or "alternate").lower()
            if href and rel in ("alternate", "self", ""):
                link = href
                break
            if href and not link:
                link = href
        elif local == "guid" and not link:
            candidate = _text(child)
            if candidate.startswith("http"):
                link = candidate
        elif local in ("origlink", "feedburner:origlink") and not link:
            link = _text(child)
    if not link:
        link = _text(_first(entry, "link", "url", "id"))
    if not link:
        link = entry.get("rdf:about") or entry.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about") or ""

    guid = _text(_first(entry, "guid", "id")) or link
    if not guid:
        import hashlib

        guid = hashlib.sha1((title + (link or feed_url)).encode()).hexdigest()

    summary_parts: list[str] = []
    content_parts: list[str] = []
    for child in entry:
        local = _local(child.tag)
        if local in ("description", "summary", "subtitle"):
            summary_parts.append(_text(child))
        elif local in ("encoded", "content"):
            namespace = _namespace(child.tag)
            if local == "content" and namespace and "search" in namespace:
                continue
            content_parts.append(_text(child))
        elif local == "abstract":
            summary_parts.append(_text(child))

    author = _text(_first(entry, "author", "creator", "bylines"))
    if not author:
        author_el = _first(entry, "author")
        if author_el is not None:
            author = _text(_first(author_el, "name"))
    author = re.sub(r"\s+", " ", author).strip()
    if author.lower().startswith("by "):
        author = author[3:].strip()
    author = htmltext.clean_author(author) or ""

    published = _text(_first(entry, "pubdate", "published", "date", "issued", "created", "datepublished"))
    updated = _text(_first(entry, "updated", "modified", "lastmod", "datemodified"))

    categories = []
    for child in entry:
        if _local(child.tag) == "category":
            value = child.get("term") or _text(child)
            if value:
                categories.append(htmltext.text_of(value)[:60])

    image = _image_from_entry(entry)
    content_html = "\n".join(part for part in content_parts if part)
    summary_html = "\n".join(part for part in summary_parts if part)
    if not image:
        image = htmltext.first_image(content_html) or htmltext.first_image(summary_html)

    paywalled = "paywall" in (content_html + summary_html).lower() and len(content_html) < 800

    if not title and not link:
        return None
    return FeedItem(
        guid=guid.strip()[:900],
        title=title[:400] or "(untitled)",
        link=link.strip()[:2000],
        summary_html=summary_html,
        content_html=content_html,
        author=author[:200] or None,
        published_raw=published or None,
        updated_raw=updated or None,
        image=image,
        categories=categories[:8],
        is_paywalled=paywalled,
    )


def _image_from_entry(entry: ET.Element) -> str | None:
    for child in entry.iter():
        local = _local(child.tag)
        if local in ("content", "thumbnail"):
            url = child.get("url")
            medium = (child.get("medium") or "").lower()
            content_type = (child.get("type") or "").lower()
            if url and (medium == "image" or content_type.startswith("image") or local == "thumbnail"):
                return url
        elif local == "image":
            href = child.get("href") or _text(child)
            if href.startswith("http"):
                return href
        elif local == "enclosure":
            url = child.get("url")
            content_type = (child.get("type") or "").lower()
            if url and content_type.startswith("image"):
                return url
    return None


def _regex_items(text: str) -> list[FeedItem]:
    items: list[FeedItem] = []
    for pattern in (_ITEM_RE, _ENTRY_RE):
        for chunk in pattern.findall(text):
            inner = re.sub(r"^<(?:item|entry)\b[^>]*>", "", chunk, flags=re.I)
            inner = re.sub(r"</(?:item|entry)>\s*$", "", inner, flags=re.I)
            fields: dict[str, str] = {}
            for match in _TAG_RE.finditer(inner):
                name = match.group(1).split(":")[-1].lower()
                if name in fields:
                    continue
                fields[name] = match.group(3)
            title = htmltext.clean_title(htmltext.text_of(fields.get("title", "")))
            link = ""
            link_match = re.search(r'<link[^>]*href=["\']([^"\']+)["\']', inner, re.I)
            if link_match:
                link = link_match.group(1)
            if not link:
                link = htmltext.text_of(fields.get("link", "")).strip()
            if not link:
                guid_text = htmltext.text_of(fields.get("guid", "")).strip()
                link = guid_text if guid_text.startswith("http") else ""
            body = fields.get("encoded") or fields.get("content") or fields.get("description") or fields.get("summary") or ""
            published = fields.get("pubdate") or fields.get("published") or fields.get("date") or fields.get("updated")
            if not title and not link:
                continue
            guid = htmltext.text_of(fields.get("guid", "")).strip() or link or title
            items.append(
                FeedItem(
                    guid=guid[:900],
                    title=title[:400] or "(untitled)",
                    link=link[:2000],
                    content_html=body,
                    summary_html=fields.get("description", ""),
                    published_raw=published,
                    image=htmltext.first_image(body),
                )
            )
    return items


def _parse_json_feed(text: str, url: str) -> ParsedFeed:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FeedError(f"Invalid JSON feed: {exc}") from exc
    if isinstance(data, list):
        data = {"items": data}
    if not isinstance(data, dict) or "items" not in data:
        raise FeedError("JSON document is not a feed")
    items: list[FeedItem] = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        content = raw.get("content_html") or raw.get("content_text") or ""
        summary = raw.get("summary") or ""
        if raw.get("image") and not htmltext.first_image(content):
            content = f'<p><img src="{raw["image"]}" alt=""></p>' + content
        authors = raw.get("authors") or raw.get("author") or {}
        if isinstance(authors, list):
            author = ", ".join(a.get("name", "") for a in authors if isinstance(a, dict))
        elif isinstance(authors, dict):
            author = authors.get("name", "")
        else:
            author = str(authors or "")
        items.append(
            FeedItem(
                guid=str(raw.get("id") or raw.get("url") or hash(raw))[:900],
                title=htmltext.clean_title(raw.get("title") or "(untitled)")[:400],
                link=raw.get("url") or raw.get("external_url") or "",
                summary_html=summary,
                content_html=content,
                author=author or None,
                published_raw=raw.get("date_published"),
                updated_raw=raw.get("date_modified"),
                image=raw.get("image"),
            )
        )
    if not items:
        raise FeedError("JSON feed contains no items")
    return ParsedFeed(title=data.get("title", ""), items=items, kind="json")
