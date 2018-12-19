"""defines git timestamps"""
import time
from datetime import datetime, timedelta, timezone
import re
import itertools
import random
import calendar
from typing import List, Tuple


DATE_FMT = "%a %b %d %H:%M:%S %Y %z"
DATE_FMT_ALT = "%d.%m.%Y %H:%M:%S %z"


class TimeStamp:
    """ Class for dealing with git timestamps"""
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

    @staticmethod
    def utc_now():
        """ time in utc + offset"""
        utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
        utc_offset = timedelta(seconds=-utc_offset_sec)
        return  datetime.utcnow().replace(tzinfo=timezone(offset=utc_offset)).strftime(DATE_FMT)

    @staticmethod
    def now():
        """local time + offset"""
        utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
        utc_offset = timedelta(seconds=-utc_offset_sec)
        return datetime.now().replace(tzinfo=timezone(offset=utc_offset)).strftime(DATE_FMT)

    @staticmethod
    def format(timestamp) -> str:
        try:
            date = datetime.strptime(timestamp, DATE_FMT_ALT)
        except:
            date = datetime.strptime(timestamp, DATE_FMT)

        return date.strftime(DATE_FMT_ALT)

    @staticmethod
    def to_string(timestamp, git_like=False):
        """converts timestamp to string"""
        if git_like:
            return timestamp.strftime(DATE_FMT)
        return timestamp.strftime(DATE_FMT_ALT)

    def datelist(self, start_date, end_date, amount):
        """ returns datelist """
        start = datetime.strptime(start_date, DATE_FMT_ALT)
        end = datetime.strptime(end_date, DATE_FMT_ALT)
        diff = (end - start) / (amount - 1)
        datelist = []
        current_date = start
        datelist.append(self.to_string(current_date))
        for i in range(amount - 2):
            current_date += diff
            datelist.append(self.to_string(current_date))
        datelist.append(self.to_string(end))
        return datelist

    def reduce(self, timestamp: datetime) -> datetime:
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
        timestamp = self.enforce_limit(timestamp)
        return timestamp

    def enforce_limit(self, timestamp: datetime) -> datetime:
        if not self.limit:
            return timestamp
        start, end = self.limit
        if timestamp.hour < start:
            timestamp = timestamp.replace(hour=start, minute=0, second=0)
        if timestamp.hour >= end:
            timestamp = timestamp.replace(hour=end, minute=0, second=0)
        return timestamp

    @staticmethod
    def average(stamps: List[datetime]) -> timedelta:
        timedeltas = [max(stamps[i-1:i+1]) - min(stamps[i-1:i+1]) for i in range(1, len(stamps))]
        average_timedelta = sum(timedeltas, timedelta(0)) / len(timedeltas)
        return average_timedelta

    @staticmethod
    def seconds_to_gitstamp(seconds: int, time_zone: int) -> str:
        """ time in utc + offset"""
        return datetime.fromtimestamp(seconds, timezone(timedelta(seconds=-time_zone))).strftime(DATE_FMT)

    def get_next_timestamp(self, repo) -> datetime:
        """ returns the next timestamp"""
        if self.mode == "reduce":
            stamp = self.reduce(self.now())
            return stamp
        if self.mode == "average":
            commits = list(repo.iter_commits())
            list_of_stamps = [c.authored_datetime for c in commits]
            last_commit = commits[0]
            last_timestamp = last_commit.authored_datetime
            next_stamp = last_timestamp + self.average(list_of_stamps)
            return next_stamp
        raise ValueError(f"Unknown mode {self.mode}")
