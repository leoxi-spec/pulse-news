"""Citation formatting for school work (MLA 9, APA 7, Chicago, Harvard, BibTeX)."""
from __future__ import annotations

import re
from datetime import datetime

from .timeutil import now, parse_iso

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _author_parts(author: str | None) -> tuple[str, str, str]:
    """Best-effort split of a byline into (first, last, full)."""
    if not author:
        return "", "", ""
    cleaned = re.sub(r"^(by|written by|words by)\s+", "", author.strip(), flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned)
    if "," in cleaned:
        last, first = [part.strip() for part in cleaned.split(",", 1)]
        return first, last, cleaned
    parts = cleaned.split()
    if len(parts) == 1:
        return "", parts[0], parts[0]
    return " ".join(parts[:-1]), parts[-1], cleaned


def _date_bits(article: dict) -> tuple[str, str, str, str]:
    published = parse_iso(article.get("published_at"))
    if published is None:
        return "", "", "", ""
    return str(published.year), _MONTHS[published.month - 1], str(published.day), published


def _accessed() -> datetime:
    return now()


def _key(article: dict) -> str:
    _, last, _ = _author_parts(article.get("author"))
    surname = re.sub(r"[^A-Za-z]", "", last) or re.sub(r"[^A-Za-z]", "", article.get("source_name") or "source")
    year, _, _, _ = _date_bits(article)
    slug = re.sub(r"\W+", "", (article.get("title") or "").split()[0] if article.get("title") else "story")
    return f"{surname.lower()}{year or 'nd'}{slug.lower()[:14]}"


def format_citation(article: dict, style: str = "mla") -> str:
    first, last, full = _author_parts(article.get("author"))
    title = (article.get("title") or "Untitled").strip()
    outlet = article.get("source_name") or ""
    url = article.get("url") or ""
    year, month, day, dt = _date_bits(article)
    accessed = _accessed()
    style = (style or "mla").lower()

    if style in ("mla", "mla9"):
        author = f"{last}, {first}." if last and first else (f"{last}." if last else "")
        date = f"{day} {month} {year}" if dt else "n.d."
        return _clean(
            f"{author} \"{title}.\" {outlet}, {date}, {url}. Accessed {accessed.day} {_MONTHS[accessed.month - 1]} {accessed.year}."
        )

    if style in ("apa", "apa7"):
        if last and first:
            author = f"{last}, {first[0]}."
        elif last:
            author = f"{last}."
        else:
            author = f"{outlet}."
        date = f"({year}, {month} {day})" if dt else "(n.d.)"
        return _clean(f"{author} {date}. {title}. {outlet}. {url}")

    if style == "chicago":
        author = f"{last}, {full.replace(last, '').strip()}." if last and first else (f"{last}." if last else "")
        date = f"{month} {day}, {year}" if dt else "n.d."
        return _clean(f"{author} \"{title}.\" {outlet}, {date}. {url}.")

    if style == "harvard":
        author = f"{last}, {first[0]}." if last and first else (f"{last}." if last else f"{outlet}.")
        date = year if year else "n.d."
        return _clean(
            f"{author} ({date}) '{title}', {outlet}, {day} {month}. Available at: {url} "
            f"(Accessed: {accessed.day} {_MONTHS[accessed.month - 1]} {accessed.year})."
        )

    if style == "bibtex":
        fields = [
            f"  author = {{{full or outlet}}}",
            f"  title = {{{title}}}",
            f"  year = {{{year or 'n.d.'}}}",
            f"  publisher = {{{outlet}}}",
            f"  url = {{{url}}}",
            f"  urldate = {{{accessed.date().isoformat()}}}",
        ]
        return "@misc{" + _key(article) + ",\n" + ",\n".join(fields) + "\n}"

    if style == "plain":
        date = f"{day} {month} {year}" if dt else "date unknown"
        return _clean(f"{title} — {outlet}, {date}. {url}")

    return format_citation(article, "mla")


def available_styles() -> list[dict]:
    return [
        {"id": "mla", "label": "MLA 9", "hint": "Most US high schools & humanities"},
        {"id": "apa", "label": "APA 7", "hint": "Psychology, education, social sciences"},
        {"id": "chicago", "label": "Chicago", "hint": "History & some humanities"},
        {"id": "harvard", "label": "Harvard", "hint": "Common in the UK & Australia"},
        {"id": "bibtex", "label": "BibTeX", "hint": "LaTeX / reference managers"},
        {"id": "plain", "label": "Plain text", "hint": "Quick copy for notes"},
    ]


def all_citations(article: dict) -> dict[str, str]:
    return {style["id"]: format_citation(article, style["id"]) for style in available_styles()}


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" ,", ",").replace(" .", ".").replace("..", ".")
    return text.strip()
