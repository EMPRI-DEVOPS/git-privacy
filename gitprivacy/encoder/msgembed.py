import git  # type: ignore
import re

from datetime import datetime, timezone
from typing import Optional, Tuple

from . import Encoder, BasicEncoder
from .. import utils
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


    def decode(self, commit: git.Commit) -> Tuple[Optional[datetime], Optional[datetime]]:
        return _decrypt_from_msg(self.crypto, commit.message)


def _contains_tag(commit: git.Commit):
    return any([line.startswith(MSG_TAG)
               for line in commit.message.splitlines()])


def _extract_enc_dates(msg: str) -> Optional[Tuple[str, Optional[str]]]:
    """Extract encrypted dates from the commit message

    Returns either a combined cipher for author and committer date or one
    separate cipher each if present.
    """
    for line in msg.splitlines():
        # 2nd cipher is optional for backward compatability with
        # combined author and committer date ciphers
        match = re.search(fr'^{MSG_TAG}(\S+)(?: (\S+))?', line)
        if match:
            ad_cipher, cd_cipher = match.groups()
            return (ad_cipher, cd_cipher)
    return None


def _encrypt_for_msg(crypto: EncryptionProvider, a_date: datetime,
                     c_date: datetime) -> str:
    """Returns ciphertexts for author and committer date joined by a
    whitespace."""
    cipher = " ".join(
        crypto.encrypt(utils.dt2gitdate(d))
        for d in (a_date, c_date)
    )
    return cipher


def _decrypt_from_msg(crypto: EncryptionProvider,
                      message: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    enc_dates = _extract_enc_dates(message)
    if crypto is None or enc_dates is None:
        return (None, None)
    enc_adate, enc_cdate = enc_dates
    raw_adate = crypto.decrypt(enc_adate)
    if enc_cdate:
        # use separate committer date
        raw_cdate = crypto.decrypt(enc_cdate)
        assert raw_adate is None or ";" not in raw_adate
    elif raw_adate and not enc_cdate:
        # combined cipher compatability mode
        assert ";" in raw_adate
        raw_adate, raw_cdate = raw_adate.split(";")
    else:
        # no readable ciphertext to use
        assert not raw_adate and not enc_cdate
        raw_cdate = None

    a_date = None
    c_date = None
    if raw_adate:
        a_date = utils.gitdate2dt(raw_adate)
    if raw_cdate:
        c_date = utils.gitdate2dt(raw_cdate)
    return a_date, c_date
