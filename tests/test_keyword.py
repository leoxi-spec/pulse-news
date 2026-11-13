# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import feed, feedparse, ingest as ingest_module, profiles
from pulse.db import db
from pulse.sources import FEEDS, SOURCES, FeedSpec
from pulse.stories import Clusterer

SPEC = FeedSpec(id="keyword-test", source_id="bbc", topic="world", url="https://example.com/feed.xml", label="world")


def setUpModule():
    db.init()
    db.seed_catalog(SOURCES, FEEDS)


class KeywordPageTests(unittest.TestCase):
    def setUp(self):
        db.execute("DELETE FROM articles")
        db.execute("DELETE FROM stories")
        item = feedparse.FeedItem(
            guid="keyword-1",
            title="Climate summit reaches a finance deal",
            link="https://example.com/climate-summit",
            summary_html="<p>Delegates agreed a climate finance package after two weeks of talks.</p>",
            published_raw="2026-11-12T10:00:00Z",
        )
        ingest_module.ingest._store_feed(SPEC, [item], Clusterer([]))
        self.profile = profiles.create("Keyword tester")

    def test_keyword_feed_returns_cards_from_the_archive(self):
        page = feed.keyword_page(self.profile, "climate", limit=10)
        self.assertGreaterEqual(page["total"], 1)
        self.assertGreaterEqual(len(page["items"]), 1)
        card = page["items"][0]
        self.assertIn("Climate", card["title"])
        self.assertEqual(card["source"]["id"], "bbc")
        self.assertIn("source", card)
        self.assertIn("image_count", card)

    def test_keyword_feed_empty_query_is_safe(self):
        page = feed.keyword_page(self.profile, "zzzz-no-match-zzzz")
        self.assertEqual(page["items"], [])
        self.assertEqual(page["total"], 0)


if __name__ == "__main__":
    unittest.main()
