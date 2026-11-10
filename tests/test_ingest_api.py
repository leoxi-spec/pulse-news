import unittest
from datetime import datetime, timedelta, timezone

from pulse import api, feedparse, ingest as ingest_module, profiles, search
from pulse.db import db
from pulse.sources import FEEDS, SOURCES, FeedSpec
from pulse.stories import Clusterer

FEED = FeedSpec(id="test-feed", source_id="bbc", topic="world", url="https://example.com/feed.xml", label="world")


def setUpModule():
    db.init()
    db.seed_catalog(SOURCES, FEEDS)


def item(title, link, body, published=None, guid=None):
    return feedparse.FeedItem(
        guid=guid or link,
        title=title,
        link=link,
        summary_html=body,
        content_html=body,
        published_raw=published,
    )


class StoreTests(unittest.TestCase):
    def setUp(self):
        db.execute("DELETE FROM articles")
        db.execute("DELETE FROM stories")
        self.clusterer = Clusterer([])

    def test_article_is_stored_with_dates_and_topic(self):
        new, updated, story_ids = ingest_module.ingest._store_feed(
            FEED,
            [item("Council approves transit plan", "https://example.com/transit",
                  "<p>The council voted 7-2 to approve a new transit plan on Tuesday.</p>",
                  "Tue, 10 Nov 2026 18:30:00 GMT")],
            self.clusterer,
        )
        self.assertEqual((new, updated), (1, 0))
        row = db.query_one("SELECT * FROM articles WHERE url='https://example.com/transit'")
        self.assertEqual(row["published_at"], "2026-11-10T18:30:00Z")
        self.assertEqual(row["date_confidence"], "exact")
        self.assertEqual(row["primary_topic"], "world")
        self.assertEqual(row["source_id"], "bbc")
        self.assertTrue(story_ids)

    def test_dedupe_does_not_duplicate(self):
        payload = [item("Duplicate story", "https://example.com/dup", "<p>Body text that is long enough to keep.</p>", "2026-11-10T10:00:00Z")]
        ingest_module.ingest._store_feed(FEED, payload, self.clusterer)
        new, updated, _ = ingest_module.ingest._store_feed(FEED, payload, self.clusterer)
        self.assertEqual(new, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM articles"), 1)

    def test_future_date_is_clamped(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ingest_module.ingest._store_feed(
            FEED,
            [item("Future story", "https://example.com/future", "<p>Some body text for the future story.</p>", future)],
            self.clusterer,
        )
        row = db.query_one("SELECT published_at, date_confidence, published_raw FROM articles WHERE url='https://example.com/future'")
        self.assertEqual(row["date_confidence"], "inferred")
        self.assertEqual(row["published_raw"], future)
        self.assertLess(row["published_at"], future)

    def test_similar_headlines_share_a_story(self):
        ingest_module.ingest._store_feed(
            FEED,
            [item("Trump ally Jim Jordan elected House Republican leader", "https://example.com/j1",
                  "<p>Republicans elected Jim Jordan as their leader on Tuesday.</p>", "2026-11-10T12:00:00Z")],
            self.clusterer,
        )
        ingest_module.ingest._store_feed(
            FeedSpec(id="test-feed-2", source_id="politico", topic="politics", url="https://example.com/feed2.xml", label="politics"),
            [item("Jim Jordan elected House Republican leader after party vote", "https://example.com/j2",
                  "<p>House Republicans picked Jim Jordan to lead them next year.</p>", "2026-11-10T13:00:00Z")],
            self.clusterer,
        )
        stories = db.query("SELECT id, article_count, source_count FROM stories")
        self.assertEqual(len(stories), 1)
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM articles WHERE story_id=?", (stories[0]["id"],)), 2)

    def test_search_index_is_updated(self):
        ingest_module.ingest._store_feed(
            FEED,
            [item("Volcanic eruption disrupts flights in Iceland", "https://example.com/volcano",
                  "<p>A volcanic eruption sent ash across the Reykjanes peninsula and disrupted flights.</p>", "2026-11-09T08:00:00Z")],
            self.clusterer,
        )
        result = search.search("volcanic eruption")
        self.assertGreaterEqual(result["total"], 1)
        self.assertTrue(any("Volcanic" in row["title"] for row in result["results"]))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = profiles.create("API Test")
        profiles.update(cls.profile["id"], survey={"topics": {"world": 3, "tech": 2}}, onboarded=True)
        cls.profile = profiles.get(cls.profile["id"])

    @classmethod
    def tearDownClass(cls):
        profiles.delete(cls.profile["id"])

    def request(self, path, method="GET", query=None, body=None, profile=True):
        return api.Request(
            method=method,
            path=path,
            query=query or {},
            body=(__import__("json").dumps(body).encode() if body is not None else b""),
            profile_id=self.profile["id"] if profile else None,
        )

    def test_bootstrap(self):
        status, payload, _ = api.handle(self.request("/api/bootstrap"))
        self.assertEqual(status, 200)
        self.assertGreater(payload["catalog"]["sources"], 100)
        self.assertTrue(payload["topics"])
        self.assertIn("ai", payload)
        self.assertEqual(payload["profile"]["id"], self.profile["id"])

    def test_feed(self):
        status, payload, _ = api.handle(self.request("/api/feed", query={"mode": "latest", "limit": "5"}))
        self.assertEqual(status, 200)
        self.assertIn("items", payload)
        self.assertLessEqual(len(payload["items"]), 5)

    def test_article_and_overview(self):
        db.execute("DELETE FROM articles WHERE guid='overview-fixture'")
        ingest_module.ingest._store_feed(
            FEED,
            [item(
                "City council approves major transit expansion",
                "https://example.com/overview-fixture",
                "<p>The city council voted 7-2 on Tuesday to approve a transit plan that adds twelve miles of bus lanes. "
                "Officials said construction will begin next spring and finish in 2028, at a cost of $40 million. "
                "Critics argued the money should go to schools instead, and said the vote was rushed.</p>",
                "Tue, 10 Nov 2026 18:30:00 GMT",
                guid="overview-fixture",
            )],
            Clusterer([]),
        )
        article_id = db.scalar("SELECT id FROM articles WHERE guid='overview-fixture'")
        status, payload, _ = api.handle(self.request(f"/api/articles/{article_id}"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["article"]["id"], article_id)
        status, overview, _ = api.handle(self.request(f"/api/articles/{article_id}/overview"))
        self.assertEqual(status, 200)
        self.assertIn(overview["engine"], ("ai", "extractive"))
        self.assertTrue(overview["summary"])

    def test_quiz_and_citations(self):
        article_id = db.scalar("SELECT id FROM articles ORDER BY id DESC LIMIT 1")
        status, quiz, _ = api.handle(self.request(f"/api/articles/{article_id}/quiz"))
        self.assertEqual(status, 200)
        self.assertIn("questions", quiz)
        status, cites, _ = api.handle(self.request(f"/api/articles/{article_id}/citations"))
        self.assertEqual(status, 200)
        self.assertIn("mla", cites["citations"])

    def test_save_and_notes_flow(self):
        article_id = db.scalar("SELECT id FROM articles ORDER BY id DESC LIMIT 1")
        status, payload, _ = api.handle(self.request(f"/api/articles/{article_id}/save", method="POST", body={"collection": "Test"}))
        self.assertEqual(status, 200)
        self.assertTrue(payload["saved"])
        status, payload, _ = api.handle(self.request(f"/api/articles/{article_id}/notes", method="POST", body={"body": "Remember this", "quote": "quote"}))
        self.assertEqual(status, 201)
        status, payload, _ = api.handle(self.request(f"/api/articles/{article_id}/notes"))
        self.assertTrue(payload["notes"])
        api.handle(self.request(f"/api/articles/{article_id}/save", method="DELETE"))
        self.assertEqual(profiles.saved(self.profile["id"]), [])

    def test_profile_patch(self):
        status, payload, _ = api.handle(self.request("/api/profile", method="PATCH", body={"prefs": {"theme": "light"}}))
        self.assertEqual(status, 200)
        self.assertEqual(payload["profile"]["prefs"]["theme"], "light")

    def test_search_endpoint(self):
        status, payload, _ = api.handle(self.request("/api/search", query={"q": "the", "limit": "3"}))
        self.assertEqual(status, 200)
        self.assertIn("results", payload)

    def test_unknown_article_is_404(self):
        with self.assertRaises(api.ApiError) as ctx:
            api.handle(self.request("/api/articles/999999"))
        self.assertEqual(ctx.exception.status, 404)

    def test_unknown_route_is_404(self):
        with self.assertRaises(api.ApiError) as ctx:
            api.handle(self.request("/api/nope"))
        self.assertEqual(ctx.exception.status, 404)

    def test_image_proxy_rejects_private_addresses(self):
        for target in ("http://127.0.0.1/secret.png", "http://localhost/a.png", "file:///etc/passwd"):
            with self.assertRaises(api.ApiError):
                api.handle(self.request("/api/img", query={"u": target}))

    def test_sports_endpoint_shape(self):
        status, payload, _ = api.handle(self.request("/api/sports", query={"leagues": "nba"}))
        self.assertEqual(status, 200)
        self.assertIn("events", payload)
        self.assertIn("fetched_at", payload)


if __name__ == "__main__":
    unittest.main()
