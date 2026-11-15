import unittest
from datetime import date
from pathlib import Path

from pulse import holidays


class HolidayScheduleTests(unittest.TestCase):
    def test_has_24_distinct_seasons(self):
        self.assertEqual(len(holidays.SEASONS), 24)
        self.assertEqual(len({season["id"] for season in holidays.SEASONS}), 24)

    def test_current_day_is_normal_before_the_window_opens(self):
        data = holidays.current(date(2026, 11, 14))
        self.assertIsNone(data["active"])
        self.assertEqual(data["next"]["id"], "thanksgiving")

    def test_thanksgiving_window_opens_within_1_5_weeks(self):
        data = holidays.current(date(2026, 11, 16))
        self.assertEqual(data["active"]["id"], "thanksgiving")
        self.assertEqual(data["active"]["starts"], "2026-11-16")

    def test_christmas_then_kwanzaa_then_new_year(self):
        self.assertEqual(holidays.current(date(2026, 12, 24))["active"]["id"], "christmas")
        self.assertEqual(holidays.current(date(2026, 12, 26))["active"]["id"], "kwanzaa")
        self.assertEqual(holidays.current(date(2027, 1, 1))["active"]["id"], "new-year")

    def test_overlap_goes_to_the_more_significant_holiday(self):
        # Easter (83) overlaps Passover (68); Easter owns the shared days and
        # Passover resumes afterwards.
        self.assertEqual(holidays.current(date(2026, 3, 24))["active"]["id"], "passover")
        self.assertEqual(holidays.current(date(2026, 3, 27))["active"]["id"], "easter")

    def test_schedule_is_non_overlapping(self):
        items = holidays.schedule(date(2026, 1, 1), date(2027, 12, 31))
        for before, after in zip(items, items[1:]):
            self.assertLess(before.end, after.start, f"{before.id} overlaps {after.id}")

    def test_manifest_switches_icon_with_the_season(self):
        self.assertIn("/icon-192.png", holidays.manifest(date(2026, 12, 24))["icons"][0]["src"])
        self.assertIn("christmas", holidays.manifest(date(2026, 12, 24))["icons"][0]["src"])
        self.assertIn("v24", holidays.manifest(date(2026, 11, 14))["icons"][0]["src"])

    def test_archive_lists_all_24_and_their_icons(self):
        rows = holidays.archive(date(2026, 11, 14))
        self.assertEqual(len(rows), 24)
        for row in rows:
            self.assertIn("/icons/seasons/", row["icon"]["small"])
            self.assertTrue(Path("pulse/static" + row["icon"]["small"]).exists(), row["icon"]["small"])

    def test_icon_paths_are_stable_and_ordered(self):
        small, large, maskable, apple = holidays.icon_paths("diwali")
        self.assertTrue(small.endswith("icon-192.png"))
        self.assertTrue(large.endswith("icon-512.png"))
        self.assertTrue(maskable.endswith("icon-maskable.png"))
        self.assertTrue(apple.endswith("apple-touch-icon.png"))


if __name__ == "__main__":
    unittest.main()
