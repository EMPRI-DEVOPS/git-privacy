from datetime import datetime


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
