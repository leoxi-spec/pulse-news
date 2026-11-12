#!/usr/bin/env python3
"""Remove publisher video URLs that no longer resolve.

JWPlayer and similar CDNs hand out signed URLs that expire. A URL that used to
work can return 404 weeks later, which shows a broken player even though the
article is fine. This tool checks file-based videos with a ranged GET and clears
the video fields on 404/410 so the reader gets the honest "clip unavailable"
state instead of a failed request on every visit.

Usage:
    python3 tools/check_videos.py --dry-run
    python3 tools/check_videos.py --workers 12
"""
from __future__ import annotations

import argparse
import concurrent.futures
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pulse import tls  # noqa: E402
from pulse.db import db  # noqa: E402


def check(url: str, timeout: float = 12.0) -> str:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Range": "bytes=0-0",
            "User-Agent": "Mozilla/5.0 (compatible; PulseVideoCheck/1.0)",
        },
    )
    try:
        context = tls.get_context() if url.startswith("https://") else None
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            if response.status in (200, 206, 301, 302, 303, 307, 308):
                return "ok"
            return f"http-{response.status}"
    except urllib.error.HTTPError as exc:
        return f"http-{exc.code}"
    except Exception as exc:  # network/DNS/TLS
        return f"error-{type(exc).__name__}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    db.init()
    rows = db.query(
        "SELECT id, title, video_url FROM articles WHERE video_kind='file' AND video_url IS NOT NULL ORDER BY id DESC"
    )
    if args.limit:
        rows = rows[: args.limit]
    print(f"checking {len(rows)} file videos with {args.workers} workers")
    bad: list[tuple[int, str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(check, row["video_url"]): row for row in rows}
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            row = futures[future]
            result = future.result()
            if result in ("http-404", "http-410"):
                bad.append((int(row["id"]), result, row["video_url"]))
                print(f"BAD {result} {row['id']} {row['title'][:70]}")
            elif result != "ok":
                print(f"SKIP {result} {row['id']} {row['title'][:60]}")
            if index % 50 == 0:
                print(f"  checked {index}/{len(rows)}")
    print(f"bad: {len(bad)}")
    if bad and not args.dry_run:
        with db.writer() as conn:
            for article_id, _result, _url in bad:
                conn.execute(
                    "UPDATE articles SET video_url=NULL, video_id=NULL, video_kind=NULL WHERE id=?",
                    (article_id,),
                )
        print(f"cleared {len(bad)} broken video references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
