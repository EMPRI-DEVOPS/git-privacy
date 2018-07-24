"""defines git timestamps"""
import time
import datetime
import re
import itertools
from git import Repo

class TimeStamp:

    def __init__(self, limit=False, mode=False):
        super(TimeStamp, self).__init__()
        foo_bar = re.search('([0-9]+)-([0-9]+)', str(limit))
        self.limit = [int(foo_bar.group(1)), int(foo_bar.group(2))]
        self.mode = mode

    @staticmethod
    def pairwise(iterable):
        "s -> (s0,s1), (s1,s2), (s2, s3), ..."
        a, b = itertools.tee(iterable)
        next(b, None)
        return zip(a, b)

    """Timestamps"""
    @staticmethod
    def utc_now():
        """ time in utc + offset"""
        utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
        utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
        ts = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone(offset=utc_offset)).strftime("%a %b %d %H:%M:%S %Y %z")
        return ts

    @staticmethod
    def now():
        """local time + offset"""
        utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
        utc_offset = datetime.timedelta(seconds=-utc_offset_sec)
        time_stamp = datetime.datetime.now().replace(tzinfo=datetime.timezone(offset=utc_offset)).strftime("%a %b %d %H:%M:%S %Y %z")
        return time_stamp

    @staticmethod
    def custom(year, month, day, hour, minute, second, timezone):
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
        for a, b in stamp_list:
            stamp_a = datetime.datetime.strptime(a, "%a %b %d %H:%M:%S %Y %z")
            stamp_b = datetime.datetime.strptime(b, "%a %b %d %H:%M:%S %Y %z")
            list_of_dates.append(stamp_a)
            list_of_dates.append(stamp_b)
        # subtracting datetimes gives timedeltas
        timedeltas = [list_of_dates[i-1]-list_of_dates[i] for i in range(1, len(list_of_dates))]
        # giving datetime.timedelta(0) as the start value makes sum work on tds
        average_timedelta = sum(timedeltas, datetime.timedelta(0)) / len(timedeltas)
        return average_timedelta



    @staticmethod
    def seconds_to_gitstamp(seconds, tz):
        """ time in utc + offset"""
        ts = datetime.datetime.fromtimestamp(seconds, datetime.timezone(datetime.timedelta(seconds=-tz))).strftime("%a %b %d %H:%M:%S %Y %z")
        return ts

    def get_next_timestamp(self, repo):
        if self.mode == "simple":
            commit_id = repo.git.rev_list("master").splitlines()[1]
            commit = repo.commit(commit_id)
            last_timestamp = self.seconds_to_gitstamp(commit.authored_date, commit.author_tz_offset)
            return self.plus_hour(last_timestamp, 1)
        else:
            commits = repo.git.rev_list("master").splitlines()
            list_of_stamps = []
            for a, b in self.pairwise(commits):
                stamp_a = self.seconds_to_gitstamp(repo.commit(a).authored_date, repo.commit(a).author_tz_offset)
                stamp_b = self.seconds_to_gitstamp(repo.commit(b).authored_date, repo.commit(b).author_tz_offset)
                list_of_stamps.append([stamp_a, stamp_b])
            last_commit_id = commits[1]
            last_commit = commit = repo.commit(last_commit_id)
            last_timestamp = self.seconds_to_gitstamp(last_commit.authored_date, last_commit.author_tz_offset)
            next_stamp = last_timestamp + self.average(list_of_stamps)
            return next_stamp