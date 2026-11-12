"""Backfill article galleries for stories extracted before multi-image support.

Usage: python3 tools/enrich_images.py [--limit 60] [--workers 4]

Fetches recent extracted pages, collects their large images and stores them in
the articles.images column. Safe to re-run; only touches rows that have no
gallery yet.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pulse import htmltext  # noqa: E402
from pulse.db import db  # noqa: E402
from pulse.httpclient import HttpClient  # noqa: E402
from pulse.logging_setup import get_logger  # noqa: E402
from pulse.timeutil import iso  # noqa: E402

log = get_logger("enrich_images")


def enrich(row, client: HttpClient) -> tuple[int, int]:
    article_id, url = row["id"], row["url"]
    if not url:
        return article_id, 0
    try:
        result = client.fetch(url, accept="text/html,application/xhtml+xml", timeout=18, retries=0)
        if not result.ok or not result.text:
            return article_id, 0
        parsed = htmltext.extract_article(result.text, url)
        if parsed.paywall:
            return article_id, 0
        images = [image for image in parsed.images[:24] if image]
        if len(images) < 2:
            return article_id, len(images)
        with db.writer() as conn:
            conn.execute(
                "UPDATE articles SET images=?, image_url=COALESCE(image_url, ?) WHERE id=?",
                (json.dumps(images), images[0], article_id),
            )
        return article_id, len(images)
    except Exception as exc:  # network/publisher failures are expected
        log.debug("image enrich failed %s: %s", url, exc)
        return article_id, 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    db.init()
    rows = db.query(
        """SELECT id, url FROM articles
           WHERE content_state='extracted' AND url IS NOT NULL AND url <> ''
             AND (images IS NULL OR images='' OR images='[]' OR json_array_length(images) < 24)
           ORDER BY COALESCE(published_at, first_seen_at) DESC LIMIT ?""",
        (max(1, args.limit),),
    )
    print(f"scanning {len(rows)} articles…")
    client = HttpClient()
    found = 0
    galleries = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(enrich, row, client) for row in rows]
        for index, future in enumerate(as_completed(futures), 1):
            _, count = future.result()
            if count:
                found += 1
            if count > 1:
                galleries += 1
            if index % 10 == 0:
                print(f"  {index}/{len(rows)} checked · {galleries} galleries")
    print(f"done: {found} pages had images, {galleries} now have galleries · {iso()}")


if __name__ == "__main__":
    main()
