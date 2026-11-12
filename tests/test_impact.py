# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import impact, profiles
from pulse.db import db


def setUpModule():
    db.init()


class ImpactTests(unittest.TestCase):
    def setUp(self):
        db.execute("DELETE FROM roadmap_votes")
        db.execute("DELETE FROM feedback")
        self.profile = profiles.create("Impact tester")

    def test_metrics_are_honest_and_complete(self):
        data = impact.metrics(self.profile)
        self.assertIn("product", data)
        self.assertIn("diversity", data)
        self.assertIn("privacy", data)
        self.assertIn("method", data)
        self.assertGreaterEqual(data["product"]["sources"], 300)
        self.assertEqual(data["privacy"]["ads"], 0)
        self.assertIn("single-server", data["method"].lower())

    def test_report_and_press_kit_markdown(self):
        data = impact.metrics(self.profile)
        report = impact.report_markdown(data)
        kit = impact.press_kit_markdown(data)
        self.assertIn("# Pulse — Impact Report", report)
        self.assertIn("# Pulse — Press Kit", kit)
        self.assertIn("sources", kit)

    def test_roadmap_vote_round_trip(self):
        items = impact.roadmap(self.profile["id"])
        self.assertGreaterEqual(len(items), 8)
        item = items[0]
        self.assertFalse(item["voted"])
        voted = impact.vote(self.profile["id"], item["id"], True)
        self.assertTrue(voted["voted"])
        self.assertEqual(voted["votes"], 1)
        removed = impact.vote(self.profile["id"], item["id"], False)
        self.assertFalse(removed["voted"])
        self.assertEqual(removed["votes"], 0)

    def test_feedback_is_stored_and_counted(self):
        result = impact.add_feedback(self.profile["id"], "classroom", "A pilot note for the next lesson.")
        self.assertTrue(result["ok"])
        self.assertEqual(result["category"], "classroom")
        self.assertGreaterEqual(result["total"], 1)
        row = db.query_one("SELECT category, message FROM feedback ORDER BY id DESC LIMIT 1")
        self.assertEqual(row["category"], "classroom")
        self.assertIn("pilot note", row["message"])

    def test_feedback_rejects_empty_message(self):
        with self.assertRaises(ValueError):
            impact.add_feedback(self.profile["id"], "feature", "   ")


if __name__ == "__main__":
    unittest.main()
