# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import feedparse

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Example News</title>
    <item>
      <title>Council approves plan &amp; promises repairs</title>
      <link>https://example.com/a?utm_source=rss</link>
      <guid isPermaLink="false">abc-123</guid>
      <description><![CDATA[<p>The council voted 7-2 to approve the plan &nbsp; on Tuesday.</p>]]></description>
      <content:encoded><![CDATA[<p>Full body text here with more detail for readers.</p><p>Second paragraph.</p>]]></content:encoded>
      <pubDate>Tue, 10 Nov 2026 18:30:00 GMT</pubDate>
      <dc:creator>Jane Doe</dc:creator>
      <category>Politics</category>
      <media:content url="https://example.com/photo.jpg" medium="image"/>
    </item>
    <item>
      <title>Second story</title>
      <link>/relative-link</link>
      <description>Short summary</description>
    </item>
  </channel>
</rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Example</title>
  <entry>
    <title type="html">Scientists find &lt;em&gt;surprising&lt;/em&gt; result</title>
    <link rel="alternate" href="https://example.org/science/story"/>
    <id>tag:example.org,2026:1</id>
    <updated>2026-11-10T09:00:00Z</updated>
    <published>2026-11-10T08:00:00Z</published>
    <author><name>Sam Lee</name></author>
    <summary>A surprising result was announced on Monday.</summary>
    <content type="html">&lt;p&gt;The team measured a record value in the lab.&lt;/p&gt;</content>
  </entry>
</feed>"""

JSONFEED = """{
  "version": "https://jsonfeed.org/version/1.1",
  "title": "JSON Example",
  "items": [
    {
      "id": "1",
      "title": "JSON feed story",
      "url": "https://example.net/json/1",
      "content_html": "<p>Body from a JSON feed.</p>",
      "summary": "Summary text",
      "date_published": "2026-11-09T12:00:00Z",
      "authors": [{"name": "Alex Kim"}]
    }
  ]
}"""

BROKEN = """<rss><channel><title>Broken</title>
<item><title>Recovered item</title><link>https://example.com/r</link>
<description>Body with a bare ampersand & more text</description><pubDate>Mon, 09 Nov 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""

BLOCK_PAGE = """<!DOCTYPE html><html><head><title>For your safety this page has been restricted</title></head>
<body><h1>For your safety this page has been restricted</h1></body></html>"""


class RssTests(unittest.TestCase):
    def setUp(self):
        self.feed = feedparse.parse_feed(RSS, "https://example.com/rss")

    def test_channel_title(self):
        self.assertEqual(self.feed.title, "Example News")

    def test_items(self):
        self.assertEqual(len(self.feed.items), 2)
        first = self.feed.items[0]
        self.assertEqual(first.guid, "abc-123")
        self.assertEqual(first.link, "https://example.com/a?utm_source=rss")
        self.assertEqual(first.author, "Jane Doe")
        self.assertIn("Full body text", first.content_html)
        self.assertEqual(first.image, "https://example.com/photo.jpg")
        self.assertIn("Politics", first.categories)

    def test_title_entities_decoded(self):
        self.assertIn("&", self.feed.items[0].title)

    def test_relative_links_kept_raw_for_caller(self):
        self.assertEqual(self.feed.items[1].link, "/relative-link")


class AtomTests(unittest.TestCase):
    def test_atom(self):
        feed = feedparse.parse_feed(ATOM)
        self.assertEqual(feed.kind, "atom")
        item = feed.items[0]
        self.assertEqual(item.link, "https://example.org/science/story")
        self.assertEqual(item.guid, "tag:example.org,2026:1")
        self.assertEqual(item.author, "Sam Lee")
        self.assertEqual(item.published_raw, "2026-11-10T08:00:00Z")
        self.assertNotIn("<em>", item.title)


class JsonFeedTests(unittest.TestCase):
    def test_json(self):
        feed = feedparse.parse_feed(JSONFEED)
        self.assertEqual(feed.kind, "json")
        self.assertEqual(feed.items[0].link, "https://example.net/json/1")
        self.assertEqual(feed.items[0].author, "Alex Kim")


class FailureTests(unittest.TestCase):
    def test_malformed_recovers_items(self):
        feed = feedparse.parse_feed(BROKEN)
        self.assertEqual(len(feed.items), 1)
        self.assertEqual(feed.items[0].title, "Recovered item")

    def test_block_page_is_reported_as_blocked(self):
        with self.assertRaises(feedparse.FeedError) as ctx:
            feedparse.parse_feed(BLOCK_PAGE)
        self.assertTrue(ctx.exception.blocked)

    def test_empty(self):
        with self.assertRaises(feedparse.FeedError):
            feedparse.parse_feed("")

    def test_html_not_feed(self):
        with self.assertRaises(feedparse.FeedError):
            feedparse.parse_feed("<html><body><p>hello</p></body></html>")


if __name__ == "__main__":
    unittest.main()
