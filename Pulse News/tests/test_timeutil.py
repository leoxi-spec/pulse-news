# Tests must never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest
from datetime import datetime, timedelta, timezone

from pulse import timeutil


class DateParsingTests(unittest.TestCase):
    def test_rfc822(self):
        dt, confidence, raw = timeutil.parse_date("Tue, 10 Nov 2026 18:30:00 GMT")
        self.assertEqual(confidence, "exact")
        self.assertEqual(dt.isoformat(), "2026-11-10T18:30:00+00:00")
        self.assertEqual(raw, "Tue, 10 Nov 2026 18:30:00 GMT")

    def test_iso_with_offset_is_converted_to_utc(self):
        dt, confidence, _ = timeutil.parse_date("2026-11-10T20:30:00+09:00")
        self.assertEqual(confidence, "exact")
        self.assertEqual(dt.hour, 11)
        self.assertEqual(dt.day, 10)

    def test_compact_iso(self):
        dt, _, _ = timeutil.parse_date("20261110T183000Z")
        self.assertEqual(dt.isoformat(), "2026-11-10T18:30:00+00:00")

    def test_date_only_is_flagged(self):
        dt, confidence, _ = timeutil.parse_date("2026-11-10")
        self.assertEqual(confidence, "day")
        self.assertEqual((dt.year, dt.month, dt.day), (2026, 11, 10))

    def test_future_timestamps_are_clamped_and_inferred(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        dt, confidence, raw = timeutil.parse_date(future)
        self.assertEqual(confidence, "inferred")
        self.assertLessEqual(dt, datetime.now(timezone.utc) + timedelta(minutes=2))
        self.assertEqual(raw, future)

    def test_garbage_is_unknown(self):
        dt, confidence, _ = timeutil.parse_date("yesterday-ish")
        self.assertIsNone(dt)
        self.assertEqual(confidence, "unknown")

    def test_empty(self):
        self.assertEqual(timeutil.parse_date(None), (None, "unknown", None))

    def test_written_dates(self):
        dt, _, _ = timeutil.parse_date("10 November 2026 06:05 +0000")
        self.assertEqual((dt.day, dt.hour, dt.minute), (10, 6, 5))

    def test_relative_labels(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(timeutil.relative((now - timedelta(seconds=10)).isoformat()), "just now")
        self.assertIn("min", timeutil.relative((now - timedelta(minutes=20)).isoformat()))
        self.assertIn("hr", timeutil.relative((now - timedelta(hours=3)).isoformat()))
        self.assertIn("day", timeutil.relative((now - timedelta(days=2)).isoformat()))

    def test_small_future_skew_reads_as_just_now(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(timeutil.relative((now + timedelta(minutes=3)).isoformat()), "just now")

    def test_freshness_buckets(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(timeutil.freshness((now - timedelta(minutes=5)).isoformat()), "breaking")
        self.assertEqual(timeutil.freshness((now - timedelta(hours=8)).isoformat()), "today")
        self.assertEqual(timeutil.freshness((now - timedelta(days=30)).isoformat()), "archive")

    def test_machine_roundtrip(self):
        stamp = timeutil.iso(datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
        self.assertEqual(timeutil.machine(stamp), "2020-01-02T03:04:05Z")
        self.assertEqual(timeutil.parse_iso(stamp).year, 2020)


if __name__ == "__main__":
    unittest.main()
