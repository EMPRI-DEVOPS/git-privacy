from datetime import datetime

import git  # type: ignore

import gitprivacy.dateredacter as dateredacter


DATE_FMT = "%a %b %d %H:%M:%S %Y %z"


def fmtdate(timestamp: datetime) -> str:
    return timestamp.strftime(DATE_FMT)


def dt2gitdate(d: datetime) -> str:
    """Returns a UTC Posix timestamp with timezone information"""
    utc_sec = int(d.timestamp())
    tz = d.strftime("%z")
    return f"{utc_sec} {tz}"


def gitdate2dt(string: str) -> datetime:
    """Takes a UTC Posix timestamp with timezone information"""
    seconds, tz = string.split()
    return datetime.fromtimestamp(
        int(seconds),
        datetime.strptime(tz, "%z").tzinfo,
    )


def is_already_redacted(redacter: dateredacter.DateRedacter,
                        commit: git.Commit) -> bool:
    """Check if the timestamps are already redacted."""
    adate = commit.authored_datetime
    cdate = commit.committed_datetime
    new_ad = redacter.redact(adate)
    new_cd = redacter.redact(cdate)
    if new_ad == adate and new_cd == cdate:
        return True
    return False


def get_named_ref(commit: git.Commit) -> str:
    """Get a user-friendly named ref for the commit."""
    _hexsha, name = commit.name_rev.split(" ")
    return remove_prefix(name, "remotes/")


def remove_prefix(string: str, prefix: str) -> str:
    if string.startswith(prefix):
        return string[len(prefix):]
    return string
