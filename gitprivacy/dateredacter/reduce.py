from datetime import datetime, timezone
import re

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
            except AttributeError:
                raise ValueError("Unexpected syntax for limit.")

    def redact(self, timestamp: datetime) -> datetime:
        """Reduces timestamp precision for the parts specifed by the pattern using
        M: month, d: day, h: hour, m: minute, s: second, z: timezone (to UTC).

        Example: A pattern of 's' sets the seconds to 0.

        'z' converts the timestamp to UTC (offset +00:00) and thereby removes
        the timezone offset as a location fingerprint. It is applied before the
        precision reductions, so those operate on the resulting UTC wall-clock
        time (and, with a 'limit', the working-hours window is interpreted in
        UTC as well)."""

        if "z" in self.pattern:
            timestamp = self._to_utc(timestamp)
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

    @staticmethod
    def _to_utc(timestamp: datetime) -> datetime:
        """Convert an aware timestamp to UTC, preserving the instant. A naive
        timestamp is assumed to already be UTC and merely tagged as such, so the
        result is deterministic regardless of the host's local timezone."""
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    def _enforce_limit(self, timestamp: datetime) -> datetime:
        if not self.limit:
            return timestamp
        start, end = self.limit
        if timestamp.hour < start:
            timestamp = timestamp.replace(hour=start, minute=0, second=0)
        if timestamp.hour >= end:
            timestamp = timestamp.replace(hour=end, minute=0, second=0)
        return timestamp
