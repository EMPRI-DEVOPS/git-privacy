from datetime import datetime, timezone
import git
import re
from typing import Optional, Tuple

from . import Encoder, BasicEncoder
from ..crypto import EncryptionProvider
from ..dateredacter import DateRedacter


MSG_TAG = "GitPrivacy: "


class MessageEmbeddingEncoder(BasicEncoder):
    def __init__(self,
                 redacter: DateRedacter,
                 crypto: EncryptionProvider) -> None:
        super().__init__(redacter)
        self.crypto = crypto


    def get_message_extra(self, commit: git.Commit) -> str:
        if not _contains_tag(commit):  # keep prior tag if already present
            encdates = _encrypt_for_msg(self.crypto,
                                    commit.authored_datetime,
                                    commit.committed_datetime)
            return f"{MSG_TAG}{encdates}"
        else:
            return ""


    def decode(self, commit: git.Commit) -> Tuple[datetime, datetime]:
        dec_dates = _decrypt_from_msg(self.crypto, commit.message)
        if dec_dates is None:
            # decryption failed return redacted dates
            return (commit.authored_datetime,
                    commit.committed_datetime)
        return dec_dates


def _contains_tag(commit: git.Commit):
    return any([line.startswith(MSG_TAG)
               for line in commit.message.splitlines()])


def _extract_enc_dates(msg: str) -> Optional[str]:
    """Extract encrypted dates from the commit message"""
    for line in msg.splitlines():
        match = re.search(fr'^{MSG_TAG}(\S+)', line)
        if match:
            return match.group(1)
    return None


def _encrypt_for_msg(crypto: EncryptionProvider, a_date: datetime,
                     c_date: datetime) -> str:
    plain = ";".join(_strftime(d) for d in (a_date, c_date))
    return crypto.encrypt(plain)


def _decrypt_from_msg(crypto: EncryptionProvider,
                      message: str) -> Optional[Tuple[datetime, datetime]]:
    enc_dates = _extract_enc_dates(message)
    if crypto is None or enc_dates is None:
        return None
    plain_dates = crypto.decrypt(enc_dates)
    if plain_dates is None:
        return None
    a_date, c_date = [_strptime(d) for d in plain_dates.split(";")]
    return a_date, c_date


def _strftime(d: datetime) -> str:
    """Returns a UTC Posix timestamp with timezone information"""
    utc_sec = int(d.timestamp())
    tz = d.strftime("%z")
    return f"{utc_sec} {tz}"


def _strptime(string: str) -> datetime:
    """Takes a UTC Posix timestamp with timezone information"""
    seconds, tz = string.split()
    return datetime.fromtimestamp(
        int(seconds),
        datetime.strptime(tz, "%z").tzinfo,
    )
