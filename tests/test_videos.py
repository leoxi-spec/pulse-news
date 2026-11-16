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


class VideoPagingTests(unittest.TestCase):
    """A filtered video page must not be empty while ``total`` counts rows.

    The Formula 1 lane and the formality checks are Python predicates. When
    they ran after ``LIMIT``, a first page of "motorsport" videos with no F1
    clip in it came back with zero items and ``total: 25``, so the grid showed
    "No video here yet" and "Load more" looped on nothing.
    """

    def setUp(self):
        db.execute("DELETE FROM articles")
        db.execute("DELETE FROM stories")

    def _add(self, index: int, title: str, *, topic: str = "motorsport", kind: str = "youtube"):
        guid = f"yp:{index:03d}"
        video_id = f"vid{index:08d}"
        db.execute(
            """
            INSERT INTO articles(guid, source_id, url, title, summary, published_at,
                                 first_seen_at, last_seen_at, primary_topic, topics,
                                 content_state, video_kind, video_id, video_url)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                guid, "yt-bbc", f"https://www.youtube.com/watch?v={video_id}", title,
                "A clip from the race weekend.",
                f"2026-11-{index % 20 + 1:02d}T10:00:00+00:00",
                f"2026-11-{index % 20 + 1:02d}T10:00:00+00:00",
                f"2026-11-{index % 20 + 1:02d}T10:00:00+00:00",
                topic, f'["{topic}"]', "feed", kind, video_id if kind != "file" else None,
                f"https://www.youtube.com/watch?v={video_id}",
            ),
        )

    def test_formula_one_page_is_not_empty_behind_other_motorsport(self):
        # Newer non-F1 clips fill the first SQL page; the F1 clips are older.
        for index in range(30):
            self._add(index, f"IndyCar race highlights number {index}")
        for index in range(30, 36):
            self._add(index, f"Verstappen wins the Grand Prix, race {index}")

        profile = profiles.create()
        page = feed.video_feed(profile, topic="motorsport", limit=5)
        self.assertEqual(page["total"], 6)
        self.assertEqual(len(page["items"]), 5)
        self.assertTrue(page["has_more"])
        for item in page["items"]:
            self.assertIn("Grand Prix", item["title"])

    def test_paging_covers_everything_once_and_stops(self):
        for index in range(12):
            self._add(index, f"Grand Prix qualifying report {index}")

        profile = profiles.create()
        seen: list[int] = []
        offset = 0
        while True:
            page = feed.video_feed(profile, topic="motorsport", offset=offset, limit=4)
            if not page["items"]:
                break
            seen.extend(item["id"] for item in page["items"])
            offset += len(page["items"])
            if not page["has_more"]:
                break
        self.assertEqual(len(seen), 12)
        self.assertEqual(len(set(seen)), 12)

    def test_same_clip_published_twice_is_one_tile(self):
        self._add(1, "Grand Prix: the winning move")
        self._add(2, "Grand Prix: the winning move")  # re-published with a new GUID
        self._add(3, "Grand Prix: a different session")

        profile = profiles.create()
        page = feed.video_feed(profile, topic="motorsport")
        titles = [item["title"] for item in page["items"]]
        self.assertEqual(len(titles), 2)
        self.assertEqual(len(set(titles)), 2)
        self.assertEqual(page["total"], 2)

    def test_unplayable_clip_is_not_counted(self):
        self._add(1, "Grand Prix: the winning move")
        self._add(2, "Grand Prix: the winning move, again")
        # A stream manifest cannot be played by the browser, so the card would
        # render an empty player. It must not inflate the total either.
        db.execute("UPDATE articles SET video_kind='file', video_id=NULL, video_url=? WHERE guid='yp:002'",
                   ("https://cdn.example.com/live.m3u8",))

        profile = profiles.create()
        page = feed.video_feed(profile, topic="motorsport")
        self.assertEqual(page["total"], 1)
        self.assertEqual(len(page["items"]), 1)
        self.assertFalse(page["has_more"])


if __name__ == "__main__":
    unittest.main()
