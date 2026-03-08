from datetime import datetime, timedelta
import re

from . import DateRedacter


class ResolutionDateRedacter(DateRedacter):
    """Resolution reducing timestamp redacter."""
    def __init__(self, pattern="s", limit=None, limit_day=None, mode="reduce"):
        self.mode = mode
        self.pattern = pattern
        self.limit = limit
        self.limit_days = None
        if limit:
            try:
                match = re.search('([0-9]+)-([0-9]+)', str(limit))
                self.limit = (int(match.group(1)), int(match.group(2)))
            except AttributeError:
                raise ValueError("Unexpected syntax for limit.")
        if limit_day:
            try:
                limit_day = str(limit_day)
                match = re.search('^([0-6])-([0-6])$', str(limit_day))
                if match:
                    start = int(match.group(1))
                    end = int(match.group(2))
                    if start > end:
                        raise ValueError("Start day can't be after end day for limit_day.")
                    self.limit_days = list(range(start, end + 1))
                    self.limit_days = {num: True for num in range(start, end + 1)}
                else:
                    limit_days = str(limit_day).split(',')
                    self.limit_days = {}
                    for day in limit_days:
                        day = int(day.strip())
                        if day < 0 or day > 6:
                            raise ValueError("Day must be between 0 and 6 for limit_day.")
                        self.limit_days[day] = True
            except AttributeError:
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
        timestamp = self.enforce_limits(timestamp)
        return timestamp

    def enforce_limits(self, timestamp: datetime) -> datetime:
        timestamp = self._enforce_limit(timestamp)
        return self._enforce_limit_day(timestamp)

    def _enforce_limit(self, timestamp: datetime) -> datetime:
        if not self.limit:
            return timestamp
        start, end = self.limit
        if timestamp.hour < start:
            timestamp = timestamp.replace(hour=start, minute=0, second=0)
        if timestamp.hour >= end:
            timestamp = timestamp.replace(hour=end, minute=0, second=0)
        return timestamp

    def _enforce_limit_day(self, timestamp: datetime) -> datetime:
        if not self.limit_days:
            return timestamp

        current_weekday = timestamp.weekday()
        if current_weekday in self.limit_days:
            return timestamp

        for days_back in range(1, 8): # Maximum 7 days to check all weekdays
            check_day = (current_weekday - days_back) % 7
            if check_day in self.limit_days:
                return timestamp - timedelta(days=days_back)

        # This should never happen if limit_days contains at least one weekday
        return timestamp
