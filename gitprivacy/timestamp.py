"""defines git timestamps"""
import time
from datetime import datetime, timedelta, timezone
import re
import itertools
import random
import calendar

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
    def pairwise(iterable):
        "s -> (s0,s1), (s1,s2), (s2, s3), ..."
        first, second = itertools.tee(iterable)
        next(second, None)
        return zip(first, second)

    @staticmethod
    def utc_now():
        """ time in utc + offset"""
        utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
        utc_offset = timedelta(seconds=-utc_offset_sec)
        return  datetime.utcnow().replace(tzinfo=timezone(offset=utc_offset)).strftime("%a %b %d %H:%M:%S %Y %z")

    @staticmethod
    def now():
        """local time + offset"""
        utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
        utc_offset = timedelta(seconds=-utc_offset_sec)
        return datetime.now().replace(tzinfo=timezone(offset=utc_offset)).strftime("%a %b %d %H:%M:%S %Y %z")

    @staticmethod
    def get_timezone(timestamp):
        """returns list of timestamp and corresponding timezone"""
        timezone = datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y %z").strftime("%z")
        return [timestamp, timezone]

    @staticmethod
    def format(timestamp) -> str:
        try:
            date = datetime.strptime(timestamp, "%d.%m.%Y %H:%M:%S %z")
        except:
            date = datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y %z")

        return date.strftime("%d.%m.%Y %H:%M:%S %z")

    @staticmethod
    def to_string(timestamp, git_like=False):
        """converts timestamp to string"""
        if git_like:
            return timestamp.strftime("%a %b %d %H:%M:%S %Y %z")
        return timestamp.strftime("%d.%m.%Y %H:%M:%S %z")

    def datelist(self, start_date, end_date, amount):
        """ returns datelist """
        start = datetime.strptime(start_date, "%d.%m.%Y %H:%M:%S %z")
        end = datetime.strptime(end_date, "%d.%m.%Y %H:%M:%S %z")
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
    def custom(year, month, day, hour, minute, second, timezone): # pylint: disable=too-many-arguments
        """Some custom time"""
        utc_offset = timedelta(hours=timezone)
        time_stamp = datetime(year, month, day, hour, minute, second).replace(
            tzinfo=timezone(offset=utc_offset)).strftime("%a %b %d %H:%M:%S %Y %z")
        return time_stamp

    def plus_hour(self, timestamp, hours):
        """adds hour to timestamp and returns"""
        timestamp = datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y %z")
        timestamp += timedelta(hours=hours)
        return timestamp.strftime("%a %b %d %H:%M:%S %Y %z")

    @staticmethod
    def average(stamp_list):
        """adds hour to timestamp and returns"""
        list_of_dates = []
        for first, second in stamp_list:
            stamp_first = datetime.strptime(first, "%a %b %d %H:%M:%S %Y %z")
            stamp_second = datetime.strptime(second, "%a %b %d %H:%M:%S %Y %z")
            list_of_dates.append(stamp_first)
            list_of_dates.append(stamp_second)
        timedeltas = [list_of_dates[i-1]-list_of_dates[i] for i in range(1, len(list_of_dates))]
        average_timedelta = sum(timedeltas, timedelta(0)) / len(timedeltas)
        return average_timedelta

    @staticmethod
    def seconds_to_gitstamp(seconds, time_zone):
        """ time in utc + offset"""
        return datetime.fromtimestamp(seconds, timezone(timedelta(seconds=-time_zone))).strftime("%a %b %d %H:%M:%S %Y %z")

    def get_next_timestamp(self, repo):
        """ returns the next timestamp"""
        if self.mode == "reduce":
            stamp = self.reduce(self.now())
            return stamp
        if self.mode == "average":
            commits = repo.git.rev_list(repo.active_branch.name).splitlines()
            list_of_stamps = []
            for a, b in self.pairwise(commits):
                list_of_stamps.append([self.seconds_to_gitstamp(repo.commit(a).authored_date, repo.commit(a).author_tz_offset),
                                       self.seconds_to_gitstamp(repo.commit(b).authored_date, repo.commit(b).author_tz_offset)])
            last_commit_id = commits[1]
            last_commit = commit = repo.commit(last_commit_id)
            last_timestamp = self.seconds_to_gitstamp(last_commit.authored_date, last_commit.author_tz_offset)
            next_stamp = last_timestamp + self.average(list_of_stamps)
            return next_stamp
        return None
