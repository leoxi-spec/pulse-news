import unittest
from pulse.rank import diversify


def row(i, topic):
    return {"id": i, "primary_topic": topic, "source_id": f"src-{i}", "story_id": None}


class ReadingMixTests(unittest.TestCase):
    def test_quota_follows_reading_percentages(self):
        rows = [row(i, "sports") for i in range(20)] + [row(100 + i, "world") for i in range(20)]
        chosen = diversify(rows, limit=10, mix={"sports": 0.5, "world": 0.5}, per_source=5)
        topics = [item["primary_topic"] for item in chosen]
        self.assertEqual(topics.count("sports"), 5)
        self.assertEqual(topics.count("world"), 5)

    def test_remainder_is_filled(self):
        rows = [row(i, "sports") for i in range(10)]
        chosen = diversify(rows, limit=6, mix={"sports": 0.2}, per_source=10)
        self.assertEqual(len(chosen), 6)


if __name__ == "__main__":
    unittest.main()
