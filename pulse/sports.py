"""Live sports scores and ESPN news.

Scores come from ESPN's public scoreboard JSON, normalised into a small shape
so the UI never has to understand ESPN's schema.  Responses are cached in
SQLite (and in memory) for a few seconds so a room full of clients hitting
"refresh" does not hammer the upstream API.
"""
from __future__ import annotations

import concurrent.futures
import json
from dataclasses import dataclass
from typing import Any

from .config import settings
from .db import db
from .httpclient import FetchError, HttpClient
from .logging_setup import get_logger
from .timeutil import iso, minutes_since, parse_iso

log = get_logger("sports")


@dataclass(frozen=True)
class League:
    slug: str
    label: str
    sport: str
    path: str
    emoji: str
    group: str


LEAGUES: tuple[League, ...] = (
    League("nba", "NBA", "basketball", "basketball/nba", "🏀", "Basketball"),
    League("wnba", "WNBA", "basketball", "basketball/wnba", "🏀", "Basketball"),
    League("ncaab", "Men's College Basketball", "basketball", "basketball/mens-college-basketball", "🏀", "Basketball"),
    League("nfl", "NFL", "football", "football/nfl", "🏈", "Football"),
    League("ncaaf", "College Football", "football", "football/college-football", "🏈", "Football"),
    League("mlb", "MLB", "baseball", "baseball/mlb", "⚾", "Baseball"),
    League("nhl", "NHL", "hockey", "hockey/nhl", "🏒", "Hockey"),
    League("mls", "MLS", "soccer", "soccer/usa.1", "⚽", "Soccer"),
    League("eng.1", "Premier League", "soccer", "soccer/eng.1", "⚽", "Soccer"),
    League("esp.1", "LaLiga", "soccer", "soccer/esp.1", "⚽", "Soccer"),
    League("ita.1", "Serie A", "soccer", "soccer/ita.1", "⚽", "Soccer"),
    League("ger.1", "Bundesliga", "soccer", "soccer/ger.1", "⚽", "Soccer"),
    League("fra.1", "Ligue 1", "soccer", "soccer/fra.1", "⚽", "Soccer"),
    League("uefa.champions", "Champions League", "soccer", "soccer/uefa.champions", "⚽", "Soccer"),
    League("f1", "Formula 1", "racing", "racing/f1", "🏎️", "Racing"),
)

LEAGUE_BY_SLUG = {league.slug: league for league in LEAGUES}
# ESPN's news endpoint uses a different set of paths for a couple of leagues.
_NEWS_PATHS = {
    "ncaab": "basketball/mens-college-basketball",
    "ncaaf": "football/college-football",
}
_MEMORY: dict[str, tuple[float, dict]] = {}

_client = HttpClient(user_agent=f"{settings.user_agent} (scores)")


def _scoreboard_key(slug: str) -> str:
    return f"scoreboard:{slug}"


def scoreboard(slug: str, *, force: bool = False) -> dict:
    league = LEAGUE_BY_SLUG.get(slug)
    if league is None:
        raise ValueError(f"Unknown league {slug!r}")
    key = _scoreboard_key(slug)
    if not force:
        cached = _MEMORY.get(key)
        if cached and minutes_since(cached[1].get("fetched_at")) * 60 < settings.sports_cache_seconds:
            return cached[1]
        row = db.query_one("SELECT payload, fetched_at FROM sports_cache WHERE key=?", (key,))
        if row and (minutes_since(row["fetched_at"]) * 60) < settings.sports_cache_seconds:
            try:
                payload = json.loads(row["payload"])
                _MEMORY[key] = (0.0, payload)
                return payload
            except (ValueError, TypeError):
                pass
    payload = _fetch_scoreboard(league)
    db.execute(
        "INSERT INTO sports_cache(key, payload, fetched_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, fetched_at=excluded.fetched_at",
        (key, json.dumps(payload), payload["fetched_at"]),
    )
    _MEMORY[key] = (0.0, payload)
    return payload


def _fetch_scoreboard(league: League) -> dict:
    url = f"{settings.espn_base}/apis/site/v2/sports/{league.path}/scoreboard"
    try:
        data = _client.get_json(url, timeout=10, retries=1)
    except FetchError as exc:
        log.warning("scoreboard %s failed: %s", league.slug, exc)
        return {
            "league": _league_meta(league),
            "events": [],
            "fetched_at": iso(),
            "error": str(exc),
        }
    events = [_normalise_event(event, league) for event in data.get("events", []) if isinstance(event, dict)]
    events = [event for event in events if event]
    league_meta = _league_meta(league)
    season = (data.get("leagues") or [{}])[0].get("season") or {}
    if season.get("displayName"):
        league_meta["season"] = season["displayName"]
    return {"league": league_meta, "events": events, "fetched_at": iso(), "error": None}


def _league_meta(league: League) -> dict:
    return {
        "slug": league.slug,
        "label": league.label,
        "emoji": league.emoji,
        "group": league.group,
        "sport": league.sport,
    }


