#!/usr/bin/env python3
"""Start Pulse: `python3 run.py [--host 0.0.0.0] [--port 8787]`.

No third-party dependencies. Python 3.10+ (3.13 recommended).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    from pulse.logging_setup import configure

    configure()
    from pulse.config import settings
    from pulse.server import serve

    parser = argparse.ArgumentParser(description="Pulse — news that keeps up with you")
    parser.add_argument("--host", default=settings.host, help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=settings.port, help="port (default 8787)")
    parser.add_argument("--no-ingest", action="store_true", help="serve only, do not fetch feeds")
    parser.add_argument("--ingest-once", action="store_true", help="run one ingestion pass and exit")
    args = parser.parse_args()

    if args.no_ingest:
        os.environ["PULSE_INGEST"] = "0"
    if args.ingest_once:
        from pulse.db import db
        from pulse.ingest import ingest
        from pulse.sources import FEEDS, SOURCES

        db.init()
        db.seed_catalog(SOURCES, FEEDS)
        report = ingest.run_once()
        print(report)
        return
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
