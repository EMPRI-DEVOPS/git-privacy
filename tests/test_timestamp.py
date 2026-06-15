import unittest
from datetime import datetime, timedelta, timezone

from gitprivacy.dateredacter import ResolutionDateRedacter


class ReduceTestCase(unittest.TestCase):
    def setUp(self):
        self.full = datetime(year=2018, month=12, day=18,
                             hour=14, minute=42, second=13)

    def test_seconds(self):
        ts = ResolutionDateRedacter(mode="reduce", pattern="s")
        expected = datetime(year=2018, month=12, day=18,
                            hour=14, minute=42, second=0)
        self.assertEqual(ts.redact(self.full), expected)

    def test_minute(self):
        ts = ResolutionDateRedacter(mode="reduce", pattern="m")
        expected = datetime(year=2018, month=12, day=18,
                            hour=14, minute=0, second=13)
        self.assertEqual(ts.redact(self.full), expected)

    def test_hour(self):
        ts = ResolutionDateRedacter(mode="reduce", pattern="h")
        expected = datetime(year=2018, month=12, day=18,
                            hour=0, minute=42, second=13)
        self.assertEqual(ts.redact(self.full), expected)

    def test_day(self):
        ts = ResolutionDateRedacter(mode="reduce", pattern="d")
        expected = datetime(year=2018, month=12, day=1,
                            hour=14, minute=42, second=13)
        self.assertEqual(ts.redact(self.full), expected)

    def test_month(self):
        ts = ResolutionDateRedacter(mode="reduce", pattern="M")
        expected = datetime(year=2018, month=1, day=18,
                            hour=14, minute=42, second=13)
        self.assertEqual(ts.redact(self.full), expected)


class TimezoneTestCase(unittest.TestCase):
    def setUp(self):
        # 14:42:13 at UTC+02:00  ==  12:42:13 UTC (same instant)
        self.cet = datetime(year=2018, month=12, day=18,
                            hour=14, minute=42, second=13,
                            tzinfo=timezone(timedelta(hours=2)))

    def test_to_utc(self):
        ts = ResolutionDateRedacter(mode="reduce", pattern="z")
        result = ts.redact(self.cet)
        expected = datetime(year=2018, month=12, day=18,
                            hour=12, minute=42, second=13,
                            tzinfo=timezone.utc)
        self.assertEqual(result, expected)
        self.assertEqual(result.utcoffset(), timedelta(0))

    def test_preserves_instant(self):
        ts = ResolutionDateRedacter(mode="reduce", pattern="z")
        self.assertEqual(ts.redact(self.cet).timestamp(), self.cet.timestamp())

    def test_applied_before_reductions(self):
        # 01:30 +02:00 -> 2018-12-17 23:30 UTC -> 'h' zeroes the hour -> 00:30 UTC.
        # The date rolling back to the 17th proves the UTC conversion ran first.
        ts = ResolutionDateRedacter(mode="reduce", pattern="hz")
        early = datetime(year=2018, month=12, day=18,
                         hour=1, minute=30, second=0,
                         tzinfo=timezone(timedelta(hours=2)))
        expected = datetime(year=2018, month=12, day=17,
                            hour=0, minute=30, second=0,
                            tzinfo=timezone.utc)
        self.assertEqual(ts.redact(early), expected)

    def test_naive_assumed_utc(self):
        ts = ResolutionDateRedacter(mode="reduce", pattern="z")
        naive = datetime(year=2018, month=12, day=18,
                         hour=14, minute=42, second=13)
        result = ts.redact(naive)
        self.assertEqual(result.utcoffset(), timedelta(0))
        self.assertEqual(result.replace(tzinfo=None), naive)


class LimitTestCase(unittest.TestCase):
    def test_before(self):
        ts = ResolutionDateRedacter(limit="9-17")
        full = datetime(year=2018, month=12, day=18,
                        hour=8, minute=42, second=15)
        expected = datetime(year=2018, month=12, day=18,
                            hour=9, minute=0, second=0)
        self.assertEqual(ts.limit, (9, 17))
        self.assertEqual(ts._enforce_limit(full), expected)

    def test_after(self):
        ts = ResolutionDateRedacter(limit="9-17")
        full = datetime(year=2018, month=12, day=18,
                        hour=17, minute=42, second=15)
        expected = datetime(year=2018, month=12, day=18,
                            hour=17, minute=0, second=0)
        self.assertEqual(ts.limit, (9, 17))
        self.assertEqual(ts._enforce_limit(full), expected)
