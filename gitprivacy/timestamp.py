"""defines git timestamps"""
import time
import datetime
import re
import itertools
import random
import calendar
from git import Repo # pylint: disable=unused-import

class TimeStamp:
    """ Class for dealing with git timestamps"""
    def __init__(self, pattern="s", limit=False, mode="simple"):
        super(TimeStamp, self).__init__()
        foo_bar = re.search('([0-9]+)-([0-9]+)', str(limit))
        if limit is not False:
            self.limit = [int(foo_bar.group(1)), int(foo_bar.group(2))]
        self.mode = mode
        self.pattern = pattern

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
        utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
        return  datetime.datetime.utcnow().replace(tzinfo=datetime.timezone(offset=utc_offset)).strftime("%a %b %d %H:%M:%S %Y %z")

    @staticmethod
    def now():
        """local time + offset"""
        utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
        utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
        return datetime.datetime.now().replace(tzinfo=datetime.timezone(offset=utc_offset)).strftime("%a %b %d %H:%M:%S %Y %z")

    @staticmethod
    def get_timezone(timestamp):
        """returns list of timestamp and corresponding timezone"""
        timezone = datetime.datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y %z").strftime("%z")
        return [timestamp, timezone]

    @staticmethod
    def simple(timestamp):
        """parses timestamp for anonymizing Repo"""
        try:
            date = datetime.datetime.strptime(timestamp, "%d.%m.%Y %H:%M:%S %z")
        except:
            date = datetime.datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y %z")

        return date.strftime("%d.%m.%Y %H:%M:%S %z")

    @staticmethod
    def to_string(timestamp, git_like=False):
        """converts timestamp to string"""
        if git_like:
            return timestamp.strftime("%a %b %d %H:%M:%S %Y %z")
        return timestamp.strftime("%d.%m.%Y %H:%M:%S %z")

    def datelist(self, start_date, end_date, amount):
        """ returns datelist """
        start = datetime.datetime.strptime(start_date, "%d.%m.%Y %H:%M:%S %z")
        end = datetime.datetime.strptime(end_date, "%d.%m.%Y %H:%M:%S %z")
        diff = (end - start) / (amount - 1)
        datelist = []
        current_date = start
        datelist.append(self.to_string(current_date))
        for i in range(amount - 2):
            current_date += diff
            datelist.append(self.to_string(current_date))
        datelist.append(self.to_string(end))
        return datelist




    def enforce_limit(self, timestamp):
        """the limit stored in the object will be enforced on the timestamp"""
        if timestamp.hour < self.limit[0]:
            diff_to_limit = self.limit[0] - timestamp.hour
            timestamp += datetime.timedelta(hours=diff_to_limit)
        elif timestamp.hour > self.limit[1]:
            diff_to_limit = timestamp.hour - self.limit[1]
            timestamp -= datetime.timedelta(hours=diff_to_limit)
        return timestamp

    def reduce(self, input_timestamp):
        """replaces the values specifed by the pattern
            y = Year
            M = Month
            d = day
            h = hour
            m = minute
            s = second"""
        try:
            timestamp = datetime.datetime.strptime(input_timestamp, "%a %b %d %H:%M:%S %Y %z")
        except TypeError:
            timestamp = input_timestamp

        if "y" in self.pattern:
            # MIN-year: 1970 and MAX-year: 2099
            timestamp = timestamp.replace(year=random.randrange(1970, 2099, 1))
        if "M" in self.pattern:
            timestamp = timestamp.replace(month=random.randrange(1, 12, 1))
        if "d" in self.pattern:
            max_day = calendar.monthrange(timestamp.year, timestamp.month)[1]
            timestamp = timestamp.replace(day=random.randrange(1, max_day, 1))
        if "h" in self.pattern:
            if self.limit is not False:
                timestamp = timestamp.replace(hour=random.randrange(self.limit[0], self.limit[1], 1))
            else:
                timestamp = timestamp.replace(hour=random.randrange(1, 24, 1))
        if "m" in self.pattern:
            timestamp = timestamp.replace(minute=random.randrange(1, 60, 1))
        if "s" in self.pattern:
            timestamp = timestamp.replace(second=random.randrange(1, 60, 1))
        return timestamp

    @staticmethod
    def custom(year, month, day, hour, minute, second, timezone): # pylint: disable=too-many-arguments
        """Some custom time"""
        utc_offset = datetime.timedelta(hours=timezone)
        time_stamp = datetime.datetime(year,
                                       month,
                                       day,
                                       hour,
                                       minute,
                                       second).replace(
                                           tzinfo=datetime.timezone(offset=utc_offset)).strftime("%a %b %d %H:%M:%S %Y %z")
        return time_stamp

    def plus_hour(self, timestamp, hours):
        """adds hour to timestamp and returns"""
        timestamp = datetime.datetime.strptime(timestamp, "%a %b %d %H:%M:%S %Y %z")
        timestamp += datetime.timedelta(hours=hours)
        #print(timestamp)
        if timestamp.hour < self.limit[0]:
            diff_to_limit = self.limit[0] - timestamp.hour
            timestamp += datetime.timedelta(hours=diff_to_limit)
        elif timestamp.hour > self.limit[1]:
            diff_to_limit = timestamp.hour - self.limit[1]
            timestamp -= datetime.timedelta(hours=diff_to_limit)
        return timestamp.strftime("%a %b %d %H:%M:%S %Y %z")

    @staticmethod
    def average(stamp_list):
        """adds hour to timestamp and returns"""
        list_of_dates = []
        for first, second in stamp_list:
            stamp_first = datetime.datetime.strptime(first, "%a %b %d %H:%M:%S %Y %z")
            stamp_second = datetime.datetime.strptime(second, "%a %b %d %H:%M:%S %Y %z")
            list_of_dates.append(stamp_first)
            list_of_dates.append(stamp_second)
        timedeltas = [list_of_dates[i-1]-list_of_dates[i] for i in range(1, len(list_of_dates))]
        average_timedelta = sum(timedeltas, datetime.timedelta(0)) / len(timedeltas)
        return average_timedelta

    @staticmethod
    def seconds_to_gitstamp(seconds, time_zone):
        """ time in utc + offset"""
        return datetime.datetime.fromtimestamp(seconds, datetime.timezone(datetime.timedelta(seconds=-time_zone))).strftime("%a %b %d %H:%M:%S %Y %z")

    def get_next_timestamp(self, repo):
        """ returns the next timestamp"""
        if self.mode == "reduce":
            stamp = self.reduce(self.now())
            return stamp
        if self.mode == "simple":
            commit_id = repo.git.rev_list(repo.active_branch.name).splitlines()[1]
            commit = repo.commit(commit_id)
            last_timestamp = self.seconds_to_gitstamp(commit.authored_date, commit.author_tz_offset)
            return self.plus_hour(last_timestamp, 1)
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
