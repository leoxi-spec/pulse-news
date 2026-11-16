"""Seasonal themes and icons.

The calendar is intentionally data-driven: every observance has a date (or a
table of dates for lunar calendars), a lead window, a small palette and an icon
style.  Windows are resolved sequentially, so when two holidays are close
together the earlier one gets the first block and the later one starts after it
ends.  That is what makes Christmas -> Kwanzaa -> New Year read as a sequence
instead of three themes fighting over the same week.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

LEAD_DAYS = 10


def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _css(value: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % value


def _mix(a: str, b: str, amount: float) -> str:
    """Mix two hex colours; amount=0 is a, amount=1 is b."""
    ca, cb = _hex(a), _hex(b)
    return _css(tuple(round(ca[i] + (cb[i] - ca[i]) * amount) for i in range(3)))


def _dark_palette(bg: str, surface: str, text: str, accent: str, accent2: str, accent3: str) -> dict[str, str]:
    """Build a complete dark theme from six well-chosen colours."""
    return {
        "--bg": bg,
        "--bg-alt": _mix(bg, "#ffffff", 0.035),
        "--surface": surface,
        "--surface-2": _mix(surface, "#ffffff", 0.045),
        "--surface-3": _mix(surface, "#ffffff", 0.095),
        "--line": _mix(surface, "#ffffff", 0.13),
        "--line-soft": _mix(surface, "#ffffff", 0.075),
        "--text": text,
        "--text-2": _mix(text, bg, 0.26),
        "--muted": _mix(text, bg, 0.48),
        "--faint": _mix(text, bg, 0.64),
        "--accent": accent,
        "--accent-2": accent2,
        "--accent-3": accent3,
        "--accent-ink": "#ffffff",
        "--grad": f"linear-gradient(120deg, {accent} 0%, {accent2} 100%)",
        "--grad-soft": f"linear-gradient(120deg, {_mix(bg, accent, 0.20)}, {_mix(bg, accent2, 0.13)})",
    }


def _season(
    ident: str,
    label: str,
    blurb: str,
    *,
    bg: str,
    surface: str,
    text: str,
    accent: str,
    accent2: str,
    accent3: str,
    icon_start: str,
    icon_end: str,
    motif: str,
    motif_color: str,
    detail: str,
    pattern: str = "none",
    bar: str = "#fffaf2",
    lead: int = LEAD_DAYS,
    tail: int = 0,
    dates: dict[int, str] | None = None,
    window: tuple[int, int, int, int] | None = None,
) -> dict:
    return {
        "id": ident,
        "label": label,
        "blurb": blurb,
        "palette": _dark_palette(bg, surface, text, accent, accent2, accent3),
        "icon": {
            "start": icon_start,
            "end": icon_end,
            "bar": bar,
            "motif": motif,
            "motif_color": motif_color,
            "detail": detail,
            "pattern": pattern,
        },
        "lead": lead,
        "tail": tail,
        "dates": dates or {},
        "window": window,
    }


# Variable-date observances.  The table covers the years around the current
# release; fixed-date observances are generated automatically below.
_DATES = {
    "lunar-new-year": {
        2025: "01-29", 2026: "02-17", 2027: "02-06", 2028: "01-26",
        2029: "02-13", 2030: "02-03", 2031: "01-23", 2032: "02-11",
    },
    "holi": {
        2025: "03-14", 2026: "03-03", 2027: "03-22", 2028: "03-11",
        2029: "03-01", 2030: "03-20", 2031: "03-10", 2032: "03-27",
    },
    "eid": {
        2025: "03-30", 2026: "03-20", 2027: "03-10", 2028: "02-26",
        2029: "02-14", 2030: "03-05", 2031: "02-25", 2032: "02-14",
    },
    "easter": {
        2025: "04-20", 2026: "04-05", 2027: "03-28", 2028: "04-16",
        2029: "04-01", 2030: "04-21", 2031: "04-13", 2032: "03-28",
    },
    "passover": {
        2025: "04-13", 2026: "04-02", 2027: "04-22", 2028: "04-11",
        2029: "03-31", 2030: "04-18", 2031: "04-08", 2032: "03-27",
    },
    "mothers-day": {
        2025: "05-11", 2026: "05-10", 2027: "05-09", 2028: "05-14",
        2029: "05-13", 2030: "05-12", 2031: "05-11", 2032: "05-09",
    },
    "victoria-day": {
        2025: "05-19", 2026: "05-18", 2027: "05-24", 2028: "05-22",
        2029: "05-21", 2030: "05-20", 2031: "05-19", 2032: "05-24",
    },
    "fathers-day": {
        2025: "06-15", 2026: "06-21", 2027: "06-20", 2028: "06-18",
        2029: "06-17", 2030: "06-16", 2031: "06-15", 2032: "06-20",
    },
    "labor-day": {
        2025: "09-01", 2026: "09-07", 2027: "09-06", 2028: "09-04",
        2029: "09-03", 2030: "09-02", 2031: "09-01", 2032: "09-06",
    },
    "rosh-hashanah": {
        2025: "09-23", 2026: "09-12", 2027: "10-02", 2028: "09-21",
        2029: "09-10", 2030: "09-28", 2031: "09-18", 2032: "09-06",
    },
    "diwali": {
        2025: "10-20", 2026: "11-08", 2027: "10-29", 2028: "10-17",
        2029: "11-05", 2030: "10-26", 2031: "11-14", 2032: "11-02",
    },
    "thanksgiving": {
        2025: "11-27", 2026: "11-26", 2027: "11-25", 2028: "11-23",
        2029: "11-22", 2030: "11-28", 2031: "11-27", 2032: "11-25",
    },
    "hanukkah": {
        2025: "12-15", 2026: "12-05", 2027: "12-25", 2028: "12-13",
        2029: "12-02", 2030: "12-20", 2031: "12-10", 2032: "11-28",
    },
}

_FIXED = {
    "new-year": "01-01",
    "valentines": "02-14",
    "st-patricks": "03-17",
    "earth-day": "04-22",
    "juneteenth": "06-19",
    "canada-day": "07-01",
    "independence-day": "07-04",
    "halloween": "10-31",
    "christmas": "12-25",
    "kwanzaa": "12-26",
}

SEASONS = [
    _season(
        "new-year", "New Year", "Fireworks, midnight and a clean slate.",
        bg="#090d20", surface="#111936", text="#f6f1e5", accent="#ffd166", accent2="#ff7a59", accent3="#7dd3fc",
        icon_start="#080c24", icon_end="#3b1b6b", motif="star", motif_color="#ffd166", detail="#7dd3fc", pattern="confetti",
    ),
    _season(
        "lunar-new-year", "Lunar New Year", "Lanterns, reunion and a lucky new year.",
        bg="#21090d", surface="#2d1014", text="#fff1e5", accent="#ffb703", accent2="#ef476f", accent3="#ffd166",
        icon_start="#4a0b12", icon_end="#16080d", motif="lantern", motif_color="#ffcf5c", detail="#ef476f", pattern="confetti",
        tail=6, dates=_DATES["lunar-new-year"],
    ),
    _season(
        "valentines", "Valentine's Day", "A little more heart, a little more care.",
        bg="#220b19", surface="#321024", text="#fff0f5", accent="#ff5c8a", accent2="#ff9eb5", accent3="#f7c948",
        icon_start="#4d0d2c", icon_end="#1b0714", motif="heart", motif_color="#ff6b95", detail="#ffd1dc", pattern="petals",
    ),
    _season(
        "st-patricks", "St. Patrick's Day", "Green, gold and a bit of Irish luck.",
        bg="#071910", surface="#0d2418", text="#edfff4", accent="#43d17c", accent2="#f5c451", accent3="#9be15d",
        icon_start="#06351d", icon_end="#071b12", motif="shamrock", motif_color="#5ee08c", detail="#f5c451", pattern="confetti",
    ),
    _season(
        "holi", "Holi", "Colour thrown in every direction.",
        bg="#1b0b22", surface="#27112f", text="#fff2fb", accent="#ff5c8a", accent2="#ffd166", accent3="#5ee0d0",
        icon_start="#3f0c4e", icon_end="#19102f", motif="sun", motif_color="#ffd166", detail="#ff5c8a", pattern="confetti",
        dates=_DATES["holi"],
    ),
    _season(
        "eid", "Eid al-Fitr", "A crescent, a feast and a fresh start.",
        bg="#071a20", surface="#0c2830", text="#f3fff9", accent="#f7c948", accent2="#6ee7c8", accent3="#a7f3d0",
        icon_start="#07313a", icon_end="#07131c", motif="crescent", motif_color="#f7c948", detail="#6ee7c8", pattern="stars",
        tail=2, dates=_DATES["eid"],
    ),
    _season(
        "easter", "Easter", "Spring colour, eggs and new beginnings.",
        bg="#1b1526", surface="#271f34", text="#fff8f2", accent="#f7a6c8", accent2="#b8e986", accent3="#ffd166",
        icon_start="#47325f", icon_end="#1e152b", motif="egg", motif_color="#ffd1e0", detail="#b8e986", pattern="petals",
        dates=_DATES["easter"],
    ),
    _season(
        "passover", "Passover", "Liberation, memory and the seder table.",
        bg="#0a1226", surface="#111b36", text="#f5f2e8", accent="#8db7ff", accent2="#f7c948", accent3="#d6e4ff",
        icon_start="#152852", icon_end="#080d1e", motif="star6", motif_color="#d6e4ff", detail="#f7c948", pattern="stars",
        tail=7, dates=_DATES["passover"],
    ),
    _season(
        "earth-day", "Earth Day", "One blue-green home, worth looking after.",
        bg="#061a14", surface="#0b291f", text="#edfff7", accent="#4ade80", accent2="#38bdf8", accent3="#a3e635",
        icon_start="#064b3a", icon_end="#072033", motif="globe", motif_color="#38bdf8", detail="#4ade80", pattern="bubbles",
    ),
    _season(
        "mothers-day", "Mother's Day", "For the people who hold everything together.",
        bg="#25101a", surface="#351522", text="#fff3f6", accent="#ff8fab", accent2="#ffd166", accent3="#f9a8d4",
        icon_start="#5c173d", icon_end="#200a14", motif="flower", motif_color="#ff8fab", detail="#ffd166", pattern="petals",
        dates=_DATES["mothers-day"],
    ),
    _season(
        "victoria-day", "Victoria Day", "The first long weekend of the Canadian summer.",
        bg="#160c11", surface="#241118", text="#fff4ee", accent="#ff6b6b", accent2="#f7c948", accent3="#f2e9dc",
        icon_start="#4a1018", icon_end="#1a0d12", motif="maple", motif_color="#ff6b6b", detail="#f7c948", pattern="confetti",
        dates=_DATES["victoria-day"],
    ),
    _season(
        "pride", "Pride", "Every colour belongs here.",
        bg="#101020", surface="#191932", text="#fbf7ff", accent="#ff5c8a", accent2="#5ee0d0", accent3="#ffd166",
        icon_start="#30104a", icon_end="#071d2d", motif="rainbow", motif_color="#ff5c8a", detail="#ffd166", pattern="confetti",
        lead=0, tail=6, window=(6, 1, 6, 7),
    ),
    _season(
        "fathers-day", "Father's Day", "For the people who show up.",
        bg="#081526", surface="#0f2136", text="#f2f8ff", accent="#4fa3ff", accent2="#f7c948", accent3="#8fd4ff",
        icon_start="#0b2b54", icon_end="#07101e", motif="tie", motif_color="#4fa3ff", detail="#f7c948", pattern="stars",
        dates=_DATES["fathers-day"],
    ),
    _season(
        "juneteenth", "Juneteenth", "Freedom, family and a long road forward.",
        bg="#0e0c0b", surface="#1a1512", text="#fff5e8", accent="#ef476f", accent2="#43d17c", accent3="#f7c948",
        icon_start="#2c0d0d", icon_end="#0b120b", motif="star", motif_color="#ef476f", detail="#43d17c", pattern="confetti",
    ),
    _season(
        "canada-day", "Canada Day", "Maple, summer and the whole country.",
        bg="#210b0d", surface="#301014", text="#fff5f2", accent="#ff5e5e", accent2="#fff3dc", accent3="#ffd166",
        icon_start="#4d0d12", icon_end="#1b090b", motif="maple", motif_color="#ff5e5e", detail="#fff3dc", pattern="confetti",
    ),
    _season(
        "independence-day", "Independence Day", "Stars, stripes and summer fireworks.",
        bg="#071125", surface="#0d1c3a", text="#f7f9ff", accent="#ff5e5e", accent2="#f7f9ff", accent3="#8db7ff",
        icon_start="#152a56", icon_end="#1c0a13", motif="star", motif_color="#ff5e5e", detail="#f7f9ff", pattern="confetti",
    ),
    _season(
        "labor-day", "Labor Day", "The last long weekend of summer.",
        bg="#17110c", surface="#251b12", text="#fff7ed", accent="#f7a35c", accent2="#ffd166", accent3="#8db7ff",
        icon_start="#4a2a12", icon_end="#17100b", motif="gear", motif_color="#f7a35c", detail="#ffd166", pattern="stars",
        dates=_DATES["labor-day"],
    ),
    _season(
        "rosh-hashanah", "Rosh Hashanah", "Apples, honey and a sweet new year.",
        bg="#0c1224", surface="#151d34", text="#fbf6e9", accent="#f7c948", accent2="#ff8a5c", accent3="#8db7ff",
        icon_start="#1b2d58", icon_end="#1c0f12", motif="apple", motif_color="#ff6b5f", detail="#f7c948", pattern="stars",
        tail=1, dates=_DATES["rosh-hashanah"],
    ),
    _season(
        "diwali", "Diwali", "Lamps, light and the festival of new beginnings.",
        bg="#1a0d22", surface="#291331", text="#fff5f6", accent="#ffb703", accent2="#ff6b6b", accent3="#ffd166",
        icon_start="#3b124c", icon_end="#180b16", motif="diya", motif_color="#ffb703", detail="#ff6b6b", pattern="bubbles",
        tail=4, dates=_DATES["diwali"],
    ),
    _season(
        "halloween", "Halloween", "Pumpkins, shadows and one more sweet.",
        bg="#0d0b10", surface="#1a1420", text="#fff4e8", accent="#ff8a1f", accent2="#b78bff", accent3="#ffd166",
        icon_start="#381039", icon_end="#0f0a10", motif="pumpkin", motif_color="#ff8a1f", detail="#b78bff", pattern="stars",
    ),
    _season(
        "thanksgiving", "Thanksgiving", "Gratitude, family and the harvest table.",
        bg="#1b1009", surface="#2b1a0f", text="#fff7e8", accent="#e9a23b", accent2="#c46a3b", accent3="#f4d58d",
        icon_start="#4a2710", icon_end="#1b0e08", motif="leaf", motif_color="#e9a23b", detail="#c46a3b", pattern="leaves",
        dates=_DATES["thanksgiving"],
    ),
    _season(
        "hanukkah", "Hanukkah", "Eight nights of light and latkes.",
        bg="#0a1024", surface="#121b38", text="#f7f8ff", accent="#6ea8fe", accent2="#f7c948", accent3="#d6e4ff",
        icon_start="#172b5c", icon_end="#080d20", motif="menorah", motif_color="#d6e4ff", detail="#f7c948", pattern="stars",
        tail=7, dates=_DATES["hanukkah"],
    ),
    _season(
        "christmas", "Christmas", "Pine, snow and a gold star on top.",
        bg="#0c2219", surface="#123024", text="#f5fff8", accent="#f34e5b", accent2="#f7c948", accent3="#56d68b",
        icon_start="#0c3c2b", icon_end="#771b27", motif="star", motif_color="#f7c948", detail="#f34e5b", pattern="snow",
    ),
    _season(
        "kwanzaa", "Kwanzaa", "Seven candles, seven principles, one community.",
        bg="#0d0d0c", surface="#191612", text="#fff7e8", accent="#ef476f", accent2="#43d17c", accent3="#f7c948",
        icon_start="#20100b", icon_end="#0b120b", motif="kinara", motif_color="#f7c948", detail="#43d17c", pattern="stars",
        tail=5,
    ),
]

# When windows overlap, the higher-significance holiday owns the shared days.
# Equal priorities fall back to the earlier holiday date.
_PRIORITY = {
    "christmas": 100,
    "kwanzaa": 96,
    "new-year": 95,
    "thanksgiving": 90,
    "lunar-new-year": 88,
    "diwali": 86,
    "eid": 84,
    "hanukkah": 84,
    "easter": 83,
    "pride": 80,
    "halloween": 80,
    "canada-day": 78,
    "independence-day": 78,
    "juneteenth": 76,
    "rosh-hashanah": 75,
    "valentines": 74,
    "mothers-day": 73,
    "fathers-day": 72,
    "st-patricks": 70,
    "holi": 70,
    "earth-day": 68,
    "passover": 68,
    "victoria-day": 60,
    "labor-day": 60,
}
for _item in SEASONS:
    _item["priority"] = _PRIORITY[_item["id"]]

SEASON_BY_ID = {season["id"]: season for season in SEASONS}
NORMAL_ID = "normal"


@dataclass(frozen=True)
class Occurrence:
    season: dict
    holiday: date
    start: date
    end: date

    @property
    def id(self) -> str:
        return self.season["id"]


def _holiday_date(season: dict, year: int) -> date | None:
    ident = season["id"]
    if ident in _FIXED:
        month, day = (int(part) for part in _FIXED[ident].split("-"))
        return date(year, month, day)
    if season.get("window"):
        month, day = season["window"][:2]
        return date(year, month, day)
    value = season.get("dates", {}).get(year)
    if value:
        month, day = (int(part) for part in value.split("-"))
        return date(year, month, day)
    return None


def occurrences(first_year: int, last_year: int) -> list[Occurrence]:
    """Raw windows before overlap resolution."""
    result: list[Occurrence] = []
    for year in range(first_year, last_year + 1):
        for season in SEASONS:
            holiday = _holiday_date(season, year)
            if holiday is None:
                continue
            if season.get("window"):
                start_month, start_day, end_month, end_day = season["window"]
                start = date(year, start_month, start_day) - timedelta(days=season["lead"])
                end = date(year, end_month, end_day)
            else:
                start = holiday - timedelta(days=season["lead"])
                end = holiday + timedelta(days=season["tail"])
            result.append(Occurrence(season, holiday, start, end))
    result.sort(key=lambda item: (item.holiday, item.id))
    return result


def schedule(first: date, last: date) -> list[Occurrence]:
    """Resolve overlapping windows by significance, then coalesce by owner.

    Each day has exactly one owner.  A higher-priority holiday wins the shared
    days; a lower-priority holiday keeps any non-overlapping shoulders.  The
    resulting day map is then compressed back into contiguous windows.
    """
    raw = occurrences(first.year - 1, last.year + 1)
    owners: dict[date, Occurrence] = {}
    for item in raw:
        day = item.start
        while day <= item.end:
            current = owners.get(day)
            if current is None:
                owners[day] = item
            else:
                # More significant wins. Equal significance prefers the
                # holiday that arrives first; id is a stable final tiebreak.
                current_key = (current.season["priority"], -current.holiday.toordinal(), current.id)
                item_key = (item.season["priority"], -item.holiday.toordinal(), item.id)
                if item_key > current_key:
                    owners[day] = item
            day += timedelta(days=1)
    resolved: list[Occurrence] = []
    for day in sorted(owners):
        item = owners[day]
        if resolved and resolved[-1].id == item.id and resolved[-1].end + timedelta(days=1) >= day:
            previous = resolved[-1]
            resolved[-1] = Occurrence(previous.season, previous.holiday, previous.start, max(previous.end, day))
        else:
            resolved.append(Occurrence(item.season, item.holiday, day, day))
    return resolved


def _public(item: Occurrence, today: date) -> dict:
    season = item.season
    return {
        "id": season["id"],
        "label": season["label"],
        "blurb": season["blurb"],
        "starts": item.start.isoformat(),
        "ends": item.end.isoformat(),
        "holiday": item.holiday.isoformat(),
        "days_until_holiday": (item.holiday - today).days,
        "days_left": (item.end - today).days,
        "palette": season["palette"],
        "icon": {
            "small": icon_paths(season["id"])[0],
            "large": icon_paths(season["id"])[1],
            "maskable": icon_paths(season["id"])[2],
            "apple": icon_paths(season["id"])[3],
        },
    }


def icon_paths(ident: str) -> tuple[str, str, str, str]:
    if ident == NORMAL_ID:
        return (
            "/icons/icon-192-v28.png",
            "/icons/icon-512-v28.png",
            "/icons/icon-maskable-v28.png",
            "/icons/apple-touch-icon-v28.png",
        )
    base = f"/icons/seasons/v28/{ident}"
    return (f"{base}/icon-192.png", f"{base}/icon-512.png", f"{base}/icon-maskable.png", f"{base}/apple-touch-icon.png")


def normal_payload(today: date) -> dict:
    return {
        "id": NORMAL_ID,
        "label": "Pulse",
        "blurb": "The regular Pulse theme.",
        "starts": None,
        "ends": None,
        "holiday": None,
        "days_until_holiday": None,
        "days_left": None,
        "palette": {},
        "icon": {
            "small": icon_paths(NORMAL_ID)[0],
            "large": icon_paths(NORMAL_ID)[1],
            "maskable": icon_paths(NORMAL_ID)[2],
            "apple": icon_paths(NORMAL_ID)[3],
        },
    }


def current(today: date | None = None) -> dict:
    today = today or date.today()
    items = schedule(today - timedelta(days=45), today + timedelta(days=90))
    active = next((item for item in items if item.start <= today <= item.end), None)
    upcoming = next((item for item in items if item.start > today), None)
    return {
        "today": today.isoformat(),
        "active": _public(active, today) if active else None,
        "next": _public(upcoming, today) if upcoming else None,
        "normal": normal_payload(today),
    }


def archive(today: date | None = None) -> list[dict]:
    today = today or date.today()
    items = schedule(today - timedelta(days=400), today + timedelta(days=500))
    next_by_id: dict[str, Occurrence] = {}
    for item in items:
        if item.holiday >= today and item.id not in next_by_id:
            next_by_id[item.id] = item
    rows = []
    for season in SEASONS:
        row = dict(season)
        nxt = next_by_id.get(season["id"])
        row["next"] = _public(nxt, today) if nxt else None
        row["palette"] = season["palette"]
        row["icon"] = {
            "small": icon_paths(season["id"])[0],
            "large": icon_paths(season["id"])[1],
            "maskable": icon_paths(season["id"])[2],
            "apple": icon_paths(season["id"])[3],
        }
        rows.append(row)
    return rows


def manifest(today: date | None = None) -> dict:
    data = current(today)
    active = data["active"] or data["normal"]
    icons = icon_paths(active["id"])
    palette = active.get("palette") or {}
    bg = palette.get("--bg") or "#0a0c11"
    shortcuts = [
        ("Pulse Shorts", "Shorts", "/reels"),
        ("Watch video", "Watch", "/videos"),
        ("Today's brief", "Brief", "/brief"),
        ("Live scores", "Scores", "/sports"),
        ("Search the archive", "Search", "/search"),
        ("Impact report", "Impact", "/impact"),
        ("Pulse Arcade", "Arcade", "/arcade"),
    ]
    return {
        "id": "/",
        "name": "Pulse — Student News",
        "short_name": "Pulse",
        "description": "A personalised news app for students and teens: 500+ sources, video from newsrooms and YouTube, live scores, AI overviews, a permanent searchable archive, study tools and zero ads.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "display_override": ["window-controls-overlay", "standalone", "minimal-ui"],
        "orientation": "any",
        "background_color": bg,
        "theme_color": bg,
        "categories": ["news", "education", "magazines"],
        "lang": "en",
        "dir": "ltr",
        "prefer_related_applications": False,
        "icons": [
            {"src": icons[0], "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": icons[1], "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": icons[2], "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            *(([{"src": "/icons/icon-v28.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}]
               if active["id"] == NORMAL_ID else [])),
        ],
        "shortcuts": [
            {"name": name, "short_name": short, "url": url, "icons": [{"src": icons[0], "sizes": "192x192"}]}
            for name, short, url in shortcuts
        ],
        "launch_handler": {"client_mode": "navigate-existing"},
        "screenshots": [
            {"src": "/screenshots/welcome-wide.png", "sizes": "1440x900", "type": "image/png", "form_factor": "wide", "label": "A calmer front page"},
            {"src": "/screenshots/home-wide.png", "sizes": "1440x900", "type": "image/png", "form_factor": "wide", "label": "Brief, top stories and Shorts"},
            {"src": "/screenshots/onboarding-wide.png", "sizes": "1440x900", "type": "image/png", "form_factor": "wide", "label": "Reading levels for every age"},
            {"src": "/screenshots/article-wide.png", "sizes": "1440x900", "type": "image/png", "form_factor": "wide", "label": "Reading with photo galleries"},
            {"src": "/screenshots/watch-wide.png", "sizes": "1440x1000", "type": "image/png", "form_factor": "wide", "label": "Watch video from newsrooms and YouTube"},
            {"src": "/screenshots/sports-wide.png", "sizes": "1440x900", "type": "image/png", "form_factor": "wide", "label": "Live scores and player stats"},
            {"src": "/screenshots/shorts-narrow.png", "sizes": "860x1864", "type": "image/png", "form_factor": "narrow", "label": "Pulse Shorts"},
            {"src": "/screenshots/home-narrow.png", "sizes": "860x1864", "type": "image/png", "form_factor": "narrow", "label": "The front page on mobile"},
            {"src": "/screenshots/impact-wide.png", "sizes": "1440x1000", "type": "image/png", "form_factor": "wide", "label": "Live impact report"},
            {"src": "/screenshots/about-wide.png", "sizes": "1440x1000", "type": "image/png", "form_factor": "wide", "label": "The project and press kit"},
            {"src": "/screenshots/arcade-wide.png", "sizes": "1440x1000", "type": "image/png", "form_factor": "wide", "label": "Pulse Arcade"},
        ],
    }
