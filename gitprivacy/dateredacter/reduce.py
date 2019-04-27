from datetime import datetime, timedelta, timezone
import re
import time
from typing import List, Tuple

from . import DateRedacter


class ResolutionDateRedacter(DateRedacter):
    """Resolution reducing timestamp redacter."""
    def __init__(self, pattern="s", limit=None, mode="reduce"):
        self.mode = mode
        self.pattern = pattern
        self.limit = limit
        if limit:
            try:
                match = re.search('([0-9]+)-([0-9]+)', str(limit))
                self.limit = (int(match.group(1)), int(match.group(2)))
            except AttributeError as e:
                raise ValueError("Unexpected syntax for limit.")

    def redact(self, timestamp: datetime) -> datetime:
        """Reduces timestamp precision for the parts specifed by the pattern using
        M: month, d: day, h: hour, m: minute, s: second.

        Example: A pattern of 's' sets the seconds to 0."""

        if "M" in self.pattern:
            timestamp = timestamp.replace(month=1)
        if "d" in self.pattern:
            timestamp = timestamp.replace(day=1)
        if "h" in self.pattern:
            timestamp = timestamp.replace(hour=0)
        if "m" in self.pattern:
            timestamp = timestamp.replace(minute=0)
        if "s" in self.pattern:
            timestamp = timestamp.replace(second=0)
        timestamp = self._enforce_limit(timestamp)
        return timestamp

    def _enforce_limit(self, timestamp: datetime) -> datetime:
        if not self.limit:
            return timestamp
        start, end = self.limit
        if timestamp.hour < start:
            timestamp = timestamp.replace(hour=start, minute=0, second=0)
        if timestamp.hour >= end:
            timestamp = timestamp.replace(hour=end, minute=0, second=0)
        return timestamp
