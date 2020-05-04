from datetime import datetime


DATE_FMT = "%a %b %d %H:%M:%S %Y %z"


def fmtdate(timestamp: datetime) -> str:
    return timestamp.strftime(DATE_FMT)
