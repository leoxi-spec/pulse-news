# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import citations, search


class QueryParsingTests(unittest.TestCase):
    def test_plain_terms(self):
        parsed = search.parse_query("climate policy")
        self.assertEqual(parsed.terms, ["climate", "policy"])
        self.assertTrue(parsed.fts)

    def test_filter_language(self):
        parsed = search.parse_query("election source:bbc topic:tech after:2025-01-01 -trump is:breaking")
        self.assertEqual(parsed.sources, ["bbc"])
        self.assertEqual(parsed.topics, ["tech"])
        self.assertEqual(parsed.after, "2025-01-01")
        self.assertIn("trump", parsed.excluded)
        self.assertIn("breaking", parsed.flags)

    def test_source_resolution_by_domain(self):
        parsed = search.parse_query("story source:nytimes.com")
        self.assertEqual(parsed.sources, ["nyt"])

    def test_phrase(self):
        parsed = search.parse_query('"student loans" forgiveness')
        self.assertIn("student loans", parsed.phrases)
        self.assertIn("forgiveness", parsed.terms)

    def test_punctuation_does_not_break_fts(self):
        parsed = search.parse_query("C++ (python) [rust] {go} ^regex")
        expression = search._fts_expression(parsed)
        self.assertNotIn("(", expression)
        self.assertNotIn("^", expression)

    def test_empty_query(self):
        self.assertEqual(search.parse_query("").fts, "")
        self.assertEqual(search.parse_query("   ").terms, [])


class CitationTests(unittest.TestCase):
    ARTICLE = {
        "title": "Council approves transit plan",
        "author": "Jane Doe",
        "source_name": "Example News",
        "url": "https://example.com/story",
        "published_at": "2026-11-10T18:30:00Z",
    }

    def test_mla(self):
        text = citations.format_citation(self.ARTICLE, "mla")
        self.assertIn("Doe, Jane", text)
        self.assertIn("Council approves transit plan", text)
        self.assertIn("Example News", text)
        self.assertIn("10 November 2026", text)
        self.assertIn("https://example.com/story", text)

    def test_apa(self):
        text = citations.format_citation(self.ARTICLE, "apa")
        self.assertIn("Doe, J.", text)
        self.assertIn("(2026, November 10)", text)

    def test_chicago_and_harvard(self):
        self.assertIn("November 10, 2026", citations.format_citation(self.ARTICLE, "chicago"))
        self.assertIn("Available at", citations.format_citation(self.ARTICLE, "harvard"))

    def test_bibtex(self):
        text = citations.format_citation(self.ARTICLE, "bibtex")
        self.assertTrue(text.startswith("@misc{"))
        self.assertIn("publisher = {Example News}", text)

    def test_missing_date_and_author(self):
        text = citations.format_citation({"title": "Untitled piece", "source_name": "Wire"}, "mla")
        self.assertIn("n.d.", text)
        self.assertIn("Wire", text)

    def test_all_styles(self):
        styles = citations.available_styles()
        self.assertEqual(len(styles), 6)
        for style in styles:
            self.assertTrue(citations.format_citation(self.ARTICLE, style["id"]))


if __name__ == "__main__":
    unittest.main()
