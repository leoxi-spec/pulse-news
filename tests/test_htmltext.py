# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import htmltext


SAMPLE = """
<html><head><title>Fallback title</title>
<meta property="og:title" content="Council approves transit plan">
<meta property="og:image" content="https://example.com/lead.jpg">
<script>window.tracker = 'do not keep me';</script>
</head><body>
<nav><a href="/">Home</a><a href="/world">World</a></nav>
<article>
  <h1>Council approves transit plan</h1>
  <p>By Jane Doe</p>
  <p>Jane Doe is a transportation reporter covering the city council.</p>
  <p>Published 11/10/2026</p>
  <p>The city council voted 7-2 on Tuesday to approve a new transit plan that adds twelve miles of bus lanes.</p>
  <p>Officials said construction will begin next spring and finish in 2028, with a total cost of $40 million.</p>
  <p>Critics argued the money should go to schools, and said the vote was rushed.</p>
  <h2>What happens next</h2>
  <p>The mayor is expected to sign the plan within two weeks, according to her office.</p>
</article>
<footer>All rights reserved. Cookie policy.</footer>
</body></html>
"""


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.result = htmltext.extract_article(SAMPLE, "https://example.com/story")

    def test_title_and_image(self):
        self.assertEqual(self.result.title, "Council approves transit plan")
        self.assertEqual(self.result.image, "https://example.com/lead.jpg")

    def test_boilerplate_is_removed(self):
        text = self.result.text
        self.assertNotIn("transportation reporter", text)
        self.assertNotIn("Published 11/10/2026", text)
        self.assertNotIn("Cookie policy", text)
        self.assertNotIn("do not keep me", text)

    def test_body_survives(self):
        self.assertIn("twelve miles of bus lanes", self.result.text)
        self.assertIn("$40 million", self.result.text)
        self.assertGreater(self.result.word_count, 40)

    def test_headings_are_preserved(self):
        kinds = [b.type for b in self.result.blocks]
        self.assertIn("h2", kinds)

    def test_text_only_never_returns_markup(self):
        evil = "<article><p>Hello <script>alert(1)</script> &lt;b&gt;world&lt;/b&gt; <img src=x onerror=alert(1)>. This paragraph is deliberately long enough to survive extraction so we can prove that only text comes out the other side, never markup.</p></article>"
        parsed = htmltext.extract_article(evil, "https://example.com/x")
        joined = parsed.text
        self.assertNotIn("<script", joined)
        self.assertNotIn("<img", joined)
        self.assertIn("Hello", joined)

    def test_paywall_detection(self):
        paywalled = "<html><body><article><p>Subscribe to continue reading this article.</p></article></body></html>"
        parsed = htmltext.extract_article(paywalled, "https://example.com/p")
        self.assertTrue(parsed.paywall)

    def test_empty_input(self):
        self.assertEqual(htmltext.extract_article("").blocks, [])


class ProseTests(unittest.TestCase):
    ARTICLE = (
        "The city council voted 7-2 on Tuesday to approve a new transit plan. "
        "The plan adds twelve miles of bus lanes and is expected to cost $40 million. "
        "Officials said construction will begin next spring and finish in 2028. "
        "Critics argued the money should go to schools instead. "
        "The mayor is expected to sign the plan within two weeks."
    )

    def test_summary_uses_real_sentences(self):
        summary = htmltext.summarize(self.ARTICLE, 2)
        for sentence in htmltext.sentences(summary):
            self.assertIn(sentence, self.ARTICLE)

    def test_key_points(self):
        points = htmltext.key_points(self.ARTICLE, 3)
        self.assertTrue(1 <= len(points) <= 3)
        for point in points:
            self.assertIn(point.rstrip("."), self.ARTICLE)

    def test_fragment_filter(self):
        self.assertTrue(htmltext.is_fragment("9. Jaguars receive: Jordan Davis Eagles receive: 2027 pick"))
        self.assertFalse(htmltext.is_fragment("The council approved the plan on Tuesday after a long debate."))

    def test_reading_time(self):
        self.assertEqual(htmltext.reading_minutes("word " * 450), 2)
        self.assertEqual(htmltext.reading_minutes(""), 1)

    def test_byline_is_removed_from_summaries(self):
        summary = htmltext.clean_summary(
            "ByLily Jamali, North America Technology correspondent and Peter Hoskins, Business reporter "
            "One of the AI firms at the centre of the story said it would cooperate."
        )
        self.assertEqual(summary, "One of the AI firms at the centre of the story said it would cooperate.")

    def test_inline_byline_is_removed(self):
        summary = htmltext.clean_summary(
            "Nvidia has become the face of the AI boom ByKali Hays, Technology reporter and more text."
        )
        self.assertTrue(summary.startswith("Nvidia has become"))

    def test_by_contrast_is_not_a_byline(self):
        text = "By contrast, the reporter said the plan would cost more than expected."
        self.assertEqual(htmltext.clean_summary(text), text)

    def test_trailing_continue_reading_is_removed(self):
        self.assertEqual(
            htmltext.clean_summary("The council approved the plan. Continue reading"),
            "The council approved the plan.",
        )

    def test_clean_title_strips_site_suffix(self):
        self.assertEqual(htmltext.clean_title("Big news today | Example News"), "Big news today")

    def test_simplify_cannot_add_words(self):
        simplified = htmltext.simplify(self.ARTICLE, 3)
        for sentence in htmltext.sentences(simplified):
            self.assertIn(sentence, self.ARTICLE)


if __name__ == "__main__":
    unittest.main()
