"""Date/time helpers.

Getting dates right is the whole ballgame for a news app: every article keeps
the publisher's own timestamp string, a normalised UTC timestamp, and a
confidence marker so the UI can say "published 2h ago" *or* "first seen 2h ago"
instead of quietly inventing a date.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime

UTC = timezone.utc
_FUTURE_SKEW = timedelta(minutes=5)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DATE_ONLY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_COMPACT = re.compile(r"^(\d{4})(\d{2})(\d{2})(?:T?(\d{2})(\d{2})(\d{2})?)?(Z|[+-]\d{4})?$")
_SLASH_DMY = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})(?:\s+(\d{1,2}):(\d{2}))?$")
_WORDY = re.compile(
    r"^(?:[A-Za-z]{3,9},?\s+)?(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\s*(?:(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?)?\s*([A-Z]{2,4}|[+-]\d{4})?$",
    re.I,
)


def now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime | None = None) -> str:
    value = dt or now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_date(value: str | None, reference: datetime | None = None) -> tuple[datetime | None, str, str | None]:
    """Parse a publisher timestamp.

    Returns (utc datetime, confidence, raw).  Confidence is one of
    ``exact``, ``day``, ``inferred`` or ``unknown``.  Dates absurdly far in the
    future are treated as suspicious and clamped to the fetch time.
    """
    if not value:
        return None, "unknown", None
    raw = str(value).strip()
    if not raw:
        return None, "unknown", None
    reference = reference or now()

    candidates = [raw]
    # "2024-05-02T10:30:00.000Z" is handled by fromisoformat; some feeds put the
    # timezone name in brackets or append extra offsets.
    cleaned = re.sub(r"\s*\([A-Za-z]+\)\s*$", "", raw)
    if cleaned != raw:
        candidates.append(cleaned)

    parsed: datetime | None = None
    confidence = "unknown"

    for text in candidates:
        parsed, confidence = _try_parse(text)
        if parsed is not None:
            break

    if parsed is None:
        return None, "unknown", raw

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    parsed = parsed.astimezone(UTC)

    if parsed > reference + _FUTURE_SKEW:
        # Publishers do get this wrong: feeds with a bogus timezone (or a clock
        # set a day ahead) produce timestamps in the future. Rather than showing
        # a story as "published in 7 hours", clamp to the moment we saw it and
        # mark the date as inferred.
        parsed = reference
        confidence = "inferred"
    if parsed.year < 1990:
        return None, "unknown", raw
    return parsed, confidence, raw


def _try_parse(text: str) -> tuple[datetime | None, str]:
    text = text.strip()
    if not text:
        return None, "unknown"

    # Unix timestamps (seconds or milliseconds)
    if re.fullmatch(r"\d{10}|\d{13}", text):
        seconds = int(text[:10])
        return datetime.fromtimestamp(seconds, UTC), "exact"

    match = _DATE_ONLY.match(text)
    if match:
        year, month, day = (int(x) for x in match.groups())
        return _safe_dt(year, month, day), "day"

    match = _COMPACT.match(text)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        hour = int(match.group(4) or 0)
        minute = int(match.group(5) or 0)
        second = int(match.group(6) or 0)
        tz_part = match.group(7)
        dt = _safe_dt(year, month, day, hour, minute, second)
        if dt is None:
            return None, "unknown"
        if tz_part and tz_part != "Z":
            dt = _apply_offset(dt, tz_part)
        return dt, "exact" if match.group(4) else "day"

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        has_time = "T" in text or " " in text.strip()
        conf = "exact" if has_time else "day"
        return parsed, conf
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(text)
        if parsed is not None:
            return parsed, "exact"
    except (TypeError, ValueError, IndexError, OverflowError):
        pass

    match = _SLASH_DMY.match(text)
    if match:
        d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        hour = int(match.group(4) or 0)
        minute = int(match.group(5) or 0)
        # Prefer day-first (most of the world) unless impossible.
        dt = _safe_dt(y, m, d, hour, minute)
        if dt is None:
            dt = _safe_dt(y, d, m, hour, minute)
        return dt, "exact" if match.group(4) else "day"

    match = _WORDY.match(text)
    if match:
        day = int(match.group(1))
        month = _MONTHS.get(match.group(2)[:4].lower().rstrip("."), _MONTHS.get(match.group(2)[:3].lower()))
        year = int(match.group(3))
        hour = int(match.group(4) or 0)
        minute = int(match.group(5) or 0)
        second = int(match.group(6) or 0)
        ampm = (match.group(7) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if month and 1 <= hour <= 23:
            dt = _safe_dt(year, month, day, hour, minute, second)
            tz_part = match.group(8)
            if dt and tz_part:
                if re.fullmatch(r"[+-]\d{4}", tz_part):
                    dt = _apply_offset(dt, tz_part)
                else:
                    abbrev = {"EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7, "MDT": -6,
                              "PST": -8, "PDT": -7, "GMT": 0, "UTC": 0, "BST": 1, "CET": 1,
                              "CEST": 2, "IST": 5, "JST": 9, "AEST": 10, "AEDT": 11}.get(tz_part.upper())
                    if abbrev is not None:
                        dt = dt - timedelta(hours=abbrev)
            return dt, "exact" if match.group(4) else "day"

    # "2 hours ago" style relative timestamps in some feeds
    rel = re.match(r"^(\d+)\s*(minute|min|hour|hr|day|week)s?\s+ago$", text, re.I)
    if rel:
        amount = int(rel.group(1))
        unit = rel.group(2).lower()
        delta = {
            "minute": timedelta(minutes=amount), "min": timedelta(minutes=amount),
            "hour": timedelta(hours=amount), "hr": timedelta(hours=amount),
            "day": timedelta(days=amount), "week": timedelta(weeks=amount),
        }[unit]
        return now() - delta, "inferred"

    return None, "unknown"


def _safe_dt(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime | None:
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    except ValueError:
        return None


def _apply_offset(dt: datetime, offset: str) -> datetime:
    sign = 1 if offset[0] == "+" else -1
    hours = int(offset[1:3])
    minutes = int(offset[3:5]) if len(offset) >= 5 else 0
    return dt - sign * timedelta(hours=hours, minutes=minutes)


def day_key(dt: datetime | None = None) -> str:
    return (dt or now()).astimezone(UTC).date().isoformat()


def start_of_day(days_ago: int = 0) -> str:
    target = (now() - timedelta(days=days_ago)).date()
    return iso(datetime.combine(target, time.min, tzinfo=UTC))


def relative(dt: datetime | str | None, *, reference: datetime | None = None) -> str:
    parsed = parse_iso(dt) if isinstance(dt, str) else dt
    if parsed is None:
        return ""
    reference = reference or now()
    seconds = (reference - parsed).total_seconds()
    future = seconds < 0
    seconds = abs(seconds)
    if seconds < 90:
        return "just now"
    elif seconds < 150:
        label = "2 min"
    elif seconds < 3600:
        label = f"{int(seconds // 60)} min"
    elif seconds < 5400:
        label = "1 hr"
    elif seconds < 86400:
        label = f"{int(seconds // 3600)} hr"
    elif seconds < 172800:
        label = "1 day"
    elif seconds < 604800:
        label = f"{int(seconds // 86400)} days"
    elif seconds < 2629800:
        label = f"{int(seconds // 604800)} wk"
    elif seconds < 31557600:
        label = f"{int(seconds // 2629800)} mo"
    else:
        label = f"{int(seconds // 31557600)} yr"
    if label == "just now":
        return label
    return f"in {label}" if future else f"{label} ago"


def absolute(dt: datetime | str | None, *, with_time: bool = True) -> str:
    parsed = parse_iso(dt) if isinstance(dt, str) else dt
    if parsed is None:
        return ""
    if with_time:
        return parsed.strftime("%b %-d, %Y · %H:%M UTC") if _supports_dash(parsed) else parsed.strftime("%b %d, %Y · %H:%M UTC")
    return parsed.strftime("%b %-d, %Y") if _supports_dash(parsed) else parsed.strftime("%b %d, %Y")


def _supports_dash(dt: datetime) -> bool:
    return not __import__("sys").platform.startswith("win")


def machine(dt: datetime | str | None) -> str:
    parsed = parse_iso(dt) if isinstance(dt, str) else dt
    return iso(parsed) if parsed else ""


def minutes_since(dt: datetime | str | None) -> float:
    parsed = parse_iso(dt) if isinstance(dt, str) else dt
    if parsed is None:
        return 10**9
    return (now() - parsed).total_seconds() / 60.0


def freshness(dt: datetime | str | None) -> str:
    """Coarse freshness bucket used by ranking and dashboards."""
    age = minutes_since(dt)
    if age <= 45:
        return "breaking"
    if age <= 240:
        return "fresh"
    if age <= 1440:
        return "today"
    if age <= 4320:
        return "recent"
    return "archive"
