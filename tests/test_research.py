# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import api, citations, feed, profiles
from pulse.db import db
from pulse.sources import FEEDS, SOURCES


def setUpModule():
    db.init()
    db.seed_catalog(SOURCES, FEEDS)


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.profile = profiles.create("Research Test")
        db.execute("DELETE FROM articles WHERE guid LIKE 'research-%'")
        for index, (state, words) in enumerate((("extracted", 820), ("linkonly", 20)), start=1):
            db.execute(
                """INSERT INTO articles(guid, source_id, url, title, summary, author, published_at,
                                        first_seen_at, last_seen_at, primary_topic, word_count,
                                        reading_minutes, content_text, content_state)
                   VALUES(?,?,?,?,?,?,?,datetime('now'),datetime('now'),'science',?,?,?,?)""",
                (
                    f"research-{index}", "bbc", f"https://example.com/research-{index}",
                    f"Quantum result number {index}", "A compact summary of the research result.",
                    "Jane Doe", "2026-11-09T10:00:00Z", words, max(1, words // 225),
                    "Body text " * words if state == "extracted" else "short", state,
                ),
            )
        self.article_id = db.scalar("SELECT id FROM articles WHERE guid='research-1'")
        profiles.save(self.profile["id"], self.article_id, "Essay")
        profiles.add_note(self.profile["id"], self.article_id, "Useful for the methods section", quote="Quantum result")

    def tearDown(self):
        profiles.delete(self.profile["id"])
        db.execute("DELETE FROM articles WHERE guid LIKE 'research-%'")

    def handle(self, path, method="GET", query=None, body=None):
        return api.handle(api.Request(
            method=method, path=path, query=query or {},
            body=(__import__("json").dumps(body).encode() if body is not None else b""),
            profile_id=self.profile["id"],
        ))

    def test_bibliography(self):
        status, payload, _ = self.handle("/api/research/bibliography", query={"style": "mla", "include_notes": "1"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["style"], "mla")
        self.assertEqual(payload["count"], 1)
        entry = payload["entries"][0]
        self.assertIn("Doe, Jane", entry["citation"])
        self.assertIn("Quantum result number 1", entry["citation"])
        self.assertIn("https://example.com/research-1", entry["citation"])
        self.assertIn("Doe", payload["combined"])
        self.assertEqual(len(payload["notes"]), 1)
        self.assertIn("BBC", payload["notes"][0]["citation"])

    def test_bibliography_style_switch(self):
        _, apa, _ = self.handle("/api/research/bibliography", query={"style": "apa"})
        self.assertIn("(2026, November 9)", apa["entries"][0]["citation"])
        _, bib, _ = self.handle("/api/research/bibliography", query={"style": "bibtex"})
        self.assertTrue(bib["entries"][0]["citation"].startswith("@misc{"))

    def test_invalid_style_falls_back(self):
        status, payload, _ = self.handle("/api/research/bibliography", query={"style": "harvard-ish"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["style"], "mla")

    def test_manual_citation(self):
        status, payload, _ = self.handle("/api/research/cite", method="POST", body={
            "title": "A book about rivers",
            "author": "Alex Kim",
            "outlet": "River Press",
            "published_at": "2019-04-02",
            "url": "",
        })
        self.assertEqual(status, 200)
        self.assertIn("Kim", payload["citations"]["mla"])
        self.assertIn("River Press", payload["citations"]["apa"])
        self.assertEqual(len(payload["styles"]), 6)

    def test_manual_citation_requires_title(self):
        with self.assertRaises(api.ApiError) as ctx:
            self.handle("/api/research/cite", method="POST", body={"title": ""})
        self.assertEqual(ctx.exception.status, 400)

    def test_readable_stream_only_returns_full_text(self):
        page = feed.feed_page(self.profile, mode="readable", limit=10)
        ids = {item["id"] for item in page["items"]}
        self.assertIn(self.article_id, ids)
        for item in page["items"]:
            self.assertTrue(item["has_full_text"] or item["content_state"] == "extracted")


if __name__ == "__main__":
    unittest.main()
