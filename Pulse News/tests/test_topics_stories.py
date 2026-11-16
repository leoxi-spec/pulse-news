# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import stories, topics


class TopicTests(unittest.TestCase):
    def test_sports(self):
        primary, all_topics = topics.classify(
            "Lakers beat Celtics in overtime thriller",
            "LeBron James scored 40 points as the Lakers won their third straight game.",
            "sports", ("sports",),
        )
        self.assertEqual(primary, "sports")
        self.assertIn("sports", all_topics)

    def test_tech(self):
        primary, _ = topics.classify(
            "OpenAI releases new model",
            "The artificial intelligence company said the software is faster and cheaper for developers.",
            "tech", ("tech",),
        )
        self.assertEqual(primary, "tech")

    def test_feed_hint_is_a_prior_not_a_verdict(self):
        primary, _ = topics.classify(
            "NASA rover finds ancient riverbed on Mars",
            "Scientists said the discovery suggests water once flowed across the surface.",
            "sports", ("sports",),
        )
        self.assertIn(primary, ("space", "science"))

    def test_opinion_only_when_labelled(self):
        primary, _ = topics.classify("Opinion: Why the city should build more housing", "The case for denser neighbourhoods.", "politics")
        self.assertEqual(primary, "opinion")

    def test_entities(self):
        names = topics.entities("President Volodymyr Zelenskyy met Chancellor Olaf Scholz in Berlin on Tuesday.")
        self.assertTrue(any("Zelenskyy" in name for name in names))
        self.assertTrue(any("Scholz" in name for name in names))

    def test_graphic_detection(self):
        self.assertTrue(topics.is_graphic("At least four people were killed in the shooting."))
        self.assertFalse(topics.is_graphic("The council approved the budget on Tuesday."))


class StoryTests(unittest.TestCase):
    def test_tokens_ignore_stopwords_and_plurals(self):
        tokens = stories.tokens_for("The teams say the games are new")
        self.assertIn("team", tokens)
        self.assertNotIn("the", tokens)

    def test_same_story(self):
        self.assertTrue(stories.is_same_story(
            "Trump ally Jim Jordan elected House Republican leader",
            "Jim Jordan elected House Republican leader after party vote",
        ))

    def test_different_stories(self):
        self.assertFalse(stories.is_same_story(
            "Apple unveils new iPhone at September event",
            "Microsoft launches new Surface laptops for students",
        ))

    def test_clusterer_merges_and_extends(self):
        clusterer = stories.Clusterer([])
        story_id = 7
        clusterer.add(stories.StoryRef(id=story_id, title="Jim Jordan elected House Republican leader", topic="politics"))
        match = clusterer.match("Republicans pick Jim Jordan as minority leader", "politics")
        self.assertIsNotNone(match)
        self.assertEqual(match.id, story_id)
        clusterer.extend(match, "Republicans pick Jim Jordan as minority leader")
        again = clusterer.match("House Republicans elect Jim Jordan to serve as minority leader", "politics")
        self.assertIsNotNone(again)

    def test_clusterer_keeps_topics_apart(self):
        clusterer = stories.Clusterer([])
        clusterer.add(stories.StoryRef(id=1, title="Bitcoin price hits record high", topic="money"))
        self.assertIsNone(clusterer.match("Bitcoin mining uses more energy than some countries", "sports"))

    def test_identical_headline_across_topics_merges(self):
        clusterer = stories.Clusterer([])
        clusterer.add(stories.StoryRef(id=1, title="Bitcoin price hits record high", topic="money"))
        self.assertIsNotNone(clusterer.match("Bitcoin price hits record high", "sports"))

    def test_heat_and_breaking(self):
        from pulse.timeutil import iso
        self.assertTrue(stories.is_breaking(4, iso()))
        self.assertFalse(stories.is_breaking(1, iso()))
        self.assertGreater(stories.heat_score(6, 8, iso()), stories.heat_score(1, 1, iso()))

    def test_story_key_stable(self):
        self.assertEqual(
            stories.story_key("Big News: Something Happened Today"),
            stories.story_key("Big news something happened today"),
        )

    def test_best_title_prefers_specific(self):
        title = stories.best_title(["BREAKING!!!", "House Republicans elect Jim Jordan as minority leader"])
        self.assertIn("Jim Jordan", title)


if __name__ == "__main__":
    unittest.main()
