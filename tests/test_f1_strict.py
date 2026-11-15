import unittest

from pulse import sources, topics


class StrictFormulaOneTests(unittest.TestCase):
    def test_accepts_formula_one_stories(self):
        for title in (
            "Max Verstappen wins the Las Vegas Grand Prix",
            "F1 rookie Isack Hadjar reveals he almost quit racing",
            "Ferrari's Lewis Hamilton and Charles Leclerc test the new car",
            "Las Vegas Grand Prix schedule and how to watch",
        ):
            self.assertTrue(topics.is_f1(title), title)

    def test_rejects_other_racing_and_events(self):
        for title in (
            "America's Cup: New Zealand wins the deciding race",
            "Why the 2027 MotoGP regulations change aerodynamics",
            "Kyle Larson clinches his third NASCAR Cup title",
            "ISU Figure Skating Grand Prix Skate America",
            "Grosjean ends his IndyCar season in 19th",
            "Tour de France stage winner attacks on the final climb",
        ):
            self.assertFalse(topics.is_f1(title), title)

    def test_non_f1_motorsport_stories_are_filed_as_sports(self):
        primary, _ = topics.classify(
            "Why the 2027 MotoGP regulations change aerodynamics",
            feed_topic="motorsport",
            source_topics=("motorsport", "sports"),
        )
        self.assertEqual(primary, "sports")

    def test_f1_motorsport_stories_keep_the_f1_lane(self):
        primary, _ = topics.classify(
            "Max Verstappen wins the Las Vegas Grand Prix",
            feed_topic="motorsport",
            source_topics=("motorsport", "sports"),
        )
        self.assertEqual(primary, "motorsport")

    def test_catalog_has_a_large_f1_desk(self):
        f1_sources = [source for source in sources.SOURCES.values() if "motorsport" in source.topics]
        self.assertGreaterEqual(len(sources.SOURCES), 500)
        self.assertGreaterEqual(len(f1_sources), 20)
        self.assertGreaterEqual(sum(len(source.feeds) for source in f1_sources), 20)

    def test_f1_search_intent_is_explicit(self):
        self.assertTrue(topics.wants_f1("f1"))
        self.assertTrue(topics.wants_f1("Formula 1 news"))
        self.assertFalse(topics.wants_f1("motogp"))


if __name__ == "__main__":
    unittest.main()
