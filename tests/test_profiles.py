# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import profiles, rank
from pulse.db import db
from pulse.sources import FEEDS, SOURCES


def setUpModule():
    db.init()
    db.seed_catalog(SOURCES, FEEDS)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        db.init()
        db.seed_catalog(SOURCES, FEEDS)
        self.profile = profiles.create("Test Student")

    def tearDown(self):
        profiles.delete(self.profile["id"])

    def test_defaults(self):
        self.assertFalse(self.profile["onboarded"])
        self.assertEqual(self.profile["level"], 1)
        self.assertEqual(self.profile["prefs"]["theme"], "system")
        self.assertEqual(self.profile["daily_goal"], 5)

    def test_age_bands_scale_reading(self):
        self.assertEqual([profiles.goal_for_age(age) for age in (6, 10, 14, 18)], [2, 4, 6, 8])
        self.assertEqual(profiles.length_for_age(6), "short")
        self.assertEqual(profiles.length_for_age(13), "medium")
        self.assertEqual(profiles.length_for_age(17), "long")
        updated = profiles.update(self.profile["id"], survey={"age": 10})
        self.assertEqual(updated["prefs"]["daily_goal"], 4)
        self.assertEqual(updated["prefs"]["reading_length"], "short")

    def test_survey_sanitisation(self):
        updated = profiles.update(
            self.profile["id"],
            survey={
                "topics": {"tech": 9, "sports": -2, "nonsense": 3},
                "sources": ["bbc", "not-a-source"],
                "keywords": ["  climate  ", ""],
                "grade": "11",
                "reading_length": "long",
                "region": "us",
                "daily_goal": 500,
            },
            onboarded=True,
        )
        survey = updated["survey"]
        self.assertEqual(survey["topics"]["tech"], 3)
        self.assertEqual(survey["topics"]["sports"], 0)
        self.assertNotIn("nonsense", survey["topics"])
        self.assertEqual(survey["sources"], ["bbc"])
        self.assertEqual(survey["keywords"], ["climate"])
        self.assertEqual(survey["reading_length"], "long")
        self.assertEqual(survey["region"], "US")
        self.assertTrue(updated["onboarded"])

    def test_prefs_sanitisation(self):
        updated = profiles.update(self.profile["id"], prefs={"theme": "neon", "text_size": 99, "daily_goal": 0})
        self.assertEqual(updated["prefs"]["theme"], "system")
        self.assertEqual(updated["prefs"]["text_size"], 4)
        self.assertEqual(updated["prefs"]["daily_goal"], 1)

    def test_follows_sync_from_survey(self):
        profiles.update(self.profile["id"], survey={"topics": {"tech": 3, "sports": 1}, "sources": ["bbc"]})
        rows = db.query("SELECT kind, value FROM follows WHERE profile_id=?", (self.profile["id"],))
        kinds = {(row["kind"], row["value"]) for row in rows}
        self.assertIn(("topic", "tech"), kinds)
        self.assertIn(("source", "bbc"), kinds)
        self.assertNotIn(("topic", "sports"), kinds)

    def test_reading_awards_xp_and_streak(self):
        progress = profiles.record_event(self.profile["id"], "read", article_id=None, value=90)
        self.assertGreater(progress["xp_awarded"], 0)
        self.assertEqual(progress["streak"]["count"], 1)
        self.assertEqual(progress["today"]["read"], 1)

    def test_duplicate_read_does_not_farm_xp(self):
        db.execute(
            "INSERT INTO articles(guid, source_id, url, title, first_seen_at, last_seen_at) "
            "VALUES('t1','bbc','https://example.com/t1','Test article',datetime('now'),datetime('now'))"
        )
        article_id = db.scalar("SELECT id FROM articles WHERE guid='t1'")
        first = profiles.record_event(self.profile["id"], "read", article_id=article_id, value=60)
        second = profiles.record_event(self.profile["id"], "read", article_id=article_id, value=60)
        self.assertGreater(first["xp_awarded"], 0)
        self.assertEqual(second["xp_awarded"], 0)

    def test_save_and_notes(self):
        db.execute(
            "INSERT INTO articles(guid, source_id, url, title, first_seen_at, last_seen_at) "
            "VALUES('t2','bbc','https://example.com/t2','Saved article',datetime('now'),datetime('now'))"
        )
        article_id = db.scalar("SELECT id FROM articles WHERE guid='t2'")
        profiles.save(self.profile["id"], article_id, "Revision")
        saved = profiles.saved(self.profile["id"])
        self.assertTrue(any(item["id"] == article_id for item in saved))
        self.assertEqual(profiles.collections(self.profile["id"])[0]["collection"], "Revision")
        profiles.add_note(self.profile["id"], article_id, "Useful for the essay", quote="Council voted 7-2")
        notes = profiles.notes(self.profile["id"], article_id)
        self.assertEqual(len(notes), 1)
        self.assertIn("essay", notes[0]["body"])
        profiles.unsave(self.profile["id"], article_id)
        self.assertEqual(profiles.saved(self.profile["id"]), [])

    def test_export_and_delete(self):
        data = profiles.export(self.profile["id"])
        self.assertEqual(data["profile"]["id"], self.profile["id"])
        self.assertIn("activity", data)
        profiles.delete(self.profile["id"])
        self.assertIsNone(profiles.get(self.profile["id"]))

    def test_badges_shape(self):
        badges = profiles.badges(profiles.get(self.profile["id"]))
        self.assertTrue(badges)
        self.assertTrue(all({"id", "label", "earned"} <= set(badge) for badge in badges))

    def test_unknown_profile_event_fails(self):
        with self.assertRaises(ValueError):
            profiles.record_event("does-not-exist", "read")


class LevelTests(unittest.TestCase):
    def test_levels_rise_with_xp(self):
        level_0, _, _, title_0 = rank.level_for_xp(0)
        level_1, _, _, _ = rank.level_for_xp(200)
        level_2, _, _, _ = rank.level_for_xp(2000)
        self.assertEqual(level_0, 1)
        self.assertGreater(level_1, level_0)
        self.assertGreater(level_2, level_1)
        self.assertEqual(title_0, "Rookie")

    def test_profile_model_uses_survey_and_engagement(self):
        profile = profiles.create("Model Test")
        try:
            profiles.update(profile["id"], survey={"topics": {"tech": 3}, "sources": ["verge"]})
            model = rank.build_model(profile["id"], profiles.get(profile["id"])["survey"], {})
            self.assertGreater(model.topic_weight("tech"), model.topic_weight("food"))
            self.assertIn("verge", model.followed_sources)
        finally:
            profiles.delete(profile["id"])


if __name__ == "__main__":
    unittest.main()