def _normalise_event(event: dict, league: League) -> dict | None:
    competition = (event.get("competitions") or [{}])[0]
    status = competition.get("status") or event.get("status") or {}
    status_type = status.get("type") or {}
    competitors = []
    for competitor in competition.get("competitors") or []:
        team = competitor.get("team") or {}
        records = competitor.get("records") or []
        logos = team.get("logos") or []
        logo = team.get("logo") or (logos[0].get("href") if logos else None)
        competitors.append(
            {
                "id": str(team.get("id") or competitor.get("id") or ""),
                "name": team.get("displayName") or team.get("name") or "TBD",
                "short": team.get("shortDisplayName") or team.get("abbreviation") or "",
                "abbr": team.get("abbreviation") or "",
                "logo": logo,
                "score": competitor.get("score"),
                "winner": bool(competitor.get("winner")),
                "home": competitor.get("homeAway") == "home",
                "record": (records[0].get("summary") if records else None) or competitor.get("record"),
                "color": team.get("color"),
            }
        )
    if not competitors:
        return None
    state = status_type.get("state") or "pre"
    detail = status_type.get("detail") or status_type.get("shortDetail") or ""
    if not detail:
        detail = status.get("displayClock") or ""
    broadcasts = []
    for broadcast in competition.get("broadcasts") or []:
        names = broadcast.get("names") or []
        broadcasts.extend(names)
    links = []
    for link in (event.get("links") or [])[:3]:
        if link.get("href"):
            links.append({"href": link["href"], "text": link.get("shortText") or link.get("text") or "ESPN"})
    return {
        "id": str(event.get("id") or competition.get("id") or ""),
        "name": event.get("name") or competition.get("headline") or "",
        "short_name": event.get("shortName") or "",
        "date": event.get("date") or competition.get("date"),
        "status": {
            "state": state,
            "detail": detail,
            "completed": bool(status_type.get("completed")),
            "clock": status.get("displayClock"),
            "period": status.get("period"),
            "description": status_type.get("description") or status_type.get("name"),
        },
        "competitors": competitors,
        "venue": (competition.get("venue") or {}).get("fullName"),
        "broadcasts": list(dict.fromkeys(broadcasts))[:4],
        "links": links,
        "league": league.slug,
        "is_live": state == "in",
    }


def all_scoreboards(*, force: bool = False, leagues: list[str] | None = None) -> dict:
    selected = [LEAGUE_BY_SLUG[s] for s in (leagues or []) if s in LEAGUE_BY_SLUG] or list(LEAGUES)
    results: dict[str, dict] = {}
    if not settings.sports_enabled:
        return {"leagues": [], "events": [], "fetched_at": iso(), "disabled": True}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(selected))) as pool:
        futures = {pool.submit(scoreboard, league.slug, force=force): league for league in selected}
        for future in concurrent.futures.as_completed(futures):
            league = futures[future]
            try:
                results[league.slug] = future.result()
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("scoreboard %s crashed: %s", league.slug, exc)
                results[league.slug] = {
                    "league": _league_meta(league), "events": [], "fetched_at": iso(), "error": str(exc)
                }
    events = []
    for payload in results.values():
        for event in payload.get("events", []):
            events.append(event)
    live = [event for event in events if event.get("is_live")]
    upcoming = [event for event in events if event.get("status", {}).get("state") == "pre"]
    finished = [event for event in events if event.get("status", {}).get("state") == "post"]
    events.sort(key=lambda e: (0 if e.get("is_live") else 1 if e["status"]["state"] == "pre" else 2, e.get("date") or ""))
    return {
        "leagues": [_league_meta(league) for league in selected],
        "events": events,
        "live_count": len(live),
        "upcoming_count": len(upcoming),
        "completed_count": len(finished),
        "fetched_at": iso(),
        "cache_seconds": settings.sports_cache_seconds,
        "errors": [p.get("error") for p in results.values() if p.get("error")],
    }


def league_scores(slug: str) -> dict:
    payload = scoreboard(slug)
    return payload


def news(league_slug: str, limit: int = 12) -> list[dict[str, Any]]:
    """ESPN news for a league, shaped like feed items so ingestion is uniform."""
    league = LEAGUE_BY_SLUG.get(league_slug)
    if league is None:
        return []
    key = f"news:{league.slug}"
    row = db.query_one("SELECT payload, fetched_at FROM sports_cache WHERE key=?", (key,))
    if row and minutes_since(row["fetched_at"]) < 10:
        try:
            return json.loads(row["payload"])
        except (ValueError, TypeError):
            pass
    path = _NEWS_PATHS.get(league.slug, league.path)
    url = f"{settings.espn_base}/apis/site/v2/sports/{path}/news"
    try:
        data = _client.get_json(url, timeout=10, retries=1)
    except FetchError as exc:
        log.debug("espn news %s failed: %s", league.slug, exc)
        return []
    articles = []
    for raw in (data.get("articles") or [])[:limit]:
        if not isinstance(raw, dict):
            continue
        link = ((raw.get("links") or {}).get("web") or {}).get("href") or raw.get("link") or ""
        images = raw.get("images") or []
        image = images[0].get("url") if images else None
        articles.append(
            {
                "guid": f"espn:{raw.get('id') or link}",
                "title": raw.get("headline") or "",
                "link": link,
                "summary": raw.get("description") or "",
                "published": raw.get("published"),
                "image": image,
                "byline": raw.get("byline"),
                "league": league.slug,
                "league_label": league.label,
            }
        )
    payload = [a for a in articles if a["title"] and a["link"]]
    db.execute(
        "INSERT INTO sports_cache(key, payload, fetched_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload, fetched_at=excluded.fetched_at",
        (key, json.dumps(payload), iso()),
    )
    return payload


def followed_teams(profile_id: str) -> list[str]:
    rows = db.query("SELECT value FROM follows WHERE profile_id=? AND kind='team'", (profile_id,))
    return [row["value"] for row in rows]


def team_games(team_ids: list[str], *, days_back: int = 6) -> list[dict]:
    if not team_ids:
        return []
    wanted = set(team_ids)
    payload = all_scoreboards()
    games = []
    for event in payload["events"]:
        if any(competitor["id"] in wanted for competitor in event["competitors"]):
            games.append(event)
    return games


def clear_cache() -> None:
    _MEMORY.clear()
    db.execute("DELETE FROM sports_cache")
