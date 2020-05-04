import functools
import time

from datetime import datetime


DATE_FMT = "%a %b %d %H:%M:%S %Y %z"


def fmtdate(timestamp: datetime) -> str:
    return timestamp.strftime(DATE_FMT)


def retry(retry_count=5, delay=5, allowed_exceptions=()):
    # https://codereview.stackexchange.com/a/188544
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            result = None
            last_exception = None
            for _ in range(retry_count):
                try:
                    result = f(*args, **kwargs)
                    if result:
                        return result
                except allowed_exceptions as e:
                    last_exception = e
                #log.debug("Waiting for %s seconds before retrying again")
                time.sleep(delay)

            if last_exception is not None:
                raise type(last_exception) from last_exception

            return result

        return wrapper
    return decorator
