#!/usr/bin/env python3
"""Check the source catalogue and (optionally) every feed URL.

    python3 tools/verify_catalog.py            # structure only
    python3 tools/verify_catalog.py --live     # fetch every feed (slow)

Exits non-zero if the catalogue has structural problems, or if --live is used
and fewer than half the feeds respond.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pulse import feedparse
from pulse.config import settings
from pulse.httpclient import FetchError, HttpClient
from pulse.sources import FEEDS, FEEDS_BY_SOURCE, SOURCES, TOPIC_SLUGS, catalog_stats


def structural() -> list[str]:
    problems = []
    seen = set()
    for feed in FEEDS:
        if feed.source_id not in SOURCES:
            problems.append(f"feed {feed.url} points at unknown source {feed.source_id}")
        if feed.topic not in TOPIC_SLUGS:
            problems.append(f"feed {feed.url} has unknown topic {feed.topic}")
        if not feed.url.startswith(("http://", "https://", "espn-json:")):
            problems.append(f"feed {feed.url} is not http(s)")
        if feed.url in seen:
            problems.append(f"duplicate feed {feed.url}")
        seen.add(feed.url)
    for source in SOURCES.values():
        if not source.feeds:
            problems.append(f"source {source.id} has no feeds")
    return problems


def live_check(limit: int | None = None) -> int:
    client = HttpClient()
    feeds = FEEDS[:limit] if limit else FEEDS

    def check(feed):
        try:
            if feed.kind == "espn":
                return feed, True, "JSON"
            result = client.get_text(feed.url, timeout=settings.feed_timeout_seconds, retries=0)
            if not result.ok:
                return feed, False, f"HTTP {result.status}"
            parsed = feedparse.parse_feed(result.text, feed.url)
            return feed, True, f"{len(parsed.items)} items"
        except (FetchError, feedparse.FeedError) as exc:
            return feed, False, str(exc)[:80]
        except Exception as exc:  # pragma: no cover
            return feed, False, f"{type(exc).__name__}: {exc}"

    ok = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for feed, success, detail in pool.map(check, feeds):
            ok += int(success)
            if not success:
                print(f"FAIL  {feed.source_id:14s} {feed.url[:90]}  {detail}")
    print(f"\n{ok}/{len(feeds)} feeds responded")
    return 0 if ok >= len(feeds) / 2 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="fetch every feed")
    parser.add_argument("--limit", type=int, default=None, help="only check the first N feeds")
    args = parser.parse_args()

    stats = catalog_stats()
    print(
        f"{stats['sources']} sources · {stats['feeds']} feeds · "
        f"{stats['countries']} countries · {stats['teen_sources']} teen-friendly"
    )
    problems = structural()
    for problem in problems:
        print("PROBLEM", problem)
    if problems:
        return 1
    if args.live:
        return live_check(args.limit)
    print("catalogue OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
