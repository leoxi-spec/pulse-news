import unittest

from pulse.feed import _seeded_head


class FeedSeedTests(unittest.TestCase):
    def setUp(self):
        self.ranked = [(index, 100 - index, []) for index in range(30)]

    def test_same_seed_keeps_the_front_page_stable(self):
        first = _seeded_head(self.ranked, "load-a", 10)
        second = _seeded_head(self.ranked, "load-a", 10)
        self.assertEqual([row[0] for row in first], [row[0] for row in second])

    def test_new_seed_changes_the_quality_pool_order(self):
        first = _seeded_head(self.ranked, "load-a", 10)
        second = _seeded_head(self.ranked, "load-b", 10)
        self.assertNotEqual([row[0] for row in first[:6]], [row[0] for row in second[:6]])

    def test_only_the_leading_pool_is_reordered(self):
        shuffled = _seeded_head(self.ranked, "load-a", 10)
        self.assertEqual(sorted(row[0] for row in shuffled[:10]), list(range(10)))
        self.assertEqual([row[0] for row in shuffled[10:]], list(range(10, 30)))
        self.assertNotEqual([row[0] for row in shuffled[:10]], list(range(10)))

    def test_no_seed_leaves_order_untouched(self):
        self.assertEqual(_seeded_head(self.ranked, None, 10), self.ranked)


if __name__ == "__main__":
    unittest.main()
