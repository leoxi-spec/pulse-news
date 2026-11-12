# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import feed, feedparse, htmltext, ingest as ingest_module, profiles
from pulse.db import db
from pulse.sources import FEEDS, SOURCES, FeedSpec
from pulse.stories import Clusterer

YOUTUBE_ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/">
  <title>BBC News</title>
  <entry>
    <id>yt:video:abc12345678</id>
    <yt:videoId>abc12345678</yt:videoId>
    <title>Inside the climate summit</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc12345678"/>
    <published>2026-11-12T10:00:00+00:00</published>
    <media:group>
      <media:thumbnail url="https://i.ytimg.com/vi/abc12345678/hqdefault.jpg"/>
      <media:description>World leaders meet in Brazil. Subscribe for more daily news.</media:description>
    </media:group>
  </entry>
</feed>"""


def setUpModule():
    db.init()
    db.seed_catalog(SOURCES, FEEDS)


class VideoParsingTests(unittest.TestCase):
    def test_youtube_atom_carries_video_and_thumbnail(self):
        parsed = feedparse.parse_feed(YOUTUBE_ATOM)
        item = parsed.items[0]
        self.assertEqual(item.video_kind, "youtube")
        self.assertEqual(item.video_id, "abc12345678")
        self.assertEqual(item.video_url, "https://www.youtube.com/watch?v=abc12345678")
        self.assertIn("i.ytimg.com", item.image)
        self.assertIn("World leaders", item.summary_html)

    def test_video_from_open_graph_and_iframe(self):
        kind, video_id, url = htmltext.video_from_markup(
            '<meta property="og:video" content="https://www.youtube.com/embed/dQw4w9WgXcQ">'
        )
        self.assertEqual((kind, video_id), ("youtube", "dQw4w9WgXcQ"))
        self.assertIn("watch?v=", url)

    def test_json_escaped_video_url_is_repaired(self):
        kind, video_id, url = htmltext.video_from_markup(
            r'<meta property="og:video" content="https:\/\/cdn.example.com\/videos\/clip.mp4">'
        )
        self.assertEqual(kind, "file")
        self.assertIsNone(video_id)
        self.assertEqual(url, "https://cdn.example.com/videos/clip.mp4")

    def test_direct_mp4_is_recognised(self):
        kind, video_id, url = htmltext.video_from_markup(
            '<video src="https://cdn.example.com/clip.mp4" poster="/x.jpg"></video>'
        )
        self.assertEqual(kind, "file")
        self.assertIsNone(video_id)
        self.assertEqual(url, "https://cdn.example.com/clip.mp4")

    def test_video_summary_drops_youtube_housekeeping(self):
        text = "The summit opened on Monday. Subscribe for more daily news. Watch PBS News for live coverage."
        cleaned = ingest_module._video_summary(text)
        self.assertIn("summit opened", cleaned)
        self.assertNotIn("Subscribe", cleaned)
        self.assertNotIn("Watch PBS", cleaned)


class VideoStoreTests(unittest.TestCase):
    def setUp(self):
        db.execute("DELETE FROM articles")
        db.execute("DELETE FROM stories")
        self.clusterer = Clusterer([])
        self.feed = FeedSpec(
            id="yt-bbc-test", source_id="yt-bbc", topic="world",
            url="https://www.youtube.com/feeds/videos.xml?channel_id=test", label="world",
        )

    def test_youtube_item_is_stored_and_streamed(self):
        item = feedparse.FeedItem(
            guid="yt:video:abc12345678",
            title="Inside the climate summit",
            link="https://www.youtube.com/watch?v=abc12345678",
            summary_html="<p>World leaders meet in Brazil to discuss emissions.</p>",
            published_raw="2026-11-12T10:00:00Z",
            video_kind="youtube",
            video_id="abc12345678",
            video_url="https://www.youtube.com/watch?v=abc12345678",
        )
        new, _, _ = ingest_module.ingest._store_feed(self.feed, [item], self.clusterer)
        self.assertEqual(new, 1)
        row = db.query_one("SELECT * FROM articles WHERE guid=?", ("yt:video:abc12345678",))
        self.assertEqual(row["video_kind"], "youtube")
        self.assertEqual(row["video_id"], "abc12345678")
        self.assertIn("i.ytimg.com", row["image_url"])

        profile = profiles.create()
        stream = feed.video_feed(profile)
        self.assertEqual(stream["total"], 1)
        card = stream["items"][0]
        self.assertEqual(card["video"]["kind"], "youtube")
        self.assertIn("youtube-nocookie.com/embed/abc12345678", card["video"]["embed"])
        self.assertEqual(card["source"]["id"], "yt-bbc")


if __name__ == "__main__":
    unittest.main()
