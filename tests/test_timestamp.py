import unittest
from datetime import datetime, timedelta

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
